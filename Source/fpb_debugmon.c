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
 * @file   fpb_debugmon.c
 * @brief  DebugMonitor-based function redirection implementation
 *
 * This module provides an alternative to FPB REMAP for ARMv8-M cores
 * where REMAP functionality has been removed.
 *
 * Exception Stack Frame (Cortex-M):
 *   [SP+0]  R0
 *   [SP+4]  R1
 *   [SP+8]  R2
 *   [SP+12] R3
 *   [SP+16] R12
 *   [SP+20] LR (R14)
 *   [SP+24] PC (Return address) <- We modify this!
 *   [SP+28] xPSR
 *
 * When DebugMonitor is triggered by FPB breakpoint:
 * 1. CPU pushes registers to stack
 * 2. Stacked PC = address that triggered breakpoint
 * 3. We look up redirect target for that address
 * 4. We modify stacked PC to point to redirect target
 * 5. On exception return, CPU pops modified PC -> execution continues at new location
 */

#include "fpb_debugmon.h"

/* NuttX uses fpb_debugmon_nuttx.c instead */
#if !defined(FPB_NO_DEBUGMON) && !defined(__NuttX__)

#include <string.h>
#include <stdio.h>

/* Debug logging - uses simple UART polling to avoid dependencies */
#define FPB_DEBUGMON_LOG 0

#if FPB_DEBUGMON_LOG

#ifdef __STM32F1__
/* Direct UART1 output for debugging (polling mode, no interrupts) */
#define USART1_BASE 0x40013800UL
#define USART1_SR (*(volatile uint32_t*)(USART1_BASE + 0x00))
#define USART1_DR (*(volatile uint32_t*)(USART1_BASE + 0x04))
#define USART_SR_TXE (1UL << 7)

static void dbg_putc(char c) {
    while (!(USART1_SR & USART_SR_TXE))
        ;
    USART1_DR = c;
}
#else
#include <stdio.h>

static void dbg_putc(char c) {
    putc(c, stdout);
}
#endif

static void dbg_puts(const char* s) {
    while (*s)
        dbg_putc(*s++);
}

static void dbg_hex32(uint32_t v) {
    const char* hex = "0123456789ABCDEF";
    dbg_puts("0x");
    for (int i = 28; i >= 0; i -= 4) {
        dbg_putc(hex[(v >> i) & 0xF]);
    }
}
#else
#define dbg_puts(s) ((void)0)
#define dbg_hex32(v) ((void)0)
#endif

/* ============================================================================
 * Cortex-M Debug Registers
 * ============================================================================ */

#ifdef FPB_HOST_TESTING
/* Use mock registers for host-based testing */
#include "fpb_mock_regs.h"

/* Mock debug registers */
extern uint32_t mock_dhcsr;
extern uint32_t mock_demcr;
extern uint32_t mock_dfsr;

#define DHCSR mock_dhcsr
#define DEMCR mock_demcr
#define DFSR mock_dfsr

#else /* !FPB_HOST_TESTING */

/* Debug Halting Control and Status Register */
#define DHCSR (*(volatile uint32_t*)0xE000EDF0)

/* Debug Exception and Monitor Control Register */
#define DEMCR (*(volatile uint32_t*)0xE000EDFC)

/* Debug Fault Status Register */
#define DFSR (*(volatile uint32_t*)0xE000ED30)

/* FPB Registers */
#define FPB_BASE 0xE0002000UL
#define FPB_CTRL (*(volatile uint32_t*)(FPB_BASE + 0x000))
#define FPB_COMP(n) (*(volatile uint32_t*)(FPB_BASE + 0x008 + ((n)*4)))

#endif /* FPB_HOST_TESTING */

/* Debug register bits */
#define DHCSR_DBGKEY (0xA05FUL << 16) /* Debug key for write access */
#define DHCSR_C_DEBUGEN (1UL << 0)    /* Debug enable */

#define DEMCR_TRCENA (1UL << 24)   /* Enable trace and DWT */
#define DEMCR_MON_EN (1UL << 16)   /* Enable DebugMonitor exception */
#define DEMCR_MON_PEND (1UL << 17) /* Pend DebugMonitor exception */
#define DEMCR_MON_STEP (1UL << 18) /* Single step the processor */
#define DEMCR_MON_REQ (1UL << 19)  /* DebugMonitor semaphore */

