/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

/**
 * @file   fpb_debugmon_nuttx.c
 * @brief  NuttX-specific DebugMonitor implementation using up_debugpoint_add
 *
 * This implementation uses NuttX's debugpoint API which supports:
 * - FPB breakpoints for Code region (0x00000000-0x1FFFFFFF)
 * - DWT watchpoints for any address (including PSRAM, external memory)
 *
 * For code running in PSRAM, we use
 * DWT watchpoint in "execute" mode instead of FPB breakpoint.
 */

#if defined(__NuttX__) || defined(FPB_HOST_TESTING_NUTTX)

#include "fpb_debugmon.h"

#ifndef FPB_NO_DEBUGMON

#ifdef FPB_HOST_TESTING_NUTTX
/* Use external NuttX mock for host-based testing */
#include "nuttx_mock.h"
#include <string.h>
#include <stdio.h>

/* Suppress syslog in tests */
#define syslog(level, fmt, ...) ((void)0)

#else /* !FPB_HOST_TESTING_NUTTX */

#include <nuttx/config.h>
#include <nuttx/arch.h>
#include <nuttx/irq.h>
#include <nuttx/sched.h>
#include <arch/irq.h>
#include <string.h>
#include <syslog.h>
#include <stdio.h>
#include <errno.h>

/* NuttX internal dbgmonitor functions - declared in arm_internal.h */
#ifdef CONFIG_ARCH_HAVE_DEBUG
extern int arm_enable_dbgmonitor(void);
extern int arm_dbgmonitor(int irq, void* context, void* arg);
#endif

#ifndef NVIC_IRQ_DBGMONITOR
#define NVIC_IRQ_DBGMONITOR 12
#endif

/* Include compatibility shim AFTER NuttX headers, so that running_regs()
 * (defined in nuttx/sched.h) is detected correctly. On older NuttX without
 * running_regs(), the shim provides a fallback (CURRENT_REGS or NULL).
 */
#include "fpb_nuttx_compat.h"

#endif /* FPB_HOST_TESTING_NUTTX */

/* ============================================================================
 * Logging macros - auto-prefix [DBGMON], no-op in host test mode
 * ============================================================================ */

#define DBGMON_LOG(level, fmt, ...) syslog(level, "[DBGMON] " fmt, ##__VA_ARGS__)
#define DBGMON_INFO(fmt, ...) DBGMON_LOG(LOG_INFO, fmt, ##__VA_ARGS__)
#define DBGMON_ERR(fmt, ...) DBGMON_LOG(LOG_ERR, fmt, ##__VA_ARGS__)
#define DBGMON_WARN(fmt, ...) DBGMON_LOG(LOG_WARNING, fmt, ##__VA_ARGS__)

/* Stack frame offsets for Cortex-M */
#define STACK_R0 0
#define STACK_R1 1
#define STACK_R2 2
#define STACK_R3 3
#define STACK_R12 4
#define STACK_LR 5
#define STACK_PC 6
#define STACK_XPSR 7

/* ============================================================================
 * State
 * ============================================================================ */

typedef struct {
    uint32_t original_addr; /* Original function address (without Thumb bit), 0 = not used */
    uint32_t redirect_addr; /* Redirect target address (with Thumb bit) */
} debugmon_redirect_t;

static struct {
    bool initialized;
    debugmon_redirect_t redirects[FPB_DEBUGMON_MAX_REDIRECTS];
} g_debugmon_state;

/* ============================================================================
 * Debugpoint helper
 * ============================================================================ */

/* Determine debugpoint type and size based on target address.
 * - Code region (0x00000000-0x1FFFFFFF): FPB breakpoint, size=0
 * - Other regions (SRAM, PSRAM, etc.): breakpoint with size=2 (Thumb)
 */
static void debugpoint_params(uint32_t addr, int* type, size_t* size) {
    *type = DEBUGPOINT_BREAKPOINT;
    *size = (addr < 0x20000000UL) ? 0 : 2;
}

/* ============================================================================
 * Debugpoint callback
 * ============================================================================ */

/**
 * @brief Debugpoint callback - called when breakpoint/watchpoint triggers
 *
 * This is called from NuttX's DebugMonitor exception handler.
 * We modify the stacked PC to redirect execution to our inject function.
 */
static void debugmon_callback(int type, void* addr, size_t size, void* arg) {
    (void)type;
    (void)size;
    (void)addr;

    debugmon_redirect_t* redirect = (debugmon_redirect_t*)arg;

    if (!redirect || redirect->original_addr == 0) {
        DBGMON_WARN("callback: no redirect\n");
        return;
    }

    /* Get current register context from NuttX
     * In exception handler, running_regs() points to the saved register context
     * which was set up by arm_doirq(): tcb->xcp.regs = regs;
     *
     * fpb_nuttx_compat.h maps running_regs() to CURRENT_REGS on old NuttX
     * (< April 2024). On the intermediate period (April-Sept 2024), users
     * must manually define running_regs() via build flags.
     */
    uint32_t* regs = (uint32_t*)running_regs();
    if (!regs) {
        DBGMON_ERR("callback: no regs context\n");
        return;
    }

    /* Modify PC to redirect execution */
    uint32_t old_pc = regs[REG_PC];
    regs[REG_PC] = redirect->redirect_addr;

    (void)old_pc;
    // DBGMON_LOG(LOG_DEBUG, "redirect: 0x%08lX -> 0x%08lX\n", (unsigned long)old_pc,
    //            (unsigned long)redirect->redirect_addr);
}

