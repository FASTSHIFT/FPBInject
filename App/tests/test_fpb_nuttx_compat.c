/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Unit tests for fpb_nuttx_compat.h
 *
 * Since fpb_nuttx_compat.h uses preprocessor conditionals evaluated at
 * compile time, we test each scenario via separate helper translation
 * units (scenario_*.c) that simulate different NuttX macro environments.
 * This test file links against those helpers and verifies the results.
 */

#include "test_framework.h"
#include <stdint.h>

/* ============================================================================
 * Helper function declarations (implemented in separate .c files)
 * ============================================================================ */

/* Scenario 1: running_regs already defined (modern NuttX >= 2024-09) */
uint32_t scenario1_get_pc(void);
int scenario1_fallback_null_defined(void);

/* Scenario 2: CURRENT_REGS defined (old NuttX < 2024-04) */
uint32_t scenario2_get_pc(void);
int scenario2_fallback_null_defined(void);

/* Scenario 3: Neither defined (intermediate NuttX) */
uint32_t scenario3_get_pc(void);
int scenario3_fallback_null_defined(void);

/* ============================================================================
 * Tests
 * ============================================================================ */

static void test_scenario1_running_regs_native(void) {
    /* Modern NuttX: running_regs() returns real register context */
    uint32_t pc = scenario1_get_pc();
    TEST_ASSERT_EQUAL_HEX(0xDEADBEEF, pc);

    /* FPB_RUNNING_REGS_FALLBACK_NULL should NOT be defined */
    TEST_ASSERT_EQUAL(0, scenario1_fallback_null_defined());
}

static void test_scenario2_current_regs_fallback(void) {
    /* Old NuttX: running_regs() mapped to CURRENT_REGS */
    uint32_t pc = scenario2_get_pc();
    TEST_ASSERT_EQUAL_HEX(0xCAFEBABE, pc);

    /* FPB_RUNNING_REGS_FALLBACK_NULL should NOT be defined */
    TEST_ASSERT_EQUAL(0, scenario2_fallback_null_defined());
}

static void test_scenario3_null_fallback(void) {
    /* Intermediate NuttX with manual override: running_regs() works */
    uint32_t pc = scenario3_get_pc();
    TEST_ASSERT_EQUAL_HEX(0x12345678, pc);

    /* FPB_RUNNING_REGS_FALLBACK_NULL should NOT be defined */
    TEST_ASSERT_EQUAL(0, scenario3_fallback_null_defined());
}

/* ============================================================================
 * Test Runner
 * ============================================================================ */

void run_fpb_nuttx_compat_tests(void) {
    TEST_SUITE_BEGIN("fpb_nuttx_compat - running_regs native (modern NuttX)");
    RUN_TEST(test_scenario1_running_regs_native);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_nuttx_compat - CURRENT_REGS fallback (old NuttX)");
    RUN_TEST(test_scenario2_current_regs_fallback);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_nuttx_compat - NULL fallback (intermediate NuttX)");
    RUN_TEST(test_scenario3_null_fallback);
    TEST_SUITE_END();
}

/* ============================================================================
 * Main Entry Point (for standalone test executable)
 * ============================================================================ */

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    printf("\n");
    printf("============================================================\n");
    printf("  FPBInject NuttX Compat (running_regs) Unit Tests          \n");
    printf("============================================================\n");
    printf("\n");

    test_framework_init();

    run_fpb_nuttx_compat_tests();

    return test_framework_report();
}
