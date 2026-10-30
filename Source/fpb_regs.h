/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Cortex-M FPB and Debug Register Definitions
 */

#ifndef __FPB_REGS_H
#define __FPB_REGS_H

#include <stdint.h>

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

/* ============================================================================
 * FPB Registers (Flash Patch and Breakpoint Unit)
 * ============================================================================ */

#define FPB_BASE 0xE0002000UL

/* FPB Control Register */
#define FPB_CTRL (*(volatile uint32_t*)(FPB_BASE + 0x000))

/* FPB Remap Register */
#define FPB_REMAP (*(volatile uint32_t*)(FPB_BASE + 0x004))

/* FPB Comparator Registers (0-7) */
#define FPB_COMP(n) (*(volatile uint32_t*)(FPB_BASE + 0x008 + ((n)*4)))

/* ============================================================================
 * Debug Registers
 * ============================================================================ */

/* Debug Halting Control and Status Register */
#define DHCSR (*(volatile uint32_t*)0xE000EDF0)

/* Debug Exception and Monitor Control Register */
#define DEMCR (*(volatile uint32_t*)0xE000EDFC)

/* Debug Fault Status Register */
#define DFSR (*(volatile uint32_t*)0xE000ED30)

#endif /* FPB_HOST_TESTING */

/* ============================================================================
 * FPB Control Register Bits
 * ============================================================================ */

#define FPB_CTRL_ENABLE (1UL << 0)
#define FPB_CTRL_KEY (1UL << 1)
#define FPB_CTRL_NUM_CODE_MASK (0xFUL << 4)
#define FPB_CTRL_NUM_CODE_SHIFT 4

/* ============================================================================
 * FPB Comparator Register Bits
 * ============================================================================ */

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

/* Aliases for fpb_inject.c compatibility */
#define FPB_REPLACE_REMAP FPB_COMP_REPLACE_REMAP
#define FPB_REPLACE_LOWER FPB_COMP_REPLACE_BKPT_LOWER
#define FPB_REPLACE_UPPER FPB_COMP_REPLACE_BKPT_UPPER
#define FPB_REPLACE_BOTH FPB_COMP_REPLACE_BKPT_BOTH

/* ============================================================================
 * Debug Register Bits
 * ============================================================================ */

/* DHCSR bits */
#define DHCSR_DBGKEY (0xA05FUL << 16) /* Debug key for write access */
#define DHCSR_C_DEBUGEN (1UL << 0)    /* Debug enable */

/* DEMCR bits */
#define DEMCR_TRCENA (1UL << 24)   /* Enable trace and DWT */
#define DEMCR_MON_EN (1UL << 16)   /* Enable DebugMonitor exception */
#define DEMCR_MON_PEND (1UL << 17) /* Pend DebugMonitor exception */
#define DEMCR_MON_STEP (1UL << 18) /* Single step the processor */
#define DEMCR_MON_REQ (1UL << 19)  /* DebugMonitor semaphore */

/* DFSR bits */
#define DFSR_BKPT (1UL << 1) /* Breakpoint flag */

/* ============================================================================
 * Exception Stack Frame Offsets
 * ============================================================================ */

#define STACK_R0 0
#define STACK_R1 1
#define STACK_R2 2
#define STACK_R3 3
#define STACK_R12 4
#define STACK_LR 5
#define STACK_PC 6
#define STACK_XPSR 7

/* ============================================================================
 * Memory Barrier Helpers
 * ============================================================================ */

#ifndef FPB_HOST_TESTING
/* dsb/isb exist on ARM only; other targets (e.g. the simulator) build this
 * file but never drive the FPB, so they are empty there. */
#if defined(__arm__) || defined(__thumb__)
static inline void dsb(void) {
    __asm volatile("dsb" ::: "memory");
}

static inline void isb(void) {
    __asm volatile("isb" ::: "memory");
}
#else
#define dsb() ((void)0)
#define isb() ((void)0)
#endif
#endif /* !FPB_HOST_TESTING */

#endif /* __FPB_REGS_H */
