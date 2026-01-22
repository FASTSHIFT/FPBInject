/*
 * Mock NuttX irq.h for build testing
 */

#ifndef __NUTTX_IRQ_H
#define __NUTTX_IRQ_H

#include <stdint.h>

typedef int (*xcpt_t)(int irq, void* context, void* arg);

/* Mock IRQ functions */
static inline int irq_attach(int irq, xcpt_t handler, void* arg)
{
    (void)irq;
    (void)handler;
    (void)arg;
    return 0;
}

static inline void up_enable_irq(int irq)
{
    (void)irq;
}

static inline void up_disable_irq(int irq)
{
    (void)irq;
}

#endif /* __NUTTX_IRQ_H */
