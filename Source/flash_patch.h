/**
 * @file   flash_patch.h
 * @brief  Flash programming for runtime code patching
 */

#ifndef FLASH_PATCH_H
#define FLASH_PATCH_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief  Patch a function in Flash to jump to a new address
 * @param  original_addr: Address of the original function (in Flash)
 * @param  target_addr: Address to jump to (can be in RAM)
 * @return 0 on success, negative on error
 *         -1: Invalid address
 *         -2: Erase failed
 *         -3: Program failed
 */
int flash_patch_function(uint32_t original_addr, uint32_t target_addr);

/**
 * @brief  Get the original instruction at an address
 * @param  addr: Address to read
 * @return 32-bit value at the address
 */
uint32_t flash_read_instruction(uint32_t addr);

#ifdef __cplusplus
}
#endif

#endif /* FLASH_PATCH_H */
