/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Minimal Unit Test Framework for FPBInject
 */

#ifndef __TEST_FRAMEWORK_H
#define __TEST_FRAMEWORK_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================================
 * Test Result Tracking
 * ============================================================================ */

typedef struct {
    int total_tests;
    int passed_tests;
    int failed_tests;
    int total_asserts;
    int failed_asserts;
} test_results_t;

extern test_results_t g_test_results;

/* ============================================================================
 * Color Output
 * ============================================================================ */

#ifdef NO_COLOR
#define COLOR_RED ""
#define COLOR_GREEN ""
#define COLOR_YELLOW ""
#define COLOR_CYAN ""
#define COLOR_RESET ""
#else
#define COLOR_RED "\033[31m"
#define COLOR_GREEN "\033[32m"
#define COLOR_YELLOW "\033[33m"
#define COLOR_CYAN "\033[36m"
#define COLOR_RESET "\033[0m"
#endif

/* ============================================================================
 * Test Macros
 * ============================================================================ */

#define TEST_SUITE_BEGIN(name)                               \
    do {                                                     \
        printf("\n" COLOR_CYAN "%s" COLOR_RESET "\n", name); \
    } while (0)

#define TEST_SUITE_END()

#define RUN_TEST(test_func)                                               \
    do {                                                                  \
        g_test_results.total_tests++;                                     \
        int _prev_fails = g_test_results.failed_asserts;                  \
        test_func();                                                      \
        if (g_test_results.failed_asserts == _prev_fails) {               \
            g_test_results.passed_tests++;                                \
            printf("  " COLOR_GREEN "✓" COLOR_RESET " %s\n", #test_func); \
        } else {                                                          \
            g_test_results.failed_tests++;                                \
            printf("  " COLOR_RED "✗" COLOR_RESET " %s\n", #test_func);   \
        }                                                                 \
    } while (0)

#define TEST_ASSERT(condition)                                                                           \
    do {                                                                                                 \
        g_test_results.total_asserts++;                                                                  \
        if (!(condition)) {                                                                              \
            g_test_results.failed_asserts++;                                                             \
            printf("    " COLOR_RED "FAIL: %s:%d: %s" COLOR_RESET "\n", __FILE__, __LINE__, #condition); \
        }                                                                                                \
    } while (0)

#define TEST_ASSERT_MSG(condition, msg)                                                                            \
    do {                                                                                                           \
        g_test_results.total_asserts++;                                                                            \
        if (!(condition)) {                                                                                        \
            g_test_results.failed_asserts++;                                                                       \
            printf("    " COLOR_RED "FAIL: %s:%d: %s - %s" COLOR_RESET "\n", __FILE__, __LINE__, #condition, msg); \
        }                                                                                                          \
    } while (0)

#define TEST_ASSERT_EQUAL(expected, actual)                                                                    \
    do {                                                                                                       \
        g_test_results.total_asserts++;                                                                        \
        if ((expected) != (actual)) {                                                                          \
            g_test_results.failed_asserts++;                                                                   \
            printf("    " COLOR_RED "FAIL: %s:%d: Expected %ld, got %ld" COLOR_RESET "\n", __FILE__, __LINE__, \
                   (long)(expected), (long)(actual));                                                          \
        }                                                                                                      \
    } while (0)

#define TEST_ASSERT_EQUAL_HEX(expected, actual)                                                                        \
    do {                                                                                                               \
        g_test_results.total_asserts++;                                                                                \
        if ((expected) != (actual)) {                                                                                  \
            g_test_results.failed_asserts++;                                                                           \
            printf("    " COLOR_RED "FAIL: %s:%d: Expected 0x%08lX, got 0x%08lX" COLOR_RESET "\n", __FILE__, __LINE__, \
                   (unsigned long)(expected), (unsigned long)(actual));                                                \
        }                                                                                                              \
    } while (0)

#define TEST_ASSERT_NOT_NULL(ptr)                                                                         \
    do {                                                                                                  \
        g_test_results.total_asserts++;                                                                   \
        if ((ptr) == NULL) {                                                                              \
            g_test_results.failed_asserts++;                                                              \
            printf("    " COLOR_RED "FAIL: %s:%d: Pointer is NULL" COLOR_RESET "\n", __FILE__, __LINE__); \
        }                                                                                                 \
    } while (0)

#define TEST_ASSERT_NULL(ptr)                                                                                 \
    do {                                                                                                      \
        g_test_results.total_asserts++;                                                                       \
        if ((ptr) != NULL) {                                                                                  \
            g_test_results.failed_asserts++;                                                                  \
            printf("    " COLOR_RED "FAIL: %s:%d: Pointer is not NULL" COLOR_RESET "\n", __FILE__, __LINE__); \
        }                                                                                                     \
    } while (0)

#define TEST_ASSERT_TRUE(condition) TEST_ASSERT(condition)
#define TEST_ASSERT_FALSE(condition) TEST_ASSERT(!(condition))

#define TEST_ASSERT_EQUAL_MEMORY(expected, actual, len)                                                   \
    do {                                                                                                  \
        g_test_results.total_asserts++;                                                                   \
        if (memcmp((expected), (actual), (len)) != 0) {                                                   \
            g_test_results.failed_asserts++;                                                              \
            printf("    " COLOR_RED "FAIL: %s:%d: Memory mismatch" COLOR_RESET "\n", __FILE__, __LINE__); \
        }                                                                                                 \
    } while (0)

#define TEST_ASSERT_STR_EQUAL(expected, actual)                                                                      \
    do {                                                                                                             \
        g_test_results.total_asserts++;                                                                              \
        if (strcmp((expected), (actual)) != 0) {                                                                     \
            g_test_results.failed_asserts++;                                                                         \
            printf("    " COLOR_RED "FAIL: %s:%d: Expected \"%s\", got \"%s\"" COLOR_RESET "\n", __FILE__, __LINE__, \
                   (expected), (actual));                                                                            \
        }                                                                                                            \
    } while (0)

/* ============================================================================
 * Framework Functions
 * ============================================================================ */

void test_framework_init(void);
int test_framework_report(void);
void test_framework_reset(void);

#ifdef __cplusplus
}
#endif

#endif /* __TEST_FRAMEWORK_H */
