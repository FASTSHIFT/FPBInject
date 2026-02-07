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
 * @file   test.h
 * @brief  FPB injection functionality test module header
 */

#ifndef __TEST_H
#define __TEST_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>

/**
 * @brief Test result structure
 */
typedef struct {
    const char* test_name;
    const char* message;
    uint32_t value;
    bool passed;
} fpb_test_result_t;

/**
 * @brief Run all FPB tests
 * @param results Test result array (at least 10 elements)
 * @param num_tests Returns actual number of tests
 */
void fpb_run_all_tests(fpb_test_result_t* results, uint8_t* num_tests);

/**
 * @brief Get test summary
 */
void fpb_get_test_summary(fpb_test_result_t* results, uint8_t num_tests, uint8_t* passed, uint8_t* failed);

/* Individual test functions */
fpb_test_result_t fpb_test_init(void);
fpb_test_result_t fpb_test_basic_redirect(void);
fpb_test_result_t fpb_test_parameter_redirect(void);
fpb_test_result_t fpb_test_void_redirect(void);
fpb_test_result_t fpb_test_multi_patch(void);

/**
 * @brief Run FPB tests (called from main)
 */
void test_run(void);

#ifdef __cplusplus
}
#endif

#endif /* __TEST_H */
