/*
 * Mock NuttX cache.h for build testing
 */

#ifndef __NUTTX_CACHE_H
#define __NUTTX_CACHE_H

#include <stdint.h>

/* Mock cache flush function */
static inline void up_flush_dcache(uintptr_t start, uintptr_t end)
{
    (void)start;
    (void)end;
}

static inline void up_invalidate_dcache(uintptr_t start, uintptr_t end)
{
    (void)start;
    (void)end;
}

#endif /* __NUTTX_CACHE_H */