#define DFSR_BKPT (1UL << 1) /* Breakpoint flag */

#define FPB_CTRL_ENABLE (1UL << 0)
#define FPB_CTRL_KEY (1UL << 1)
#define FPB_CTRL_NUM_CODE_MASK (0xFUL << 4)
#define FPB_CTRL_NUM_CODE_SHIFT 4

/* FPB Comparator configuration */
#define FPB_COMP_ENABLE (1UL << 0)
#define FPB_COMP_ADDR_MASK 0x1FFFFFFCUL

/* FPBv1 (Cortex-M3/M4) REPLACE field [31:30]:
 *   00 = REMAP mode (requires FP_REMAP to be set up)
 *   01 = BKPT on lower halfword (bits [1:0] of address = 00)
 *   10 = BKPT on upper halfword (bits [1:0] of address = 10)
 *   11 = BKPT on both halfwords
 *
 * FPBv2 (ARMv8-M) doesn't have REPLACE field; all matches generate BKPT
 */
#define FPB_COMP_REPLACE_REMAP (0UL << 30)
#define FPB_COMP_REPLACE_BKPT_LOWER (1UL << 30)
#define FPB_COMP_REPLACE_BKPT_UPPER (2UL << 30)
#define FPB_COMP_REPLACE_BKPT_BOTH (3UL << 30)

/* Stack frame offsets */
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
    uint8_t num_comp;
    debugmon_redirect_t redirects[FPB_DEBUGMON_MAX_REDIRECTS];
} g_debugmon_state;

/* ============================================================================
 * Implementation
 * ============================================================================ */

#ifndef FPB_HOST_TESTING
static inline void dsb(void) {
    __asm volatile("dsb" ::: "memory");
}

static inline void isb(void) {
    __asm volatile("isb" ::: "memory");
}
#endif /* !FPB_HOST_TESTING */

int fpb_debugmon_init(void) {
    dbg_puts("[DBGMON] init start\r\n");

    memset(&g_debugmon_state, 0, sizeof(g_debugmon_state));

    /* Check FPB availability */
    uint32_t ctrl = FPB_CTRL;
    g_debugmon_state.num_comp = (ctrl & FPB_CTRL_NUM_CODE_MASK) >> FPB_CTRL_NUM_CODE_SHIFT;

    dbg_puts("[DBGMON] FPB comps: ");
    dbg_hex32(g_debugmon_state.num_comp);
    dbg_puts("\r\n");

    if (g_debugmon_state.num_comp == 0) {
        return -1; /* No FPB */
    }

    if (g_debugmon_state.num_comp > FPB_DEBUGMON_MAX_REDIRECTS) {
        g_debugmon_state.num_comp = FPB_DEBUGMON_MAX_REDIRECTS;
    }

    /* Enable trace (required for some debug features) */
    DEMCR |= DEMCR_TRCENA;

    /* Try to enable debug if not already enabled
     * Note: On Cortex-M3, C_DEBUGEN can only be set by external debugger
     * This write may be ignored, but we try anyway
     */
    uint32_t dhcsr = DHCSR;
    dbg_puts("[DBGMON] DHCSR before: ");
    dbg_hex32(dhcsr);
    dbg_puts("\r\n");

    if (!(dhcsr & DHCSR_C_DEBUGEN)) {
        /* Try to enable - this usually requires debugger but worth trying */
        DHCSR = DHCSR_DBGKEY | DHCSR_C_DEBUGEN;
        dsb();
    }

    dbg_puts("[DBGMON] DHCSR after: ");
    dbg_hex32(DHCSR);
    dbg_puts("\r\n");

    /* Enable DebugMonitor exception
     * This allows breakpoints to trigger DebugMonitor instead of halting
     * Note: If debugger is attached, it may override this
     */
    DEMCR |= DEMCR_MON_EN;

    dbg_puts("[DBGMON] DEMCR: ");
    dbg_hex32(DEMCR);
    dbg_puts("\r\n");

    /* Note: DebugMonitor priority is fixed and cannot be configured via SHPR.
     * It has a priority of -1 (higher than all configurable exceptions).
     */

    /* Clear all FPB comparators */
    for (uint8_t i = 0; i < g_debugmon_state.num_comp; i++) {
        FPB_COMP(i) = 0;
    }

    /* Enable FPB */
    FPB_CTRL = FPB_CTRL_KEY | FPB_CTRL_ENABLE;

    dsb();
    isb();

    g_debugmon_state.initialized = true;

    return 0;
}

