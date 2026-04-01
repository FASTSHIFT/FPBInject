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
 * @file   fl_error.h
 * @brief  Error codes for func_loader
 */

#ifndef FL_ERROR_H
#define FL_ERROR_H

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Error codes for fl_exec_cmd and command handlers
 */
typedef enum {
    FL_OK = 0,           /* Command executed (success or handled error) */
    FL_ERR_ARGS = -1,    /* Missing or invalid required arguments */
    FL_ERR_CRC = -2,     /* CRC verification failed */
    FL_ERR_PARSE = -3,   /* Argument parsing failed */
    FL_ERR_UNKNOWN = -4, /* Unknown command */
} fl_error_t;

#ifdef __cplusplus
}
#endif

#endif /* FL_ERROR_H */
