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
 * @file   func_loader_log.c
 * @brief  Function loader logging implementation
 */

#include "fl_log.h"
#include <stdarg.h>
#include <stdio.h>

#define PRINT_BUF_SIZE 256

/* Global output callback */
static fl_output_cb_t g_output_cb = NULL;
static void* g_output_user = NULL;
static char log_buf[PRINT_BUF_SIZE];

void fl_log_init(fl_output_cb_t output_cb, void* output_user) {
    g_output_cb = output_cb;
    g_output_user = output_user;
}

void fl_response(bool ok, const char* fmt, ...) {
    va_list args;

    fl_print_raw(ok ? "[FLOK] " : "[FLERR] ");
    va_start(args, fmt);
    vsnprintf(log_buf, sizeof(log_buf), fmt, args);
    va_end(args);
    fl_print_raw(log_buf);
    fl_print_raw("\n[FLEND]\n");
}

void fl_print(const char* fmt, ...) {
    va_list args;

    va_start(args, fmt);
    vsnprintf(log_buf, sizeof(log_buf), fmt, args);
    va_end(args);
    fl_print_raw(log_buf);
}

void fl_println(const char* fmt, ...) {
    va_list args;

    va_start(args, fmt);
    vsnprintf(log_buf, sizeof(log_buf), fmt, args);
    va_end(args);
    fl_print_raw(log_buf);
    fl_print_raw("\n");
}

void fl_print_raw(const char* str) {
    if (g_output_cb) {
        g_output_cb(g_output_user, str);
    }
}
