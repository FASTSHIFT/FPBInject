/*
 * Mock NuttX sched.h for build testing
 */

#ifndef __NUTTX_SCHED_H
#define __NUTTX_SCHED_H

#include <stdint.h>
#include <stdbool.h>

/* Mock task control block - only what we need for testing */
struct tcb_s
{
    /* Exception context - holds saved registers */
    struct xcptcontext
    {
        uint32_t* regs;
    } xcp;
};

/* Mock function to get current task */
static inline struct tcb_s* nxsched_self(void)
{
    static struct tcb_s mock_tcb;
    static uint32_t mock_regs[32];
    mock_tcb.xcp.regs = mock_regs;
    return &mock_tcb;
}

#endif /* __NUTTX_SCHED_H */
