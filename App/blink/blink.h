/**
 * @file   blink.h
 * @brief  LED blink demo module + FPB injection example
 */

#ifndef __BLINK_H
#define __BLINK_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/**
 * @brief Initialize blink module
 */
void blink_init(void);

/**
 * @brief Blink main loop
 */
void blink_loop(void);

/**
 * @brief Run blink demo (called from main)
 */
void blink_run(void);

#ifdef __cplusplus
}
#endif

#endif /* __BLINK_H */
