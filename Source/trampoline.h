/**
 * @file   trampoline.h
 * @brief  Trampoline functions for FPB injection
 */

#ifndef __TRAMPOLINE_H
#define __TRAMPOLINE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRAMPOLINE_COUNT  6  /* Number of available trampolines */

/**
 * @brief  Set trampoline target for a specific comparator
 * @param  comp: Comparator index (0-5)
 * @param  target: Target address (with Thumb bit set)
 */
void trampoline_set_target(uint32_t comp, uint32_t target);

/**
 * @brief  Clear trampoline target
 * @param  comp: Comparator index (0-5)
 */
void trampoline_clear_target(uint32_t comp);

/**
 * @brief  Get trampoline function address for a comparator
 * @param  comp: Comparator index (0-5)
 * @return Trampoline function address (with Thumb bit)
 */
uint32_t trampoline_get_address(uint32_t comp);

#ifdef __cplusplus
}
#endif

#endif /* __TRAMPOLINE_H */
