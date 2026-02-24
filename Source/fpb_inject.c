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
 * @file   fpb_inject.c
 * @brief  Cortex-M3/M4 Flash Patch and Breakpoint (FPB) Unit Driver Implementation
 *
 * FPB Operating Principle:
 * 1. FPB hardware monitors CPU instruction fetch addresses
 * 2. When address matches comparator-configured address, FPB intercepts
 * 3. FPB can return replacement instruction or fetch from remap region
 *
 * This implementation uses REMAP method because:
 * - More flexible for various patch scenarios
 * - Works well with Cortex-M3 FPB_REV1
 * - Allows 32-bit instruction replacement
 */

#include "fpb_inject.h"
#include <string.h>

#ifdef FPB_HOST_TESTING
/* Use mock registers for host-based testing */
#include "fpb_mock_regs.h"
#else
/* FPB Base Address (Cortex-M3/M4) */
#define FPB_BASE 0xE0002000UL

/* FPB Control Register */
#define FPB_CTRL (*(volatile uint32_t*)(FPB_BASE + 0x000))

/* FPB Remap Register */
#define FPB_REMAP (*(volatile uint32_t*)(FPB_BASE + 0x004))

/* FPB Comparator Registers (0-7) */
#define FPB_COMP(n) (*(volatile uint32_t*)(FPB_BASE + 0x008 + ((n)*4)))
#endif /* FPB_HOST_TESTING */

/* CTRL Register Bits */
#define FPB_CTRL_ENABLE (1UL << 0)
#define FPB_CTRL_KEY (1UL << 1)

/* COMP Register Bits */
#define FPB_COMP_ENABLE (1UL << 0)
#define FPB_COMP_ADDR_MASK 0x1FFFFFFCUL

/* Replacement Modes */
#define FPB_REPLACE_REMAP (0UL << 30)
#define FPB_REPLACE_LOWER (1UL << 30)
#define FPB_REPLACE_UPPER (2UL << 30)
#define FPB_REPLACE_BOTH (3UL << 30)

/* Remap table size */
#define FPB_REMAP_TABLE_SIZE FPB_MAX_CODE_COMP

/* FPB Global State */
static fpb_state_t g_fpb_state;

/* Remap Table - stores jump instructions, must be 32-byte aligned
 *
 * ARM FPB Remap mechanism:
 *   - Comparator n remaps to address (Remap_Base + 4*n)
 *   - Each remap table entry is 32 bits (one word)
 *   - remap_table[0] is for Comparator 0
 *   - remap_table[1] is for Comparator 1
 *   - etc.
 *
 * Each entry stores a 32-bit B.W (branch) instruction that jumps
 * to the actual patch target in RAM.
 */
#ifdef FPB_HOST_TESTING
static uint32_t g_fpb_remap_table[FPB_REMAP_TABLE_SIZE];
#else
__attribute__((aligned(32), section(".data"))) static uint32_t g_fpb_remap_table[FPB_REMAP_TABLE_SIZE];
#endif

/**
 * @brief Generate Thumb-2 B.W instruction (unconditional branch)
 */
static uint32_t generate_b_w_instruction(uint32_t from_addr, uint32_t target_addr) {
    /*
     * Thumb-2 B.W instruction format:
     * First halfword: 11110 S imm10
     * Second halfword: 10 J1 0 J2 imm11
     */
    int32_t offset = (int32_t)(target_addr - from_addr - 4);

    uint32_t s = (offset < 0) ? 1 : 0;
    uint32_t imm10 = (offset >> 12) & 0x3FF;
    uint32_t imm11 = (offset >> 1) & 0x7FF;

    uint32_t i1 = ((offset >> 23) & 1) ^ s ^ 1;
    uint32_t i2 = ((offset >> 22) & 1) ^ s ^ 1;
    uint32_t j1 = i1;
    uint32_t j2 = i2;

    uint16_t hw1 = 0xF000 | (s << 10) | imm10;
    uint16_t hw2 = 0x9000 | (j1 << 13) | (j2 << 11) | imm11;

    return ((uint32_t)hw2 << 16) | hw1;
}

#ifndef FPB_HOST_TESTING
static inline void dsb(void) {
    __asm volatile("dsb" ::: "memory");
}

static inline void isb(void) {
    __asm volatile("isb" ::: "memory");
}
#endif /* !FPB_HOST_TESTING */

