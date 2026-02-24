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
 * @file   test.cpp
 * @brief  FPB injection functionality test module
 *
 * Provides automated testing for FPB functionality including:
 * - FPB initialization test
 * - Function redirection test
 * - Instruction replacement test
 * - Boundary condition test
 */

#include "fpb_inject.h"
#include "test.h"
#include <stdio.h>

static volatile uint32_t g_test_counter = 0;
static volatile uint32_t g_original_call_count = 0;
static volatile uint32_t g_patched_call_count = 0;

/* Original function A - returns fixed value 100 */
__attribute__((noinline)) uint32_t test_func_original_a(void) {
    g_original_call_count++;
    return 100;
}

/* Patched function A - returns fixed value 200 */
__attribute__((noinline)) uint32_t test_func_patched_a(void) {
    g_patched_call_count++;
    return 200;
}

/* Original function B - simple calculation */
__attribute__((noinline)) uint32_t test_func_original_b(uint32_t x) {
    g_original_call_count++;
    return x * 2;
}

/* Patched function B - different calculation */
__attribute__((noinline)) uint32_t test_func_patched_b(uint32_t x) {
    g_patched_call_count++;
    return x * 3;
}

/* Original function C - void return */
__attribute__((noinline)) void test_func_original_c(void) {
    g_original_call_count++;
    g_test_counter += 10;
}

/* Patched function C - void return */
__attribute__((noinline)) void test_func_patched_c(void) {
    g_patched_call_count++;
    g_test_counter += 100;
}

fpb_test_result_t fpb_test_init(void) {
    fpb_test_result_t result;
    result.test_name = "FPB Init";
    result.message = NULL;
    result.value = 0;
    result.passed = false;

    fpb_result_t ret = fpb_init();
    if (ret == FPB_ERR_NOT_SUPPORTED) {
        result.message = "FPB not supported on this device";
        return result;
    }

    if (ret != FPB_OK) {
        result.message = "fpb_init failed";
        return result;
    }

    const fpb_state_t* state = fpb_get_state();
    if (!state->initialized) {
        result.message = "FPB state not initialized";
        return result;
    }

    if (state->num_code_comp == 0) {
        result.message = "No code comparators available";
        return result;
    }

    result.passed = true;
    result.message = "FPB initialized successfully";
    result.value = state->num_code_comp;

    return result;
}

fpb_test_result_t fpb_test_basic_redirect(void) {
    fpb_test_result_t result;
    result.test_name = "Basic Function Redirect";
    result.message = NULL;
    result.value = 0;
    result.passed = false;

    g_original_call_count = 0;
    g_patched_call_count = 0;

    uint32_t ret1 = test_func_original_a();
    if (ret1 != 100) {
        result.message = "Original function returned wrong value";
        return result;
    }

    if (g_original_call_count != 1) {
        result.message = "Original call count mismatch";
        return result;
    }

    fpb_result_t ret = fpb_set_patch(0, (uint32_t)test_func_original_a, (uint32_t)test_func_patched_a);
    if (ret != FPB_OK) {
        result.message = "fpb_set_patch failed";
        return result;
    }

    uint32_t ret2 = test_func_original_a();

    if (ret2 != 200) {
        result.message = "Patched function not executed";
        result.value = ret2;
        return result;
    }

    if (g_patched_call_count != 1) {
        result.message = "Patched call count mismatch";
        return result;
    }

    fpb_clear_patch(0);

    uint32_t ret3 = test_func_original_a();
    if (ret3 != 100) {
        result.message = "Original function not restored";
        return result;
    }

    result.passed = true;
    result.message = "Function redirect works correctly";

    return result;
}

fpb_test_result_t fpb_test_parameter_redirect(void) {
    fpb_test_result_t result;
    result.test_name = "Parameter Function Redirect";
    result.message = NULL;
    result.value = 0;
    result.passed = false;

    uint32_t ret1 = test_func_original_b(10);
    if (ret1 != 20) {
        result.message = "Original function calculation wrong";
        return result;
    }

    fpb_result_t ret = fpb_set_patch(1, (uint32_t)test_func_original_b, (uint32_t)test_func_patched_b);
    if (ret != FPB_OK) {
        result.message = "fpb_set_patch failed";
        return result;
    }

    uint32_t ret2 = test_func_original_b(10);
    if (ret2 != 30) {
        result.message = "Patched function calculation wrong";
        result.value = ret2;
        return result;
    }

    fpb_clear_patch(1);

    result.passed = true;
    result.message = "Parameter function redirect works";

    return result;
}