/* ============================================================================
 * Public API Implementation
 * ============================================================================ */

int fpb_debugmon_init(void) {
    DBGMON_INFO("NuttX init\n");

    memset(&g_debugmon_state, 0, sizeof(g_debugmon_state));

#ifdef CONFIG_ARCH_HAVE_DEBUG
    /* Re-attach NuttX's arm_dbgmonitor handler.
     * Some platforms override this with a PANIC() handler in bes_irq.c,
     * so we need to replace it with NuttX's implementation that properly
     * dispatches to our callback via up_debugpoint_add().
     */
    irq_attach(NVIC_IRQ_DBGMONITOR, arm_dbgmonitor, NULL);
    up_enable_irq(NVIC_IRQ_DBGMONITOR);

    /* Initialize FPB and DWT hardware */
    arm_enable_dbgmonitor();
    DBGMON_INFO("Attached NuttX arm_dbgmonitor handler\n");
#else
    DBGMON_ERR("CONFIG_ARCH_HAVE_DEBUG not enabled!\n");
    return -1;
#endif

    g_debugmon_state.initialized = true;
    return 0;
}

void fpb_debugmon_deinit(void) {
    if (!g_debugmon_state.initialized) {
        return;
    }

    /* Remove all debugpoints */
    for (int i = 0; i < FPB_DEBUGMON_MAX_REDIRECTS; i++) {
        if (g_debugmon_state.redirects[i].original_addr != 0) {
            fpb_debugmon_clear_redirect(i);
        }
    }

    memset(&g_debugmon_state, 0, sizeof(g_debugmon_state));
}

int fpb_debugmon_set_redirect(uint8_t comp_id, uint32_t original_addr, uint32_t redirect_addr) {
    DBGMON_INFO("set_redirect comp=%d orig=0x%08lX redir=0x%08lX\n", comp_id, (unsigned long)original_addr,
                (unsigned long)redirect_addr);

    if (!g_debugmon_state.initialized) {
        DBGMON_ERR("not initialized\n");
        return -1;
    }

    if (comp_id >= FPB_DEBUGMON_MAX_REDIRECTS) {
        DBGMON_ERR("invalid comp_id %d\n", comp_id);
        return -1;
    }

    /* Clear existing redirect if any */
    if (g_debugmon_state.redirects[comp_id].original_addr != 0) {
        fpb_debugmon_clear_redirect(comp_id);
    }

    /* Strip Thumb bit */
    uint32_t match_addr = original_addr & ~1UL;

    /* Store redirect info */
    g_debugmon_state.redirects[comp_id].original_addr = match_addr;
    g_debugmon_state.redirects[comp_id].redirect_addr = redirect_addr | 1; /* Ensure Thumb bit */

    /* Determine debugpoint type based on address region */
    int type;
    size_t size;
    debugpoint_params(match_addr, &type, &size);

    if (match_addr < 0x20000000UL) {
        DBGMON_INFO("using BREAKPOINT (FPB) for code region\n");
    } else {
        DBGMON_INFO("using BREAKPOINT for non-code region 0x%08lX\n", (unsigned long)match_addr);
    }

    /* Add debugpoint using NuttX API */
    int ret = up_debugpoint_add(type, (void*)(uintptr_t)match_addr, size, debugmon_callback,
                                &g_debugmon_state.redirects[comp_id]);
    if (ret < 0) {
        DBGMON_ERR("up_debugpoint_add failed: %d\n", ret);
        g_debugmon_state.redirects[comp_id].original_addr = 0;
        g_debugmon_state.redirects[comp_id].redirect_addr = 0;
        return -1;
    }

    DBGMON_INFO("set_redirect OK\n");
    return 0;
}

int fpb_debugmon_clear_redirect(uint8_t comp_id) {
    if (!g_debugmon_state.initialized) {
        return -1;
    }

    if (comp_id >= FPB_DEBUGMON_MAX_REDIRECTS) {
        return -1;
    }

    if (g_debugmon_state.redirects[comp_id].original_addr == 0) {
        return 0;
    }

    uint32_t match_addr = g_debugmon_state.redirects[comp_id].original_addr;

    /* Remove debugpoint */
    int type;
    size_t size;
    debugpoint_params(match_addr, &type, &size);
    up_debugpoint_remove(type, (void*)(uintptr_t)match_addr, size);

    /* Clear redirect entry */
    g_debugmon_state.redirects[comp_id].original_addr = 0;
    g_debugmon_state.redirects[comp_id].redirect_addr = 0;

    return 0;
}

uint32_t fpb_debugmon_get_redirect(uint32_t original_addr) {
    uint32_t match_addr = original_addr & ~1UL;

    for (int i = 0; i < FPB_DEBUGMON_MAX_REDIRECTS; i++) {
        if (g_debugmon_state.redirects[i].original_addr == match_addr) {
            return g_debugmon_state.redirects[i].redirect_addr;
        }
    }

    return 0;
}

bool fpb_debugmon_is_active(void) {
    return g_debugmon_state.initialized;
}

/* Handler not needed - NuttX calls our callback directly */
void fpb_debugmon_handler(uint32_t* stack_frame) {
    (void)stack_frame;
    /* Not used in NuttX implementation */
}

#endif /* !FPB_NO_DEBUGMON */

#endif /* __NuttX__ || FPB_HOST_TESTING_NUTTX */