fpb_result_t fpb_init(void) {
    /* If already initialized, return success (idempotent) */
    if (g_fpb_state.initialized) {
        return FPB_OK;
    }

    memset(&g_fpb_state, 0, sizeof(g_fpb_state));
    memset(g_fpb_remap_table, 0, sizeof(g_fpb_remap_table));

    /* Use fpb_get_info to parse FPB hardware configuration */
    fpb_info_t info;
    if (fpb_get_info(&info) != FPB_OK) {
        return FPB_ERR_NOT_SUPPORTED;
    }

    g_fpb_state.num_code_comp = info.num_code_comp;
    g_fpb_state.num_lit_comp = info.num_lit_comp;

    if (g_fpb_state.num_code_comp > FPB_MAX_CODE_COMP) {
        g_fpb_state.num_code_comp = FPB_MAX_CODE_COMP;
    }

    for (uint8_t i = 0; i < FPB_MAX_COMP; i++) {
        FPB_COMP(i) = 0;
    }

    FPB_CTRL = FPB_CTRL_KEY | FPB_CTRL_ENABLE;

    dsb();
    isb();

    g_fpb_state.initialized = true;

    return FPB_OK;
}

void fpb_deinit(void) {
    for (uint8_t i = 0; i < FPB_MAX_COMP; i++) {
        FPB_COMP(i) = 0;
    }

    FPB_CTRL = FPB_CTRL_KEY;

    memset(&g_fpb_state, 0, sizeof(g_fpb_state));

    dsb();
    isb();
}

fpb_result_t fpb_set_patch(uint8_t comp_id, uint32_t original_addr, uint32_t patch_addr) {
    if (!g_fpb_state.initialized) {
        return FPB_ERR_NOT_INIT;
    }

    if (comp_id >= g_fpb_state.num_code_comp) {
        return FPB_ERR_INVALID_COMP;
    }

    if (original_addr >= 0x20000000UL) {
        return FPB_ERR_INVALID_ADDR;
    }

    original_addr &= ~1UL;
    patch_addr &= ~1UL;

    /*
     * FPB on Cortex-M3 has limited REMAP capability - it can only remap to
     * addresses in the Code region (0x00000000-0x1FFFFFFF).
     *
     * Since we need to jump to RAM (0x20000000+), we use a different approach:
     * 1. Store a B.W (branch) instruction in the remap table
     * 2. Use FPB REPLACE mode to substitute the original instruction
     *
     * However, FPB REPLACE modes (LOWER/UPPER/BOTH) only provide 16-bit
     * replacement values, which is not enough for a full 32-bit B.W instruction.
     *
     * Alternative approach: Use FPB to replace with BL to a trampoline in low RAM
     * or use software patching if the target is in writable memory.
     *
     * For now, we'll use a workaround:
     * - Generate a 32-bit B.W instruction
     * - Place it in remap table at proper offset
     * - Configure FPB to fetch from remap region
     *
     * Note: The remap table must be in the Code region (< 0x20000000).
     * Since we can't put it there, we'll use instruction replacement mode
     * with a LDR PC sequence.
     */

    /*
     * New approach: Use REPLACE_BOTH mode to inject a 32-bit instruction
     * that loads PC from a literal pool.
     *
     * We'll inject: LDR PC, [PC, #offset] pattern
     * But this is complex. Instead, let's use the simplest approach:
     *
     * For short jumps (within ±16MB), use B.W instruction directly.
     * The REPLACE_BOTH mode writes a 32-bit value at the matched address.
     */

    /* Generate B.W instruction for the jump */
    uint32_t jump_instr = generate_b_w_instruction(original_addr, patch_addr);

    /*
     * FPB Remap mechanism (ARM DDI 0403E C1.11):
     *
     * "Comparator n remaps to address (Remap_Base + 4n)"
     *
     * So the remap table layout must be:
     *   - remap_table[0] = instruction for Comparator 0
     *   - remap_table[1] = instruction for Comparator 1
     *   - remap_table[n] = instruction for Comparator n
     *
     * Each entry is exactly one 32-bit word (4 bytes).
     *
     * FP_REMAP register:
     *   - bits[28:5] hold the base address bits[28:5]
     *   - bits[31:29] are hardwired to 0b001 (SRAM region)
     *   - So actual remap address = 0x20000000 | (FP_REMAP & 0x1FFFFFE0)
     */

    /* Store jump instruction at correct index for this comparator */
    g_fpb_remap_table[comp_id] = jump_instr;

    /* Set remap base - bits[28:5] of the table address */
    uint32_t remap_base = (uint32_t)(uintptr_t)g_fpb_remap_table;
    /* FP_REMAP stores bits[28:5], bits[31:29] are hardwired to 0b001 (SRAM) */
    FPB_REMAP = remap_base & 0x1FFFFFE0UL;

    /* Configure comparator for REMAP mode (REPLACE=00) */
    uint32_t comp_val = (original_addr & FPB_COMP_ADDR_MASK) | FPB_REPLACE_REMAP | FPB_COMP_ENABLE;
    FPB_COMP(comp_id) = comp_val;

    g_fpb_state.comp[comp_id].original_addr = original_addr;
    g_fpb_state.comp[comp_id].patch_addr = patch_addr;
    g_fpb_state.comp[comp_id].enabled = true;

    dsb();
    isb();

    return FPB_OK;
}

