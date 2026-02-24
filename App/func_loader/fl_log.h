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
 * @file   fl_log.h
 * @brief  Function loader logging utilities
 */

#ifndef FL_LOG_H
#define FL_LOG_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>

/* Callback types */
typedef void (*fl_output_cb_t)(void* user, const char* str);

/**
 * @brief Initialize logging with output callback
 * @param output_cb Output callback function
 * @param output_user User data for output callback
 */
void fl_log_init(fl_output_cb_t output_cb, void* output_user);

/**
 * @brief Send a response with OK/ERR prefix
 * @param ok true for [FLOK], false for [FLERR]
 * @param fmt Printf-style format string
 * @param ... Format arguments
 */
void fl_response(bool ok, const char* fmt, ...);

/**
 * @brief Print a message without OK/ERR prefix
 * @param fmt Printf-style format string
 * @param ... Format arguments
 */
void fl_print(const char* fmt, ...);

/**
 * @brief Print a message with newline at the end
 * @param fmt Printf-style format string
 * @param ... Format arguments
 */
void fl_println(const char* fmt, ...);

/**
 * @brief Print a raw string without formatting (no buffer limit)
 * @param str String to output
 */
void fl_print_raw(const char* str);

#ifdef __cplusplus
}
#endif

#endif /* FL_LOG_H */
