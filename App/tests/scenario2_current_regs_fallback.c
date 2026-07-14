/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Scenario 2: CURRENT_REGS defined (old NuttX < 2024-04)
 *
 * Simulates an old NuttX environment where CURRENT_REGS macro exists
 * but running_regs() does not. The compat header should map
 * running_regs() to CURRENT_REGS.
 */

#include <stdint.h>

/* Simulate __NuttX__ being defined */
#define __NuttX__

/* Simulate CURRENT_REGS from old NuttX arch/arm/include/irq.h */
static uint32_t s_scenario2_regs[16] = {0};
#define CURRENT_REGS (s_scenario2_regs)

/* running_regs is NOT defined — compat header should create it */
#include "fpb_nuttx_compat.h"

uint32_t scenario2_get_pc(void) {
    s_scenario2_regs[6] = 0xCAFEBABE; /* REG_PC */
    uint32_t* regs = (uint32_t*)running_regs();
    return regs[6];
}

int scenario2_fallback_null_defined(void) {
#ifdef FPB_RUNNING_REGS_FALLBACK_NULL
    return 1;
#else
    return 0;
#endif
}
