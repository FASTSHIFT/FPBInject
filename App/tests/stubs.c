/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Stubs for unit testing - provides minimal implementations
 * of func_loader functions for host-based testing.
 *
 * This file provides stub implementations that simulate
 * the behavior of the real code without hardware dependencies.
 */

#include "mock_hardware.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ============================================================================
 * Type Definitions (matching func_loader.h)
 * ============================================================================ */

#define FL_MAX_SLOTS 6

typedef void (*fl_output_cb_t)(void* user, const char* str);
typedef void* (*fl_malloc_cb_t)(size_t size);
typedef void (*fl_free_cb_t)(void* ptr);

typedef struct {
    bool active;
    uint32_t orig_addr;
    uint32_t target_addr;
    uint32_t code_size;
    uintptr_t alloc_addr;
} fl_slot_state_t;

typedef struct fl_context_s {
    fl_output_cb_t output_cb;
    void* output_user;
    fl_malloc_cb_t malloc_cb;
    fl_free_cb_t free_cb;
    bool is_inited;
    uintptr_t last_alloc;
    size_t last_alloc_size;
    fl_slot_state_t slots[FL_MAX_SLOTS];
} fl_context_t;

/* Stream types */
#define FL_STREAM_BUF_SIZE 256

typedef struct {
    fl_context_t* ctx;
    char buf[FL_STREAM_BUF_SIZE];
    size_t buf_len;
} fl_stream_t;

/* Forward declarations */
int fl_stream_exec_line(fl_stream_t* s);

/* ============================================================================
 * func_loader Stub Implementations
 * ============================================================================ */

void fl_init_default(fl_context_t* ctx) {
    if (ctx) {
        memset(ctx, 0, sizeof(fl_context_t));
    }
}

void fl_init(fl_context_t* ctx) {
    if (!ctx)
        return;

    /* Clear all slots */
    for (int i = 0; i < FL_MAX_SLOTS; i++) {
        memset(&ctx->slots[i], 0, sizeof(fl_slot_state_t));
    }

    ctx->is_inited = true;
    ctx->last_alloc = 0;
    ctx->last_alloc_size = 0;
}

bool fl_is_inited(fl_context_t* ctx) {
    return ctx && ctx->is_inited;
}

static void fl_output(fl_context_t* ctx, const char* str) {
    if (ctx && ctx->output_cb) {
        ctx->output_cb(ctx->output_user, str);
    }
}

int fl_exec_cmd(fl_context_t* ctx, int argc, const char** argv) {
    if (!ctx || argc < 1 || !argv || !argv[0]) {
        return 0; /* Empty command OK */
    }

    const char* cmd = argv[0];

    if (strcmp(cmd, "help") == 0) {
        fl_output(ctx, "Usage: <command> [args...]\n");
        fl_output(ctx, "Commands: help, info, list, clear <slot>, clearall, meminfo\n");
        return 0;
    }

    if (strcmp(cmd, "info") == 0) {
        fl_output(ctx, "FPBInject Function Loader v1.0\n");
        return 0;
    }

    if (strcmp(cmd, "list") == 0) {
        fl_output(ctx, "Slot Status:\n");
        for (int i = 0; i < FL_MAX_SLOTS; i++) {
            char buf[64];
            snprintf(buf, sizeof(buf), "  Slot %d: %s\n", i, ctx->slots[i].active ? "active" : "empty");
            fl_output(ctx, buf);
        }
        return 0;
    }

    if (strcmp(cmd, "clear") == 0) {
        if (argc < 2) {
            fl_output(ctx, "Error: clear requires slot number\n");
            return -1;
        }
        int slot = atoi(argv[1]);
        if (slot < 0 || slot >= FL_MAX_SLOTS) {
            fl_output(ctx, "Error: Invalid slot number\n");
            return -1;
        }
        ctx->slots[slot].active = false;
        ctx->slots[slot].orig_addr = 0;
        ctx->slots[slot].target_addr = 0;
        ctx->slots[slot].code_size = 0;
        return 0;
    }

    if (strcmp(cmd, "clearall") == 0) {
        for (int i = 0; i < FL_MAX_SLOTS; i++) {
            ctx->slots[i].active = false;
            ctx->slots[i].orig_addr = 0;
            ctx->slots[i].target_addr = 0;
            ctx->slots[i].code_size = 0;
        }
        fl_output(ctx, "All slots cleared\n");
        return 0;
    }

    if (strcmp(cmd, "meminfo") == 0) {
        fl_output(ctx, "Memory info: heap OK\n");
        return 0;
    }

    fl_output(ctx, "Error: Unknown command\n");
    return -1;
}

/* ============================================================================
 * func_loader_stream Stub Implementations
 * ============================================================================ */

