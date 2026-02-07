/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

/**
 * @file   fpb_inject.h
 * @brief  Cortex-M3/M4 Flash Patch and Breakpoint (FPB) Unit Driver
 *
 * FPB is a debug component in ARM Cortex-M processors that can:
 * 1. Set hardware breakpoints
 * 2. Remap Flash instructions to SRAM (code injection)
 *
 * This module implements runtime code injection functionality,
 * allowing instruction replacement at specified addresses without
 * modifying Flash memory - enabling hot-patching capabilities.
 *
 * Hardware Features (STM32F103 - Cortex-M3):
 * - 6 instruction comparators (FP_COMP0 - FP_COMP5) for code remapping
 * - 2 literal comparators (FP_COMP6 - FP_COMP7) for data remapping
 * - Supports Thumb instruction remapping
 */

#ifndef __FPB_INJECT_H
#define __FPB_INJECT_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>

/* Maximum code comparator count (STM32F103 Cortex-M3) */
#define FPB_MAX_CODE_COMP 6

/* Maximum literal comparator count */
#define FPB_MAX_LIT_COMP 2

/* Total comparator count */
#define FPB_MAX_COMP (FPB_MAX_CODE_COMP + FPB_MAX_LIT_COMP)

/**
 * @brief FPB Comparator State
 */
typedef struct {
    uint32_t original_addr;
    uint32_t patch_addr;
    bool enabled;
} fpb_comp_state_t;

/**
 * @brief FPB Global State
 */
typedef struct {
    bool initialized;
    uint8_t num_code_comp;
    uint8_t num_lit_comp;
    fpb_comp_state_t comp[FPB_MAX_CODE_COMP];
} fpb_state_t;

/**
 * @brief FPB Comparator Information
 */
typedef struct {
    uint32_t comp_raw;   /* Raw FP_COMPn register value */
    uint32_t match_addr; /* Address being matched (bits[28:2] << 2) */
    uint8_t replace;     /* REPLACE field (v1 only): 0=remap, 1=bp_lower, 2=bp_upper, 3=bp_both */
    bool enabled;        /* Comparator enabled */
} fpb_comp_info_t;

/**
 * @brief FPB Device Information (from FP_CTRL, FP_REMAP, FP_COMPn registers)
 */
typedef struct {
    /* FP_CTRL fields */
    uint8_t rev;           /* Flash Patch revision (0=v1, 1=v2) */
    uint8_t num_code_comp; /* Number of instruction address comparators */
    uint8_t num_lit_comp;  /* Number of literal address comparators */
    uint8_t total_comp;    /* Total comparators (num_code_comp + num_lit_comp) */
    bool enabled;          /* FPB global enable status */

    /* FP_REMAP fields */
    uint32_t remap_raw;   /* Raw FP_REMAP register value */
    uint32_t remap_base;  /* Computed remap base address (in SRAM region) */
    bool remap_supported; /* RMPSPT bit: true if remap is supported */

    /* FP_COMPn fields (up to FPB_MAX_CODE_COMP entries) */
    fpb_comp_info_t comp[FPB_MAX_CODE_COMP];
} fpb_info_t;

/**
 * @brief  Initialize FPB unit
 * @retval 0: Success, -1: Failure
 */
int fpb_init(void);

/**
 * @brief  Deinitialize FPB unit
 */
void fpb_deinit(void);

/**
 * @brief  Set code patch
 * @param  comp_id: Comparator ID (0 ~ FPB_MAX_CODE_COMP-1)
 * @param  original_addr: Original function address (must be in Code region: 0x00000000 - 0x1FFFFFFF)
 * @param  patch_addr: Patch function address
 * @retval 0: Success, -1: Invalid parameter, -2: Comparator unavailable
 */
int fpb_set_patch(uint8_t comp_id, uint32_t original_addr, uint32_t patch_addr);

/**
 * @brief  Clear code patch
 * @param  comp_id: Comparator ID
 * @retval 0: Success, -1: Invalid parameter
 */
int fpb_clear_patch(uint8_t comp_id);

/**
 * @brief  Enable/disable specified comparator
 * @param  comp_id: Comparator ID
 * @param  enable: true-enable, false-disable
 * @retval 0: Success, -1: Invalid parameter
 */
int fpb_enable_comp(uint8_t comp_id, bool enable);

/**
 * @brief  Get FPB state information
 * @return Pointer to FPB state structure
 */
const fpb_state_t* fpb_get_state(void);

/**
 * @brief  Check if FPB is supported
 * @retval true: Supported, false: Not supported
 */
bool fpb_is_supported(void);

/**
 * @brief  Get available code comparator count
 * @return Available comparator count
 */
uint8_t fpb_get_num_code_comp(void);

/**
 * @brief  Get detailed FPB device information
 * @param  info: Pointer to fpb_info_t structure to fill
 * @retval 0: Success, -1: FPB not supported or invalid parameter
 *
 * This function reads all FPB registers and populates the info structure:
 * - FP_CTRL: revision, comparator counts, global enable
 * - FP_REMAP: remap base address, remap support flag
 * - FP_COMPn: each comparator's match address, mode, and enable status
 */
int fpb_get_info(fpb_info_t* info);

/**
 * @brief  Set instruction-level patch (replace single Thumb instruction)
 * @param  comp_id: Comparator ID
 * @param  addr: Instruction address (2-byte aligned)
 * @param  new_instruction: New Thumb instruction (16-bit)
 * @param  is_upper: true-replace upper halfword, false-replace lower halfword
 * @retval 0: Success, -1: Failure
 */
int fpb_set_instruction_patch(uint8_t comp_id, uint32_t addr, uint16_t new_instruction, bool is_upper);

/**
 * @brief  Generate Thumb branch instruction
 * @param  from_addr: Branch source address
 * @param  to_addr: Branch target address
 * @param  instruction: Output instruction buffer (at least 4 bytes)
 * @return Instruction length (2 or 4 bytes)
 */
uint8_t fpb_generate_thumb_jump(uint32_t from_addr, uint32_t to_addr, uint8_t* instruction);

/**
 * @brief Get remap table base address for testing/debugging
 * @return Pointer to remap table (FPB_MAX_CODE_COMP entries)
 */
const uint32_t* fpb_test_get_remap_table(void);

#ifdef __cplusplus
}
#endif

#endif /* __FPB_INJECT_H */