void fpb_debugmon_deinit(void) {
    if (!g_debugmon_state.initialized) {
        return;
    }

    /* Disable all comparators */
    for (uint8_t i = 0; i < g_debugmon_state.num_comp; i++) {
        FPB_COMP(i) = 0;
    }

    /* Disable DebugMonitor */
    DEMCR &= ~DEMCR_MON_EN;

    memset(&g_debugmon_state, 0, sizeof(g_debugmon_state));

    dsb();
    isb();
}

int fpb_debugmon_set_redirect(uint8_t comp_id, uint32_t original_addr, uint32_t redirect_addr) {
    dbg_puts("[DBGMON] set_redirect comp=");
    dbg_hex32(comp_id);
    dbg_puts(" orig=");
    dbg_hex32(original_addr);
    dbg_puts(" redir=");
    dbg_hex32(redirect_addr);
    dbg_puts("\r\n");

    if (!g_debugmon_state.initialized) {
        dbg_puts("[DBGMON] ERROR: not initialized\r\n");
        return -1;
    }

    if (comp_id >= g_debugmon_state.num_comp) {
        dbg_puts("[DBGMON] ERROR: invalid comp_id\r\n");
        return -1;
    }

    /* Note: Traditional FPB (FPBv1) only supports Code region (0x00000000-0x1FFFFFFF).
     * However, FPBv2 on ARMv8-M supports wider address ranges.
     * Some platforms may execute code from PSRAM or external memory.
     * We remove the address check and let the hardware decide if it's supported.
     * If the address is not matchable by FPB, the breakpoint simply won't trigger.
     */

    /* Strip Thumb bit for comparison */
    uint32_t match_addr = original_addr & ~1UL;

    /* Store redirect info */
    g_debugmon_state.redirects[comp_id].original_addr = match_addr;
    g_debugmon_state.redirects[comp_id].redirect_addr = redirect_addr | 1; /* Ensure Thumb bit */
    g_debugmon_state.redirects[comp_id].enabled = true;

    /* Configure FPB comparator for breakpoint
     *
     * On Cortex-M3/M4 (FPBv1), REPLACE bits [31:30]:
     *   00 = REMAP mode (requires FP_REMAP setup)
     *   01 = BKPT on lower halfword (address bits [1:0] = 00)
     *   10 = BKPT on upper halfword (address bits [1:0] = 10)
     *   11 = BKPT on both halfwords
     *
     * We use REPLACE=11 (BKPT_BOTH) to trigger on any access to this address.
     *
     * On ARMv8-M (FPBv2), there's no REPLACE field, comparator always generates BKPT.
     */
    uint32_t comp_val = (match_addr & FPB_COMP_ADDR_MASK) | FPB_COMP_REPLACE_BKPT_BOTH | FPB_COMP_ENABLE;
    FPB_COMP(comp_id) = comp_val;

    dbg_puts("[DBGMON] FPB_COMP[");
    dbg_hex32(comp_id);
    dbg_puts("] = ");
    dbg_hex32(comp_val);
    dbg_puts("\r\n");
    dbg_puts("[DBGMON] FPB_COMP readback = ");
    dbg_hex32(FPB_COMP(comp_id));
    dbg_puts("\r\n");

    dsb();
    isb();

    dbg_puts("[DBGMON] set_redirect OK\r\n");
    return 0;
}

int fpb_debugmon_clear_redirect(uint8_t comp_id) {
    if (!g_debugmon_state.initialized) {
        return -1;
    }

    if (comp_id >= g_debugmon_state.num_comp) {
        return -1;
    }

    /* Disable FPB comparator */
    FPB_COMP(comp_id) = 0;

    /* Clear redirect entry */
    g_debugmon_state.redirects[comp_id].original_addr = 0;
    g_debugmon_state.redirects[comp_id].redirect_addr = 0;
    g_debugmon_state.redirects[comp_id].enabled = false;

    dsb();
    isb();

    return 0;
}