void fl_stream_init(fl_stream_t* s, fl_context_t* ctx) {
    if (!s)
        return;
    s->ctx = ctx;
    s->buf_len = 0;
    memset(s->buf, 0, FL_STREAM_BUF_SIZE);
}

int fl_stream_process(fl_stream_t* s, const char* data, size_t len) {
    if (!s || (!data && len > 0))
        return 0;

    for (size_t i = 0; i < len; i++) {
        char c = data[i];

        if (c == '\n' || c == '\r') {
            if (s->buf_len > 0) {
                s->buf[s->buf_len] = '\0';
                fl_stream_exec_line(s);
            }
            s->buf_len = 0;
        } else if (s->buf_len < FL_STREAM_BUF_SIZE - 1) {
            s->buf[s->buf_len++] = c;
        }
    }

    return 0;
}

int fl_stream_exec_line(fl_stream_t* s) {
    if (!s || !s->ctx)
        return 0;

    /* Parse line into argc/argv */
    char* line = s->buf;
    const char* argv[16];
    int argc = 0;

    /* Skip leading whitespace */
    while (*line == ' ' || *line == '\t')
        line++;

    /* Empty line */
    if (*line == '\0')
        return 0;

    /* Parse tokens */
    char* token = strtok(line, " \t");
    while (token && argc < 16) {
        argv[argc++] = token;
        token = strtok(NULL, " \t");
    }

    if (argc > 0) {
        return fl_exec_cmd(s->ctx, argc, argv);
    }

    return 0;
}

/* ============================================================================
 * fpb_inject Stub Implementations
 * ============================================================================ */

typedef struct {
    uint32_t original_addr;
    uint32_t patch_addr;
    bool enabled;
} fpb_comp_state_t;

typedef struct {
    bool initialized;
    uint8_t num_code_comp;
    uint8_t num_lit_comp;
    fpb_comp_state_t comp[6];
} fpb_state_t;

static fpb_state_t g_fpb_state;

int fpb_init(void) {
    memset(&g_fpb_state, 0, sizeof(g_fpb_state));
    g_fpb_state.initialized = true;
    g_fpb_state.num_code_comp = 6;
    g_fpb_state.num_lit_comp = 2;

    /* Set FPB registers */
    mock_fpb_regs.ctrl |= 0x03; /* ENABLE | KEY */

    return 0;
}

void fpb_deinit(void) {
    g_fpb_state.initialized = false;
    mock_fpb_regs.ctrl &= ~0x01; /* Clear ENABLE */

    for (int i = 0; i < 6; i++) {
        mock_fpb_regs.comp[i] = 0;
        g_fpb_state.comp[i].enabled = false;
    }
}

int fpb_set_patch(uint8_t comp_id, uint32_t original_addr, uint32_t patch_addr) {
    if (comp_id >= 6)
        return -1;
    if (original_addr >= 0x20000000)
        return -1; /* Must be in code region */

    g_fpb_state.comp[comp_id].original_addr = original_addr;
    g_fpb_state.comp[comp_id].patch_addr = patch_addr;
    g_fpb_state.comp[comp_id].enabled = true;

    /* Set comp register: address in bits 28:2, ENABLE in bit 0 */
    mock_fpb_regs.comp[comp_id] = (original_addr & 0x1FFFFFFC) | 0x01;

    return 0;
}

int fpb_clear_patch(uint8_t comp_id) {
    if (comp_id >= 6)
        return -1;

    g_fpb_state.comp[comp_id].enabled = false;
    g_fpb_state.comp[comp_id].original_addr = 0;
    g_fpb_state.comp[comp_id].patch_addr = 0;
    mock_fpb_regs.comp[comp_id] = 0;

    return 0;
}

int fpb_enable_comp(uint8_t comp_id, bool enable) {
    if (comp_id >= 6)
        return -1;

    g_fpb_state.comp[comp_id].enabled = enable;

    if (enable) {
        mock_fpb_regs.comp[comp_id] |= 0x01;
    } else {
        mock_fpb_regs.comp[comp_id] &= ~0x01;
    }

    return 0;
}

const fpb_state_t* fpb_get_state(void) {
    return &g_fpb_state;
}

bool fpb_is_supported(void) {
    return true;
}

uint8_t fpb_get_num_code_comp(void) {
    return g_fpb_state.num_code_comp;
}

void fpb_print_info(void) {
    /* No-op in stub */
}

int fpb_set_instruction_patch(uint8_t comp_id, uint32_t addr, uint16_t new_instruction, bool is_upper) {
    (void)new_instruction;
    (void)is_upper;

    if (comp_id >= 6)
        return -1;

    return fpb_set_patch(comp_id, addr, 0);
}

