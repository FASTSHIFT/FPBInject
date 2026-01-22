/*
 * Mock arch/irq.h for build testing
 */

#ifndef __ARCH_IRQ_H
#define __ARCH_IRQ_H

#include <stdint.h>

/* IRQ related register offsets - Cortex-M style */
#define REG_R0    0
#define REG_R1    1
#define REG_R2    2
#define REG_R3    3
#define REG_R12   4
#define REG_R14   5  /* LR */
#define REG_R15   6  /* PC */
#define REG_XPSR  7

/* Alias for PC register */
#define REG_PC    REG_R15

/* Mock running_regs function - returns current task's register context */
static inline uint32_t* running_regs(void)
{
    static uint32_t mock_regs[32];
    return mock_regs;
}

#endif /* __ARCH_IRQ_H */