fpb_test_result_t fpb_test_void_redirect(void) {
    fpb_test_result_t result;
    result.test_name = "Void Function Redirect";
    result.message = NULL;
    result.value = 0;
    result.passed = false;

    g_test_counter = 0;

    test_func_original_c();
    if (g_test_counter != 10) {
        result.message = "Original void function failed";
        return result;
    }

    fpb_result_t ret = fpb_set_patch(2, (uint32_t)test_func_original_c, (uint32_t)test_func_patched_c);
    if (ret != FPB_OK) {
        result.message = "fpb_set_patch failed";
        return result;
    }

    test_func_original_c();
    if (g_test_counter != 110) {
        result.message = "Patched void function failed";
        result.value = g_test_counter;
        return result;
    }

    fpb_clear_patch(2);

    result.passed = true;
    result.message = "Void function redirect works";

    return result;
}

fpb_test_result_t fpb_test_multi_patch(void) {
    fpb_test_result_t result;
    result.test_name = "Multiple Patches";
    result.message = NULL;
    result.value = 0;
    result.passed = false;

    fpb_result_t ret = fpb_set_patch(0, (uint32_t)test_func_original_a, (uint32_t)test_func_patched_a);
    if (ret != FPB_OK) {
        result.message = "fpb_set_patch failed (comp 0)";
        return result;
    }
    ret = fpb_set_patch(1, (uint32_t)test_func_original_b, (uint32_t)test_func_patched_b);
    if (ret != FPB_OK) {
        result.message = "fpb_set_patch failed (comp 1)";
        return result;
    }

    uint32_t ret1 = test_func_original_a();
    uint32_t ret2 = test_func_original_b(5);

    if (ret1 != 200 || ret2 != 15) {
        result.message = "Multi-patch failed";
        return result;
    }

    /* Clear only comp 0, comp 1 should still work */
    fpb_clear_patch(0);

    ret1 = test_func_original_a();
    ret2 = test_func_original_b(5);

    if (ret1 != 100 || ret2 != 15) {
        result.message = "Selective clear failed";
        return result;
    }

    fpb_clear_patch(1);

    result.passed = true;
    result.message = "Multiple patches work correctly";

    return result;
}

void fpb_run_all_tests(fpb_test_result_t* results, size_t results_len, uint8_t* num_tests) {
    uint8_t idx = 0;

    fpb_init();

    /* Array of test function pointers */
    fpb_test_result_t (*tests[])(void) = {fpb_test_init, fpb_test_basic_redirect, fpb_test_parameter_redirect,
                                          fpb_test_void_redirect, fpb_test_multi_patch};

    size_t num = sizeof(tests) / sizeof(tests[0]);

    if (results_len < num) {
        printf("Error: Insufficient space in results array\n");
        num = results_len;
    }

    for (size_t i = 0; i < num; ++i) {
        results[idx] = tests[i]();
        printf("[%s] %s: %s\n", results[idx].passed ? "PASS" : "FAIL", results[idx].test_name, results[idx].message);
        idx++;
    }

    *num_tests = idx;

    fpb_deinit();
}

void fpb_get_test_summary(fpb_test_result_t* results, uint8_t num_tests, uint8_t* passed, uint8_t* failed) {
    *passed = 0;
    *failed = 0;

    for (uint8_t i = 0; i < num_tests; i++) {
        if (results[i].passed) {
            (*passed)++;
        } else {
            (*failed)++;
        }
    }
}

void test_run(void) {
    fpb_test_result_t results[10];
    uint8_t num_tests = 0;
    uint8_t passed = 0, failed = 0;

    printf("\n========================================\n");
    printf("FPB Inject Test Suite\n");
    printf("========================================\n\n");

    fpb_run_all_tests(results, sizeof(results) / sizeof(results[0]), &num_tests);
    fpb_get_test_summary(results, num_tests, &passed, &failed);

    printf("\n----------------------------------------\n");
    printf("Results: %d passed, %d failed\n", passed, failed);
    printf("========================================\n");

    while (1) {
        __asm volatile("wfi");
    }
}
