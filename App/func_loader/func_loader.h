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
 * @file   func_loader.h
 * @brief  Function loader core API (minimal)
 */

#ifndef __FUNC_LOADER_H
#define __FUNC_LOADER_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Maximum slot count */
#ifndef FL_MAX_SLOTS
#define FL_MAX_SLOTS 6
#endif

/* Callback types */
typedef void (*fl_output_cb_t)(void* user, const char* str);
typedef void* (*fl_malloc_cb_t)(size_t size);
typedef void (*fl_free_cb_t)(void* ptr);
typedef void (*fl_flush_dcache_cb_t)(uintptr_t start, uintptr_t end);

/**
 * @brief Slot state for tracking injection info
 */
typedef struct {
    bool active;          /* Slot is in use */
    uint32_t orig_addr;   /* Original function address */
    uint32_t target_addr; /* Injected code address */
    uint32_t code_size;   /* Injected code size */
} fl_slot_state_t;

/**
 * @brief Function loader context
 *
 * All fields set by porting layer before fl_init()
 */
typedef struct {
    /* Output callback (required) */
    fl_output_cb_t output_cb;
    void* output_user;

    /* Memory callbacks (optional, for dynamic alloc) */
    fl_malloc_cb_t malloc_cb;
    fl_free_cb_t free_cb;

    /* Cache flush callback (optional, for platforms with dcache) */
    fl_flush_dcache_cb_t flush_dcache_cb;

    /* Static buffer (required if malloc_cb is NULL) */
    uint8_t* static_buf;
    size_t static_size;

    /* Internal state (managed by fl_init) */
    size_t static_used;
    uintptr_t dyn_base;
    size_t dyn_size;
    size_t dyn_used;

    /* Slot tracking */
    fl_slot_state_t slots[FL_MAX_SLOTS];
} fl_context_t;

/**
 * @brief Initialize context
 */
void fl_init(fl_context_t* ctx);

/**
 * @brief Execute command from argc/argv
 * @return 0 on success, -1 on error
 */
int fl_exec_cmd(fl_context_t* ctx, int argc, const char** argv);

/**
 * @brief Main entry (implemented in porting layer)
 */
void func_loader_run(void);

#ifdef __cplusplus
}
#endif

#endif /* __FUNC_LOADER_H */
