/**
 * @file   umm_malloc_cfgport.h
 * @brief  UMM_MALLOC configuration for STM32 (Cortex-M3)
 */

#ifndef UMM_MALLOC_CFGPORT_H
#define UMM_MALLOC_CFGPORT_H

#include "stm32f10x.h" /* For CMSIS intrinsics */

/* Use best-fit algorithm for better memory utilization */
#define UMM_BEST_FIT

/* Enable heap info functions */
#define UMM_INFO

/* Critical section for Cortex-M3 (disable interrupts) */
// #define UMM_CRITICAL_DECL(tag)      uint32_t _saved_primask_##tag
// #define UMM_CRITICAL_ENTRY(tag)     do { _saved_primask_##tag = __get_PRIMASK(); __disable_irq(); } while(0)
// #define UMM_CRITICAL_EXIT(tag)      do { __set_PRIMASK(_saved_primask_##tag); } while(0)

#endif /* UMM_MALLOC_CFGPORT_H */