uint32_t fpb_debugmon_get_redirect(uint32_t original_addr) {
    uint32_t match_addr = original_addr & ~1UL;

    for (uint8_t i = 0; i < g_debugmon_state.num_comp; i++) {
        if (g_debugmon_state.redirects[i].enabled && g_debugmon_state.redirects[i].original_addr == match_addr) {
            return g_debugmon_state.redirects[i].redirect_addr;
        }
    }

    return 0;
}

bool fpb_debugmon_is_active(void) {
    return g_debugmon_state.initialized;
}

void fpb_debugmon_handler(uint32_t* stack_frame) {
    dbg_puts("[DBGMON] *** HANDLER CALLED ***\r\n");

    /* Check if this was a breakpoint */
    uint32_t dfsr = DFSR;
    dbg_puts("[DBGMON] DFSR=");
    dbg_hex32(dfsr);
    dbg_puts("\r\n");

    if (!(dfsr & DFSR_BKPT)) {
        /* Not a breakpoint - shouldn't happen in our setup */
        dbg_puts("[DBGMON] Not a BKPT, returning\r\n");
        return;
    }

    /* Clear breakpoint flag */
    DFSR = DFSR_BKPT;

    /* Get the faulting PC (address that triggered breakpoint) */
    uint32_t faulting_pc = stack_frame[STACK_PC];
    dbg_puts("[DBGMON] faulting_pc=");
    dbg_hex32(faulting_pc);
    dbg_puts("\r\n");

    /* Look up redirect target */
    uint32_t redirect = fpb_debugmon_get_redirect(faulting_pc);
    dbg_puts("[DBGMON] redirect=");
    dbg_hex32(redirect);
    dbg_puts("\r\n");

    if (redirect != 0) {
        /* Modify stacked PC to redirect execution */
        stack_frame[STACK_PC] = redirect;
        dbg_puts("[DBGMON] PC redirected!\r\n");
    } else {
        dbg_puts("[DBGMON] WARNING: no redirect found!\r\n");
    }
    /* If no redirect found, execution continues at original address
     * This will immediately trigger another breakpoint - infinite loop!
     * To handle this properly, we'd need to:
     * 1. Temporarily disable the comparator
     * 2. Single-step past the breakpoint
     * 3. Re-enable the comparator
     *
     * For now, we assume all configured breakpoints have redirects.
     */
}

/* ============================================================================
 * DebugMonitor Handler (weak, for platforms without attach callback)
 * ============================================================================ */

#if !defined(FPB_DEBUGMON_NO_DEFAULT_HANDLER) && !defined(FPB_HOST_TESTING)
/**
 * @brief  DebugMonitor exception handler
 *
 * This is the actual exception vector handler.
 * It determines which stack was used and calls fpb_debugmon_handler.
 *
 * Note: On NuttX and other RTOS, use fpb_debugmon_set_attach_cb() instead,
 * as the exception vector is managed by the OS.
 */
__attribute__((weak, naked)) void DebugMon_Handler(void) {
    /* Use naked to avoid compiler-generated prologue/epilogue
     * which might corrupt the stack frame we need to read */
    __asm volatile(
        /* Quick debug output - toggle a GPIO or similar could be added here */

        /* Determine which stack pointer was used */
        "tst lr, #4\n"    /* Test bit 2 of EXC_RETURN */
        "ite eq\n"        /* If equal (bit 2 = 0, using MSP) */
        "mrseq r0, msp\n" /* Use MSP */
        "mrsne r0, psp\n" /* Else use PSP */

        /* r0 now contains stack_frame pointer */
        /* Call the C handler */
        "push {lr}\n"
        "bl fpb_debugmon_handler\n"
        "pop {lr}\n"
        "bx lr\n");
}
#endif /* !FPB_DEBUGMON_NO_DEFAULT_HANDLER && !FPB_HOST_TESTING */

#endif /* !FPB_NO_DEBUGMON && !__NuttX__ */
