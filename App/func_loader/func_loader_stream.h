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
 * @file   func_loader_stream.h
 * @brief  Serial stream processing for func_loader
 */

#ifndef __FUNC_LOADER_STREAM_H
#define __FUNC_LOADER_STREAM_H

#ifdef __cplusplus
extern "C" {
#endif

#include "func_loader.h"

#ifndef FL_LINE_SIZE
#define FL_LINE_SIZE 512
#endif

#ifndef FL_MAX_ARGC
#define FL_MAX_ARGC 16
#endif

/* Serial callbacks */
typedef int (*fl_serial_read_cb_t)(uint8_t* buf, size_t len);
typedef int (*fl_serial_write_cb_t)(const uint8_t* buf, size_t len);
typedef int (*fl_serial_available_cb_t)(void);

typedef struct {
    fl_serial_read_cb_t read_cb;
    fl_serial_write_cb_t write_cb;
    fl_serial_available_cb_t available_cb;
} fl_serial_t;

typedef struct {
    fl_context_t* ctx;
    const fl_serial_t* serial;
    char* line_buf;
    size_t line_size;
    size_t line_pos;
} fl_stream_t;

/**
 * @brief Initialize stream processor
 */
void fl_stream_init(fl_stream_t* s, fl_context_t* ctx, const fl_serial_t* serial, char* line_buf, size_t line_size);

/**
 * @brief Process incoming serial data
 */
void fl_stream_process(fl_stream_t* s);

/**
 * @brief Parse line and execute
 */
int fl_stream_exec_line(fl_stream_t* s, char* line);

#ifdef __cplusplus
}
#endif

#endif /* __FUNC_LOADER_STREAM_H */
