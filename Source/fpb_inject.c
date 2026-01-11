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

/* FPB Base Address (Cortex-M3/M4) */
#define FPB_BASE 0xE0002000UL

/* FPB Control Register */
#define FPB_CTRL (*(volatile uint32_t*)(FPB_BASE + 0x000))

/* FPB Remap Register */
#define FPB_REMAP (*(volatile uint32_t*)(FPB_BASE + 0x004))

/* FPB Comparator Registers (0-7) */
#define FPB_COMP(n) (*(volatile uint32_t*)(FPB_BASE + 0x008 + ((n)*4)))

/* CTRL Register Bits */
#define FPB_CTRL_ENABLE (1UL << 0)
#define FPB_CTRL_KEY (1UL << 1)
#define FPB_CTRL_NUM_CODE_MASK (0xFUL << 4)
#define FPB_CTRL_NUM_LIT_MASK (0xFUL << 8)
#define FPB_CTRL_NUM_CODE_SHIFT 4
#define FPB_CTRL_NUM_LIT_SHIFT 8

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

/* Remap Table - stores jump instructions, must be 32-byte aligned */
__attribute__((aligned(32), section(".data"))) static uint32_t g_fpb_remap_table[FPB_REMAP_TABLE_SIZE * 2];

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

static inline void dsb(void) {
    __asm volatile("dsb" ::: "memory");
}

static inline void isb(void) {
    __asm volatile("isb" ::: "memory");
}

int fpb_init(void) {
    memset(&g_fpb_state, 0, sizeof(g_fpb_state));
    memset(g_fpb_remap_table, 0, sizeof(g_fpb_remap_table));

    uint32_t ctrl = FPB_CTRL;

    g_fpb_state.num_code_comp = (ctrl & FPB_CTRL_NUM_CODE_MASK) >> FPB_CTRL_NUM_CODE_SHIFT;
    g_fpb_state.num_lit_comp = (ctrl & FPB_CTRL_NUM_LIT_MASK) >> FPB_CTRL_NUM_LIT_SHIFT;

    if (g_fpb_state.num_code_comp == 0) {
        return -1;
    }

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

    return 0;
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

int fpb_set_patch(uint8_t comp_id, uint32_t original_addr, uint32_t patch_addr) {
    if (!g_fpb_state.initialized) {
        return -1;
    }

    if (comp_id >= g_fpb_state.num_code_comp) {
        return -1;
    }

    if (original_addr >= 0x20000000UL) {
        return -1;
    }

    original_addr &= ~1UL;
    patch_addr &= ~1UL;

    uint32_t remap_index = comp_id * 2;

    uint32_t jump_instr = generate_b_w_instruction(original_addr, patch_addr);

    g_fpb_remap_table[remap_index] = jump_instr;
    g_fpb_remap_table[remap_index + 1] = 0;

    FPB_REMAP = ((uint32_t)g_fpb_remap_table) & 0x1FFFFFE0UL;

    uint32_t comp_val = (original_addr & FPB_COMP_ADDR_MASK) | FPB_REPLACE_REMAP | FPB_COMP_ENABLE;

    FPB_COMP(comp_id) = comp_val;

    g_fpb_state.comp[comp_id].original_addr = original_addr;
    g_fpb_state.comp[comp_id].patch_addr = patch_addr;
    g_fpb_state.comp[comp_id].enabled = true;

    dsb();
    isb();

    return 0;
}

int fpb_clear_patch(uint8_t comp_id) {
    if (!g_fpb_state.initialized) {
        return -1;
    }

    if (comp_id >= g_fpb_state.num_code_comp) {
        return -1;
    }

    FPB_COMP(comp_id) = 0;

    uint32_t remap_index = comp_id * 2;
    g_fpb_remap_table[remap_index] = 0;
    g_fpb_remap_table[remap_index + 1] = 0;

    g_fpb_state.comp[comp_id].original_addr = 0;
    g_fpb_state.comp[comp_id].patch_addr = 0;
    g_fpb_state.comp[comp_id].enabled = false;

    dsb();
    isb();

    return 0;
}

int fpb_enable_comp(uint8_t comp_id, bool enable) {
    if (!g_fpb_state.initialized || comp_id >= g_fpb_state.num_code_comp) {
        return -1;
    }

    uint32_t comp_val = FPB_COMP(comp_id);

    if (enable) {
        comp_val |= FPB_COMP_ENABLE;
    } else {
        comp_val &= ~FPB_COMP_ENABLE;
    }

    FPB_COMP(comp_id) = comp_val;
    g_fpb_state.comp[comp_id].enabled = enable;

    dsb();
    isb();

    return 0;
}

const fpb_state_t* fpb_get_state(void) {
    return &g_fpb_state;
}

bool fpb_is_supported(void) {
    uint32_t ctrl = FPB_CTRL;
    uint8_t num_code = (ctrl & FPB_CTRL_NUM_CODE_MASK) >> FPB_CTRL_NUM_CODE_SHIFT;

    return (num_code > 0);
}

uint8_t fpb_get_num_code_comp(void) {
    return g_fpb_state.num_code_comp;
}

int fpb_set_instruction_patch(uint8_t comp_id, uint32_t addr, uint16_t new_instruction, bool is_upper) {
    if (!g_fpb_state.initialized || comp_id >= g_fpb_state.num_code_comp) {
        return -1;
    }

    addr &= ~3UL;

    if (addr >= 0x20000000UL) {
        return -1;
    }

    uint32_t remap_index = comp_id * 2;
    uint32_t replace_mode;

    if (is_upper) {
        replace_mode = FPB_REPLACE_UPPER;
        g_fpb_remap_table[remap_index] = (uint32_t)new_instruction << 16;
    } else {
        replace_mode = FPB_REPLACE_LOWER;
        g_fpb_remap_table[remap_index] = new_instruction;
    }

    FPB_REMAP = ((uint32_t)g_fpb_remap_table) & 0x1FFFFFE0UL;

    uint32_t comp_val = (addr & FPB_COMP_ADDR_MASK) | replace_mode | FPB_COMP_ENABLE;

    FPB_COMP(comp_id) = comp_val;

    g_fpb_state.comp[comp_id].original_addr = addr;
    g_fpb_state.comp[comp_id].patch_addr = new_instruction;
    g_fpb_state.comp[comp_id].enabled = true;

    dsb();
    isb();

    return 0;
}

uint8_t fpb_generate_thumb_jump(uint32_t from_addr, uint32_t to_addr, uint8_t* instruction) {
    int32_t offset = (int32_t)(to_addr - from_addr - 4);

    if (offset >= -2048 && offset <= 2046) {
        uint16_t imm11 = (offset >> 1) & 0x7FF;
        uint16_t instr = 0xE000 | imm11;

        instruction[0] = instr & 0xFF;
        instruction[1] = (instr >> 8) & 0xFF;

        return 2;
    } else {
        uint32_t instr = generate_b_w_instruction(from_addr, to_addr);

        instruction[0] = instr & 0xFF;
        instruction[1] = (instr >> 8) & 0xFF;
        instruction[2] = (instr >> 16) & 0xFF;
        instruction[3] = (instr >> 24) & 0xFF;

        return 4;
    }
}

void fpb_print_info(void) {
    /* Implementation depends on available print interface */
}