fpb_result_t fpb_clear_patch(uint8_t comp_id) {
    if (!g_fpb_state.initialized) {
        return FPB_ERR_NOT_INIT;
    }

    if (comp_id >= g_fpb_state.num_code_comp) {
        return FPB_ERR_INVALID_COMP;
    }

    FPB_COMP(comp_id) = 0;

    /* Clear remap table entry */
    g_fpb_remap_table[comp_id] = 0;

    g_fpb_state.comp[comp_id].original_addr = 0;
    g_fpb_state.comp[comp_id].patch_addr = 0;
    g_fpb_state.comp[comp_id].enabled = false;

    dsb();
    isb();

    return FPB_OK;
}

const fpb_state_t* fpb_get_state(void) {
    return &g_fpb_state;
}

fpb_result_t fpb_get_info(fpb_info_t* info) {
    if (!info) {
        return FPB_ERR_INVALID_PARAM;
    }

    memset(info, 0, sizeof(fpb_info_t));

    uint32_t ctrl = FPB_CTRL;

    /* Extract FP_CTRL register fields */
    uint8_t rev = (ctrl >> 28) & 0xF;
    uint8_t num_code_low = (ctrl >> 4) & 0xF;
    uint8_t num_code_high = (ctrl >> 12) & 0x7;
    uint8_t num_lit = (ctrl >> 8) & 0xF;
    bool enabled = (ctrl & 0x1) != 0;

    /* Combine NUM_CODE bits [6:4] and [3:0] */
    uint8_t num_code = num_code_low | (num_code_high << 4);

    /* Check if FPB is supported */
    if (num_code == 0) {
        return FPB_ERR_NOT_SUPPORTED;
    }

    /* Fill FP_CTRL fields */
    info->rev = rev;
    info->num_code_comp = num_code;
    info->num_lit_comp = num_lit;
    info->enabled = enabled;
    info->total_comp = num_code + num_lit;

    /* Fill FP_REMAP fields */
    uint32_t remap = FPB_REMAP;
    info->remap_raw = remap;
    info->remap_supported = (remap >> 29) & 0x1;
    /* Compute actual remap base: bits[31:29] = 0b001 (SRAM), bits[28:5] from REMAP, bits[4:0] = 0 */
    info->remap_base = 0x20000000UL | (remap & 0x1FFFFFE0UL);

    /* Fill FP_COMPn fields for code comparators */
    uint8_t comp_count = (num_code <= FPB_MAX_CODE_COMP) ? num_code : FPB_MAX_CODE_COMP;
    for (uint8_t i = 0; i < comp_count; i++) {
        uint32_t comp = FPB_COMP(i);
        info->comp[i].comp_raw = comp;
        info->comp[i].enabled = (comp & 0x1) != 0;

        if (rev == 0) {
            /* FPB v1: REPLACE in bits[31:30], COMP in bits[28:2] */
            info->comp[i].replace = (comp >> 30) & 0x3;
            info->comp[i].match_addr = comp & 0x1FFFFFFCUL;
        } else {
            /* FPB v2: different layout, simplified here */
            info->comp[i].replace = 0; /* v2 uses different mechanism */
            info->comp[i].match_addr = comp & 0xFFFFFFFEUL;
        }
    }

    return FPB_OK;
}

/**
 * @brief Get remap table base address for testing/debugging
 * @return Pointer to remap table (FPB_MAX_CODE_COMP entries)
 */
const uint32_t* fpb_test_get_remap_table(void) {
    return g_fpb_remap_table;
}
