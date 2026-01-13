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
 * @file   fpb_debugmon.h
 * @brief  DebugMonitor-based function redirection for ARMv8-M compatibility
 *
 * ARMv8-M Architecture Changes:
 * - FPB_REMAP functionality has been removed in ARMv8-M
 * - FPB can only set breakpoints, not remap instructions
 * - This module uses DebugMonitor exception to emulate REMAP behavior
 *
 * How it works:
 * 1. Configure FPB to generate breakpoint exceptions at target addresses
 * 2. Enable DebugMonitor exception (instead of halting debugger)
 * 3. In DebugMonitor handler, modify PC on stack to redirect to RAM code
 *
 * Advantages:
 * - Works on ARMv8-M (Cortex-M23, M33, M55, etc.)
 * - No Flash modification required
 * - Preserves all registers (R0-R3 arguments intact)
 *
 * Disadvantages:
 * - Higher latency than direct FPB REMAP (~20-50 cycles overhead)
 * - DebugMonitor has lower priority than some exceptions
 * - Cannot redirect code in exception handlers with same/higher priority
 *
 * Usage:
 * 1. Call fpb_debugmon_init() to enable DebugMonitor
 * 2. Use fpb_debugmon_set_redirect() to configure redirections
 * 3. FPB breakpoint triggers DebugMonitor -> handler changes PC -> execution continues at new location
 *
 * This is independent of FPB_TRAMPOLINE - use either:
 * - FPB_TRAMPOLINE: FPB REMAP to Flash trampoline, then jump to RAM (Cortex-M3/M4)
 * - FPB_DEBUGMON: FPB breakpoint -> DebugMonitor -> modify PC (ARMv8-M)
 */

#ifndef __FPB_DEBUGMON_H
#define __FPB_DEBUGMON_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>

/* Maximum number of redirects (same as FPB code comparators) */
#ifndef FPB_DEBUGMON_MAX_REDIRECTS
#define FPB_DEBUGMON_MAX_REDIRECTS 6
#endif

/**
 * @brief  Initialize DebugMonitor-based redirection
 * @note   This enables DebugMonitor exception and configures FPB for breakpoints
 * @retval 0: Success, -1: Failure (DebugMonitor not available or locked)
 */
int fpb_debugmon_init(void);

/**
 * @brief  Deinitialize DebugMonitor redirection
 */
void fpb_debugmon_deinit(void);

/**
 * @brief  Set a function redirect via DebugMonitor
 * @param  comp_id: FPB comparator ID (0 ~ FPB_DEBUGMON_MAX_REDIRECTS-1)
 * @param  original_addr: Original function address (in Flash/Code region)
 * @param  redirect_addr: New function address (can be in RAM)
 * @retval 0: Success, -1: Invalid parameter, -2: Comparator unavailable
 */
int fpb_debugmon_set_redirect(uint8_t comp_id, uint32_t original_addr, uint32_t redirect_addr);

/**
 * @brief  Clear a redirect
 * @param  comp_id: FPB comparator ID
 * @retval 0: Success, -1: Invalid parameter
 */
int fpb_debugmon_clear_redirect(uint8_t comp_id);

/**
 * @brief  Get redirect target for an address
 * @param  original_addr: Address to look up
 * @return Redirect target, or 0 if not found
 */
uint32_t fpb_debugmon_get_redirect(uint32_t original_addr);

/**
 * @brief  Check if DebugMonitor mode is active
 * @return true if initialized and active
 */
bool fpb_debugmon_is_active(void);

/**
 * @brief  DebugMonitor exception handler
 * @note   This should be called from DebugMon_Handler (or installed as the handler)
 *         It modifies the stacked PC to redirect execution
 * @param  stack_frame: Pointer to exception stack frame (MSP or PSP)
 */
void fpb_debugmon_handler(uint32_t* stack_frame);

#ifdef __cplusplus
}
#endif

#endif /* __FPB_DEBUGMON_H */
