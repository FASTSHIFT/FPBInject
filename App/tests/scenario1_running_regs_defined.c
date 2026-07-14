/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Scenario 1: running_regs already defined (modern NuttX >= 2024-09)
 *
 * Simulates a modern NuttX environment where running_regs() is already
 * defined by nuttx/sched.h. The compat header should NOT redefine it.
 */

#include <stdint.h>

/* Simulate __NuttX__ being defined */
#define __NuttX__

/* Simulate modern NuttX: CURRENT_REGS is NOT defined, running_regs() is
 * already provided by nuttx/sched.h. Define it here to simulate that. */
static uint32_t s_scenario1_regs[16] = {0};
#define running_regs() ((void*)s_scenario1_regs)

/* Now include the compat header — CURRENT_REGS is not defined, so it
 * should NOT redefine running_regs() */
#include "fpb_nuttx_compat.h"

uint32_t scenario1_get_pc(void) {
    s_scenario1_regs[6] = 0xDEADBEEF; /* REG_PC */
    uint32_t* regs = (uint32_t*)running_regs();
    return regs[6];
}

int scenario1_fallback_null_defined(void) {
#ifdef FPB_RUNNING_REGS_FALLBACK_NULL
    return 1;
#else
    return 0;
#endif
}
