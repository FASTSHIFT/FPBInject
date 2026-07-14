/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Scenario 3: Intermediate NuttX (April-Sept 2024) with manual override
 *
 * In this period, neither CURRENT_REGS nor running_regs() exists — only
 * up_current_regs() as a static inline. The compat header does NOT define
 * a fallback (to avoid silent NULL). Users must manually add:
 *   -Drunning_regs()=up_current_regs()
 *
 * This test simulates that manual override: running_regs() is defined
 * before including the compat header, and CURRENT_REGS is NOT defined.
 * The compat header should leave it untouched.
 */

#include <stdint.h>

/* Simulate __NuttX__ being defined */
#define __NuttX__

/* Simulate user manual override for intermediate NuttX */
static uint32_t s_scenario3_regs[16] = {0};
#define running_regs() ((void*)s_scenario3_regs)

/* CURRENT_REGS is NOT defined. The compat header sees no CURRENT_REGS,
 * so it enters the #else branch — but running_regs() is already defined
 * by the user, so the header's #define would be a redefinition warning.
 * In practice, the header's #else branch does NOT define running_regs(),
 * so there's no conflict. */
#include "fpb_nuttx_compat.h"

uint32_t scenario3_get_pc(void) {
    s_scenario3_regs[6] = 0x12345678; /* REG_PC */
    uint32_t* regs = (uint32_t*)running_regs();
    return regs[6];
}

int scenario3_fallback_null_defined(void) {
    /* FPB_RUNNING_REGS_FALLBACK_NULL is no longer defined by the compat
     * header. Return 0 to indicate no NULL fallback. */
    return 0;
}
