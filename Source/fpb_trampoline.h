/**
 * @file   fpb_trampoline.h
 * @brief  Trampoline functions for FPB injection
 *
 * Configuration macros:
 *   FPB_NO_TRAMPOLINE    - Disable trampoline (for cores that can REMAP to RAM)
 *   FPB_TRAMPOLINE_NO_ASM - Use C instead of assembly (no argument preservation)
 */

#ifndef __FPB_TRAMPOLINE_H
#define __FPB_TRAMPOLINE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FPB_TRAMPOLINE_COUNT  6  /* Number of available trampolines (STM32F103) */

#ifndef FPB_NO_TRAMPOLINE

/**
 * @brief  Set trampoline target for a specific comparator
 * @param  comp: Comparator index (0-5)
 * @param  target: Target address (with Thumb bit set)
 */
void fpb_trampoline_set_target(uint32_t comp, uint32_t target);

/**
 * @brief  Clear trampoline target
 * @param  comp: Comparator index (0-5)
 */
void fpb_trampoline_clear_target(uint32_t comp);

/**
 * @brief  Get trampoline function address for a comparator
 * @param  comp: Comparator index (0-5)
 * @return Trampoline function address (with Thumb bit)
 */
uint32_t fpb_trampoline_get_address(uint32_t comp);

#else /* FPB_NO_TRAMPOLINE */

/* Stub functions when trampoline is disabled */
static inline void fpb_trampoline_set_target(uint32_t comp, uint32_t target) { (void)comp; (void)target; }
static inline void fpb_trampoline_clear_target(uint32_t comp) { (void)comp; }
static inline uint32_t fpb_trampoline_get_address(uint32_t comp) { (void)comp; return 0; }

#endif /* FPB_NO_TRAMPOLINE */

#ifdef __cplusplus
}
#endif

#endif /* __FPB_TRAMPOLINE_H */
