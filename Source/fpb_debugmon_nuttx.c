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
 * For code running in PSRAM (e.g., 0x2Cxxxxxx on BES platform), we use
 * DWT watchpoint in "execute" mode instead of FPB breakpoint.
 */

#ifdef __NUTTX__

#include "fpb_debugmon.h"

#ifndef FPB_NO_DEBUGMON

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
    uint32_t original_addr; /* Original function address (without Thumb bit) */
    uint32_t redirect_addr; /* Redirect target address (with Thumb bit) */
    bool enabled;
} debugmon_redirect_t;

static struct {
    bool initialized;
    debugmon_redirect_t redirects[FPB_DEBUGMON_MAX_REDIRECTS];
} g_debugmon_state;

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

    uint32_t original_addr = (uint32_t)(uintptr_t)addr & ~1UL;
    debugmon_redirect_t* redirect = (debugmon_redirect_t*)arg;

    if (!redirect || !redirect->enabled) {
        syslog(LOG_WARNING, "[DBGMON] callback: no redirect for 0x%08lX\n", (unsigned long)original_addr);
        return;
    }

    /* Get current register context from NuttX
     * In exception handler, running_regs() points to the saved register context
     * which was set up by arm_doirq(): tcb->xcp.regs = regs;
     */
    uint32_t* regs = (uint32_t*)running_regs();
    if (!regs) {
        syslog(LOG_ERR, "[DBGMON] callback: no regs context\n");
        return;
    }

    /* Modify PC to redirect execution */
    uint32_t old_pc = regs[REG_PC];
    regs[REG_PC] = redirect->redirect_addr;

    // syslog(LOG_DEBUG, "[DBGMON] redirect: 0x%08lX -> 0x%08lX\n", (unsigned long)old_pc,
    //        (unsigned long)redirect->redirect_addr);
}

/* ============================================================================
 * Public API Implementation
 * ============================================================================ */

int fpb_debugmon_init(void) {
    syslog(LOG_INFO, "[DBGMON] NuttX init\n");

    memset(&g_debugmon_state, 0, sizeof(g_debugmon_state));

#ifdef CONFIG_ARCH_HAVE_DEBUG
    /* Re-attach NuttX's arm_dbgmonitor handler.
     * BES platform overrides this with a PANIC() handler in bes_irq.c,
     * so we need to replace it with NuttX's implementation that properly
     * dispatches to our callback via up_debugpoint_add().
     */
    irq_attach(NVIC_IRQ_DBGMONITOR, arm_dbgmonitor, NULL);
    up_enable_irq(NVIC_IRQ_DBGMONITOR);

    /* Initialize FPB and DWT hardware */
    arm_enable_dbgmonitor();
    syslog(LOG_INFO, "[DBGMON] Attached NuttX arm_dbgmonitor handler\n");
#else
    syslog(LOG_ERR, "[DBGMON] CONFIG_ARCH_HAVE_DEBUG not enabled!\n");
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
        if (g_debugmon_state.redirects[i].enabled) {
            fpb_debugmon_clear_redirect(i);
        }
    }

    memset(&g_debugmon_state, 0, sizeof(g_debugmon_state));
}

int fpb_debugmon_set_redirect(uint8_t comp_id, uint32_t original_addr, uint32_t redirect_addr) {
    syslog(LOG_INFO, "[DBGMON] set_redirect comp=%d orig=0x%08lX redir=0x%08lX\n", comp_id,
           (unsigned long)original_addr, (unsigned long)redirect_addr);

    if (!g_debugmon_state.initialized) {
        syslog(LOG_ERR, "[DBGMON] not initialized\n");
        return -1;
    }

    if (comp_id >= FPB_DEBUGMON_MAX_REDIRECTS) {
        syslog(LOG_ERR, "[DBGMON] invalid comp_id %d\n", comp_id);
        return -1;
    }

    /* Clear existing redirect if any */
    if (g_debugmon_state.redirects[comp_id].enabled) {
        fpb_debugmon_clear_redirect(comp_id);
    }

    /* Strip Thumb bit */
    uint32_t match_addr = original_addr & ~1UL;

    /* Store redirect info */
    g_debugmon_state.redirects[comp_id].original_addr = match_addr;
    g_debugmon_state.redirects[comp_id].redirect_addr = redirect_addr | 1; /* Ensure Thumb bit */
    g_debugmon_state.redirects[comp_id].enabled = true;

    /* Determine debugpoint type based on address region:
     * - Code region (0x00000000-0x1FFFFFFF): Use BREAKPOINT (FPB)
     * - Other regions (SRAM, PSRAM, etc.): Use WATCHPOINT_RO (DWT) as execute monitor
     *
     * Note: DWT watchpoint in RO mode can detect instruction fetches,
     * which effectively acts as an execute breakpoint for non-Code regions.
     */
    int type;
    size_t size;

    if (match_addr < 0x20000000UL) {
        /* Code region - use FPB breakpoint */
        type = DEBUGPOINT_BREAKPOINT;
        size = 0;
        syslog(LOG_INFO, "[DBGMON] using BREAKPOINT (FPB) for code region\n");
    } else {
        /* Non-code region - use DWT watchpoint
         * WATCHPOINT_RO monitors read accesses including instruction fetches
         */
        type = DEBUGPOINT_BREAKPOINT; /* Try breakpoint first */
        size = 2;                     /* Thumb instruction size */
        syslog(LOG_INFO, "[DBGMON] using BREAKPOINT for non-code region 0x%08lX\n", (unsigned long)match_addr);
    }

    /* Add debugpoint using NuttX API */
    int ret = up_debugpoint_add(type, (void*)match_addr, size, debugmon_callback, &g_debugmon_state.redirects[comp_id]);
    if (ret < 0) {
        syslog(LOG_ERR, "[DBGMON] up_debugpoint_add failed: %d\n", ret);
        g_debugmon_state.redirects[comp_id].enabled = false;
        return -1;
    }

    syslog(LOG_INFO, "[DBGMON] set_redirect OK\n");
    return 0;
}

int fpb_debugmon_clear_redirect(uint8_t comp_id) {
    if (!g_debugmon_state.initialized) {
        return -1;
    }

    if (comp_id >= FPB_DEBUGMON_MAX_REDIRECTS) {
        return -1;
    }

    if (!g_debugmon_state.redirects[comp_id].enabled) {
        return 0;
    }

    uint32_t match_addr = g_debugmon_state.redirects[comp_id].original_addr;

    /* Determine type based on address */
    int type = (match_addr < 0x20000000UL) ? DEBUGPOINT_BREAKPOINT : DEBUGPOINT_BREAKPOINT;
    size_t size = (match_addr < 0x20000000UL) ? 0 : 2;

    /* Remove debugpoint */
    up_debugpoint_remove(type, (void*)match_addr, size);

    /* Clear redirect entry */
    g_debugmon_state.redirects[comp_id].original_addr = 0;
    g_debugmon_state.redirects[comp_id].redirect_addr = 0;
    g_debugmon_state.redirects[comp_id].enabled = false;

    return 0;
}

uint32_t fpb_debugmon_get_redirect(uint32_t original_addr) {
    uint32_t match_addr = original_addr & ~1UL;

    for (int i = 0; i < FPB_DEBUGMON_MAX_REDIRECTS; i++) {
        if (g_debugmon_state.redirects[i].enabled && g_debugmon_state.redirects[i].original_addr == match_addr) {
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

#endif /* __NUTTX__ */
