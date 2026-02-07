/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Test Framework Implementation
 */

#include "test_framework.h"

test_results_t g_test_results = {0};

void test_framework_init(void) {
    test_framework_reset();
    printf("\n========================================\n");
    printf("    FPBInject Unit Tests\n");
    printf("========================================\n");
}

int test_framework_report(void) {
    printf("\n========================================\n");
    printf("    Test Results\n");
    printf("========================================\n\n");

    printf("    Tests:   %d/%d passed\n", g_test_results.passed_tests, g_test_results.total_tests);
    printf("    Asserts: %d total, %d failed\n", g_test_results.total_asserts, g_test_results.failed_asserts);

    if (g_test_results.failed_tests == 0) {
        printf("\n    " COLOR_GREEN "✓ All tests passed!" COLOR_RESET "\n\n");
        return 0;
    } else {
        printf("\n    " COLOR_RED "✗ %d test(s) failed" COLOR_RESET "\n\n", g_test_results.failed_tests);
        return 1;
    }
}

void test_framework_reset(void) {
    memset(&g_test_results, 0, sizeof(g_test_results));
}
