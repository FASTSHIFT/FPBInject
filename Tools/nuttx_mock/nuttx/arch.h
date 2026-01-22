/*
 * Mock NuttX arch.h for build testing
 */

#ifndef __NUTTX_ARCH_H
#define __NUTTX_ARCH_H

#include <stdint.h>
#include <stddef.h>

/* Debugpoint types */
#define DEBUGPOINT_BREAKPOINT 1
#define DEBUGPOINT_STEPPOINT  2
#define DEBUGPOINT_WATCHPOINT_RO 3
#define DEBUGPOINT_WATCHPOINT_WO 4
#define DEBUGPOINT_WATCHPOINT_RW 5

/* Debugpoint callback type */
typedef void (*debug_callback_t)(int type, void* addr, size_t size, void* arg);

/* Mock NuttX debugpoint API */
static inline int up_debugpoint_add(int type, void* addr, size_t size,
                                    debug_callback_t callback, void* arg)
{
    (void)type;
    (void)addr;
    (void)size;
    (void)callback;
    (void)arg;
    return 0;
}

static inline int up_debugpoint_remove(int type, void* addr, size_t size)
{
    (void)type;
    (void)addr;
    (void)size;
    return 0;
}

#endif /* __NUTTX_ARCH_H */
