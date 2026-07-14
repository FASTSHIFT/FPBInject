/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Scenario 3: Neither running_regs nor CURRENT_REGS defined (intermediate)
 *
 * Simulates an intermediate NuttX version (2024-04 ~ 2024-09) where
 * up_current_regs() exists as a static inline function but neither
 * running_regs nor CURRENT_REGS is available as a macro.
 * The compat header should define running_regs() as NULL and set
 * FPB_RUNNING_REGS_FALLBACK_NULL.
 */

#include <stdint.h>

/* Simulate __NuttX__ being defined */
#define __NuttX__

/* Neither running_regs nor CURRENT_REGS is defined */
#include "fpb_nuttx_compat.h"

uint32_t scenario3_get_pc(void) {
    /* running_regs() should return NULL */
    uint32_t* regs = (uint32_t*)running_regs();
    if (!regs) {
        return 0;
    }
    return regs[6];
}

int scenario3_fallback_null_defined(void) {
#ifdef FPB_RUNNING_REGS_FALLBACK_NULL
    return 1;
#else
    return 0;
#endif
}