uint8_t fpb_generate_thumb_jump(uint32_t from_addr, uint32_t to_addr, uint8_t* instruction) {
    int32_t offset = (int32_t)(to_addr - from_addr - 4);

    /* Short branch if within range */
    if (offset >= -2048 && offset <= 2046) {
        uint16_t imm11 = (offset >> 1) & 0x7FF;
        uint16_t insn = 0xE000 | imm11;
        instruction[0] = insn & 0xFF;
        instruction[1] = (insn >> 8) & 0xFF;
        return 2;
    }

    /* Long branch (BL encoding) */
    int32_t s = (offset < 0) ? 1 : 0;
    uint32_t imm10 = (offset >> 12) & 0x3FF;
    uint32_t imm11 = (offset >> 1) & 0x7FF;
    uint32_t j1 = ((~(offset >> 23)) ^ s) & 1;
    uint32_t j2 = ((~(offset >> 22)) ^ s) & 1;

    uint16_t insn1 = 0xF000 | (s << 10) | imm10;
    uint16_t insn2 = 0x9000 | (j1 << 13) | (j2 << 11) | imm11;

    instruction[0] = insn1 & 0xFF;
    instruction[1] = (insn1 >> 8) & 0xFF;
    instruction[2] = insn2 & 0xFF;
    instruction[3] = (insn2 >> 8) & 0xFF;

    return 4;
}

/* ============================================================================
 * func_allocator Stub Implementations
 * ============================================================================ */

#define FUNC_ALLOC_BLOCK_SIZE 32
#define FUNC_ALLOC_MAX_BLOCKS 64

typedef struct {
    uint8_t* pool;
    size_t pool_size;
    size_t block_size;
    size_t num_blocks;
    uint64_t bitmap; /* Bit per block: 1=used, 0=free */
    size_t used_blocks;
} func_alloc_t;

static func_alloc_t g_func_allocator;
static uint8_t g_alloc_pool[FUNC_ALLOC_BLOCK_SIZE * FUNC_ALLOC_MAX_BLOCKS];

int func_alloc_init(func_alloc_t* a, uint8_t* pool, size_t pool_size, size_t block_size) {
    if (!a || !pool || pool_size == 0 || block_size == 0) {
        return -1;
    }

    a->pool = pool;
    a->pool_size = pool_size;
    a->block_size = block_size;
    a->num_blocks = pool_size / block_size;
    if (a->num_blocks > 64)
        a->num_blocks = 64;
    a->bitmap = 0;
    a->used_blocks = 0;

    return 0;
}

void* func_malloc(func_alloc_t* a, size_t size) {
    if (!a || size == 0)
        return NULL;

    size_t blocks_needed = (size + a->block_size - 1) / a->block_size;
    if (blocks_needed > a->num_blocks - a->used_blocks)
        return NULL;

    /* Find contiguous free blocks */
    for (size_t start = 0; start <= a->num_blocks - blocks_needed; start++) {
        bool found = true;
        for (size_t j = 0; j < blocks_needed; j++) {
            if (a->bitmap & (1ULL << (start + j))) {
                found = false;
                break;
            }
        }

        if (found) {
            /* Mark blocks as used */
            for (size_t j = 0; j < blocks_needed; j++) {
                a->bitmap |= (1ULL << (start + j));
            }
            a->used_blocks += blocks_needed;
            return a->pool + (start * a->block_size);
        }
    }

    return NULL;
}

void func_free(func_alloc_t* a, void* ptr, size_t size) {
    if (!a || !ptr || size == 0)
        return;
    if (ptr < (void*)a->pool || ptr >= (void*)(a->pool + a->pool_size))
        return;

    size_t offset = (uint8_t*)ptr - a->pool;
    size_t start = offset / a->block_size;
    size_t blocks = (size + a->block_size - 1) / a->block_size;

    for (size_t j = 0; j < blocks && (start + j) < a->num_blocks; j++) {
        if (a->bitmap & (1ULL << (start + j))) {
            a->bitmap &= ~(1ULL << (start + j));
            a->used_blocks--;
        }
    }
}

void func_alloc_stats(func_alloc_t* a, size_t* used, size_t* free_count, size_t* total) {
    if (!a)
        return;
    if (used)
        *used = a->used_blocks;
    if (free_count)
        *free_count = a->num_blocks - a->used_blocks;
    if (total)
        *total = a->num_blocks;
}

/* Global accessor for tests */
func_alloc_t* get_global_allocator(void) {
    static bool initialized = false;
    if (!initialized) {
        func_alloc_init(&g_func_allocator, g_alloc_pool, sizeof(g_alloc_pool), FUNC_ALLOC_BLOCK_SIZE);
        initialized = true;
    }
    return &g_func_allocator;
}
