/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Stub declarations for unit testing
 */

#ifndef __STUBS_H
#define __STUBS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================================
 * func_loader Types and Functions
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

void fl_init_default(fl_context_t* ctx);
void fl_init(fl_context_t* ctx);
bool fl_is_inited(fl_context_t* ctx);
int fl_exec_cmd(fl_context_t* ctx, int argc, const char** argv);

/* ============================================================================
 * func_loader_stream Types and Functions
 * ============================================================================ */

#define FL_STREAM_BUF_SIZE 256

typedef struct {
    fl_context_t* ctx;
    char buf[FL_STREAM_BUF_SIZE];
    size_t buf_len;
} fl_stream_t;

void fl_stream_init(fl_stream_t* s, fl_context_t* ctx);
int fl_stream_process(fl_stream_t* s, const char* data, size_t len);
int fl_stream_exec_line(fl_stream_t* s);

/* ============================================================================
 * fpb_inject Types and Functions
 * ============================================================================ */

#define FPB_MAX_CODE_COMP 6
#define FPB_MAX_LIT_COMP 2
#define FPB_MAX_COMP (FPB_MAX_CODE_COMP + FPB_MAX_LIT_COMP)

typedef struct {
    uint32_t original_addr;
    uint32_t patch_addr;
    bool enabled;
} fpb_comp_state_t;

typedef struct {
    bool initialized;
    uint8_t num_code_comp;
    uint8_t num_lit_comp;
    fpb_comp_state_t comp[FPB_MAX_CODE_COMP];
} fpb_state_t;

int fpb_init(void);
void fpb_deinit(void);
int fpb_set_patch(uint8_t comp_id, uint32_t original_addr, uint32_t patch_addr);
int fpb_clear_patch(uint8_t comp_id);
int fpb_enable_comp(uint8_t comp_id, bool enable);
const fpb_state_t* fpb_get_state(void);
bool fpb_is_supported(void);
uint8_t fpb_get_num_code_comp(void);
void fpb_print_info(void);
int fpb_set_instruction_patch(uint8_t comp_id, uint32_t addr, uint16_t new_instruction, bool is_upper);
uint8_t fpb_generate_thumb_jump(uint32_t from_addr, uint32_t to_addr, uint8_t* instruction);

/* ============================================================================
 * func_allocator Types and Functions
 * ============================================================================ */

typedef struct {
    uint8_t* pool;
    size_t pool_size;
    size_t block_size;
    size_t num_blocks;
    uint64_t bitmap;
    size_t used_blocks;
} func_alloc_t;

int func_alloc_init(func_alloc_t* a, uint8_t* pool, size_t pool_size, size_t block_size);
void* func_malloc(func_alloc_t* a, size_t size);
void func_free(func_alloc_t* a, void* ptr, size_t size);
void func_alloc_stats(func_alloc_t* a, size_t* used, size_t* free_count, size_t* total);
func_alloc_t* get_global_allocator(void);

#ifdef __cplusplus
}
#endif

#endif /* __STUBS_H */
