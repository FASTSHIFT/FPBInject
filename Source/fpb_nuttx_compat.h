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
 * @file   fpb_nuttx_compat.h
 * @brief  NuttX API compatibility shims for different NuttX versions
 *
 * running_regs() was introduced in NuttX Sept 2024 (commit 19b4911d7fd,
 * "arch: remove up_current_regs in common code").
 *
 * Before that, the API for obtaining the current interrupt register context
 * went through two prior generations:
 *
 *   1. CURRENT_REGS macro  — pre-April 2024
 *      Defined in arch/<arch>/include/irq.h as:
 *        #define CURRENT_REGS (g_current_regs[up_cpu_index()])
 *
 *   2. up_current_regs() inline function — April 2024 to Sept 2024
 *      Defined in arch/<arch>/include/irq.h as:
 *        static inline uint32_t *up_current_regs(void)
 *
 *   3. running_regs() macro — Sept 2024+
 *      Defined in include/nuttx/sched.h as:
 *        #define running_regs() ((FAR void **)(g_running_task->xcp.regs))
 *
 * This header provides a transparent fallback so that fpb_debugmon_nuttx.c
 * can call running_regs() regardless of which NuttX version is in use.
 *
 * Fallback priority:
 *   1. running_regs (if already defined by NuttX headers) — no-op
 *   2. CURRENT_REGS (detectable via #ifdef) — oldest API
 *   3. NULL (graceful degradation — dpatch callback logs "no regs context")
 *
 * Note: The intermediate up_current_regs() API (April-Sept 2024) is a
 * static inline function and cannot be detected with #ifdef. If neither
 * running_regs nor CURRENT_REGS is available, we fall back to NULL rather
 * than risking a compile error. The dpatch callback already handles NULL
 * gracefully (logs error and returns).
 */

#ifndef __FPB_NUTTX_COMPAT_H
#define __FPB_NUTTX_COMPAT_H

#include <stddef.h>

/* Only apply compatibility for real NuttX builds (not host testing mocks) */
#if defined(__NuttX__) && !defined(FPB_HOST_TESTING_NUTTX)

#ifndef running_regs

/* running_regs() not available — try fallbacks */

#ifdef CURRENT_REGS
/* Oldest API: CURRENT_REGS macro (pre-April 2024 NuttX).
 * CURRENT_REGS is `volatile uint32_t *`, cast to void * for compatibility
 * with the running_regs() return type (FAR void **).
 * The caller (fpb_debugmon_nuttx.c) casts to uint32_t* anyway. */
#define running_regs() ((void*)CURRENT_REGS)

#else
/* Neither running_regs nor CURRENT_REGS is available.
 * This covers the intermediate period (April-Sept 2024) where only
 * up_current_regs() existed, and any future/exotic configurations.
 *
 * We define running_regs() as NULL rather than trying to call
 * up_current_regs() (which we can't detect with #ifdef). The dpatch
 * callback in fpb_debugmon_nuttx.c already handles NULL gracefully:
 *   if (!regs) { syslog(LOG_ERR, "no regs context\n"); return; }
 *
 * If users on the intermediate NuttX version need dpatch support,
 * they can manually define running_regs in their build flags:
 *   -Drunning_regs\(\)=up_current_regs\(\)
 */
#define running_regs() (NULL)
#define FPB_RUNNING_REGS_FALLBACK_NULL 1
#endif

#endif /* !running_regs */

#endif /* __NuttX__ && !FPB_HOST_TESTING_NUTTX */

#endif /* __FPB_NUTTX_COMPAT_H */
