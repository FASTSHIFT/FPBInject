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
 * @file   fpb_attributes.h
 * @brief  Compiler attribute macros for FPBInject
 *
 * Provides portable macros for compiler attributes used across the project.
 * These macros ensure consistent attribute usage and compiler portability.
 */

#ifndef FPB_ATTRIBUTES_H
#define FPB_ATTRIBUTES_H

/**
 * @brief Prevent the compiler from inlining a function
 *
 * This is critical for FPB injection targets: if the compiler inlines a
 * function, its code gets merged into the caller and there is no standalone
 * entry point for FPB to patch. Use this macro on any function that may be
 * a patch target.
 *
 * Usage:
 *   FPB_NOINLINE void my_function(void);
 *
 *   FPB_NOINLINE void my_function(void) { ... }
 */
/* GCC, Clang, Keil (armcc/armclang), IAR all support __attribute__((noinline)) */
#if defined(__GNUC__) || defined(__clang__) || defined(__CC_ARM) || defined(__ARMCC_VERSION) \
    || defined(__IAR_SYSTEMS_ICC__)
#define FPB_NOINLINE __attribute__((noinline))
#else
#define FPB_NOINLINE
#endif

#endif /* FPB_ATTRIBUTES_H */
