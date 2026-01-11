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

/* Callback types */
typedef void (*fl_output_cb_t)(void* user, const char* str);
typedef void* (*fl_malloc_cb_t)(size_t size);
typedef void (*fl_free_cb_t)(void* ptr);

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

    /* Static buffer (required if malloc_cb is NULL) */
    uint8_t* static_buf;
    size_t static_size;

    /* Internal state (managed by fl_init) */
    size_t static_used;
    uintptr_t dyn_base;
    size_t dyn_size;
    size_t dyn_used;
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
