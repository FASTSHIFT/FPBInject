/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Unit tests for fpb_debugmon_nuttx.c
 */

#include "test_framework.h"
#include "fpb_debugmon.h"
#include "nuttx_mock.h"

/* ============================================================================
 * Test Setup/Teardown
 * ============================================================================ */

static void setup_nuttx_debugmon(void) {
    nuttx_mock_reset();
    fpb_debugmon_deinit();
}

static void teardown_nuttx_debugmon(void) {
    fpb_debugmon_deinit();
    nuttx_mock_reset();
}

/* ============================================================================
 * Initialization Tests
 * ============================================================================ */

static void test_nuttx_debugmon_init_success(void) {
    setup_nuttx_debugmon();

    int ret = fpb_debugmon_init();
    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT_TRUE(fpb_debugmon_is_active());

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_init_enables_debugmon(void) {
    setup_nuttx_debugmon();

    fpb_debugmon_init();
    TEST_ASSERT_TRUE(nuttx_mock_debugmon_is_enabled());

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_init_idempotent(void) {
    setup_nuttx_debugmon();

    int ret1 = fpb_debugmon_init();
    int ret2 = fpb_debugmon_init();

    TEST_ASSERT_EQUAL(0, ret1);
    TEST_ASSERT_EQUAL(0, ret2);
    TEST_ASSERT_TRUE(fpb_debugmon_is_active());

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_not_active_before_init(void) {
    setup_nuttx_debugmon();

    TEST_ASSERT_FALSE(fpb_debugmon_is_active());

    teardown_nuttx_debugmon();
}

/* ============================================================================
 * Set Redirect Tests
 * ============================================================================ */

static void test_nuttx_debugmon_set_redirect_success(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    int ret = fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);
    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT_EQUAL(1, nuttx_mock_get_debugpoint_count());

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_set_redirect_with_thumb_bit(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    /* Original address with Thumb bit set */
    int ret = fpb_debugmon_set_redirect(0, 0x08001001, 0x08002001);
    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT_EQUAL(1, nuttx_mock_get_debugpoint_count());

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_set_redirect_invalid_comp_id(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    int ret = fpb_debugmon_set_redirect(FPB_DEBUGMON_MAX_REDIRECTS, 0x08001000, 0x08002001);
    TEST_ASSERT_EQUAL(-1, ret);

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_set_redirect_not_initialized(void) {
    setup_nuttx_debugmon();
    /* Don't call fpb_debugmon_init() */

    int ret = fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);
    TEST_ASSERT_EQUAL(-1, ret);

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_set_redirect_multiple(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    TEST_ASSERT_EQUAL(0, fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001));
    TEST_ASSERT_EQUAL(0, fpb_debugmon_set_redirect(1, 0x08003000, 0x08004001));
    TEST_ASSERT_EQUAL(0, fpb_debugmon_set_redirect(2, 0x08005000, 0x08006001));

    TEST_ASSERT_EQUAL(3, nuttx_mock_get_debugpoint_count());

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_set_redirect_replace_existing(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    /* Set first redirect */
    TEST_ASSERT_EQUAL(0, fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001));

    /* Replace with different address */
    TEST_ASSERT_EQUAL(0, fpb_debugmon_set_redirect(0, 0x08003000, 0x08004001));

    /* Should still only have 1 debugpoint (old removed, new added) */
    TEST_ASSERT_EQUAL(1, nuttx_mock_get_debugpoint_count());

    /* Verify new redirect is active */
    TEST_ASSERT_EQUAL(0x08004001, fpb_debugmon_get_redirect(0x08003000));

    teardown_nuttx_debugmon();
}

/* ============================================================================
 * Clear Redirect Tests
 * ============================================================================ */

static void test_nuttx_debugmon_clear_redirect_success(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);
    TEST_ASSERT_EQUAL(1, nuttx_mock_get_debugpoint_count());

    int ret = fpb_debugmon_clear_redirect(0);
    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT_EQUAL(0, nuttx_mock_get_debugpoint_count());

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_clear_redirect_nonexistent(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    /* Clear without setting - should be OK (no-op) */
    int ret = fpb_debugmon_clear_redirect(0);
    TEST_ASSERT_EQUAL(0, ret);

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_clear_redirect_invalid_comp_id(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    int ret = fpb_debugmon_clear_redirect(FPB_DEBUGMON_MAX_REDIRECTS);
    TEST_ASSERT_EQUAL(-1, ret);

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_clear_redirect_multiple(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);
    fpb_debugmon_set_redirect(1, 0x08003000, 0x08004001);
    fpb_debugmon_set_redirect(2, 0x08005000, 0x08006001);
    TEST_ASSERT_EQUAL(3, nuttx_mock_get_debugpoint_count());

    /* Clear middle one */
    TEST_ASSERT_EQUAL(0, fpb_debugmon_clear_redirect(1));
    TEST_ASSERT_EQUAL(2, nuttx_mock_get_debugpoint_count());

    /* Clear first one */
    TEST_ASSERT_EQUAL(0, fpb_debugmon_clear_redirect(0));
    TEST_ASSERT_EQUAL(1, nuttx_mock_get_debugpoint_count());

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_clear_redirect_double(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);

    TEST_ASSERT_EQUAL(0, fpb_debugmon_clear_redirect(0));
    TEST_ASSERT_EQUAL(0, fpb_debugmon_clear_redirect(0)); /* Second clear should be OK */

    teardown_nuttx_debugmon();
}

/* ============================================================================
 * Get Redirect Tests
 * ============================================================================ */

static void test_nuttx_debugmon_get_redirect_existing(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);

    uint32_t result = fpb_debugmon_get_redirect(0x08001000);
    TEST_ASSERT_EQUAL(0x08002001, result);

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_get_redirect_with_thumb_bit(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);

    /* Query with Thumb bit set - should still find it */
    uint32_t result = fpb_debugmon_get_redirect(0x08001000 | 1);
    TEST_ASSERT_EQUAL(0x08002001, result);

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_get_redirect_nonexistent(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    uint32_t result = fpb_debugmon_get_redirect(0x08001000);
    TEST_ASSERT_EQUAL(0, result);

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_get_redirect_after_clear(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);
    fpb_debugmon_clear_redirect(0);

    uint32_t result = fpb_debugmon_get_redirect(0x08001000);
    TEST_ASSERT_EQUAL(0, result);

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_get_redirect_multiple(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);
    fpb_debugmon_set_redirect(1, 0x08003000, 0x08004001);
    fpb_debugmon_set_redirect(2, 0x08005000, 0x08006001);

    TEST_ASSERT_EQUAL(0x08002001, fpb_debugmon_get_redirect(0x08001000));
    TEST_ASSERT_EQUAL(0x08004001, fpb_debugmon_get_redirect(0x08003000));
    TEST_ASSERT_EQUAL(0x08006001, fpb_debugmon_get_redirect(0x08005000));

    teardown_nuttx_debugmon();
}

/* ============================================================================
 * Callback Tests (Breakpoint Trigger Simulation)
 * ============================================================================ */

static void test_nuttx_debugmon_callback_triggers(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);

    /* Trigger the breakpoint via mock */
    int ret = nuttx_mock_trigger_breakpoint(0x08001000);
    TEST_ASSERT_EQUAL(0, ret);

    /* PC should be modified to redirect address */
    uint32_t pc = nuttx_mock_get_pc();
    TEST_ASSERT_EQUAL(0x08002001, pc);

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_callback_with_thumb_bit(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);

    /* Trigger with Thumb bit */
    int ret = nuttx_mock_trigger_breakpoint(0x08001000 | 1);
    TEST_ASSERT_EQUAL(0, ret);

    teardown_nuttx_debugmon();
}

static void test_nuttx_debugmon_callback_no_breakpoint(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);

    /* Trigger at different address - should fail */
    int ret = nuttx_mock_trigger_breakpoint(0x08003000);
    TEST_ASSERT_EQUAL(-1, ret);

    teardown_nuttx_debugmon();
}

/* ============================================================================
 * Handler Tests
 * ============================================================================ */

static void test_nuttx_debugmon_handler_is_noop(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    /* In NuttX implementation, fpb_debugmon_handler is a no-op
     * because NuttX calls our callback directly */
    uint32_t stack_frame[8] = {0};

    /* Should not crash */
    fpb_debugmon_handler(stack_frame);

    teardown_nuttx_debugmon();
}

/* ============================================================================
 * Deinit Tests
 * ============================================================================ */

static void test_nuttx_debugmon_deinit_clears_all(void) {
    setup_nuttx_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x08002001);
    fpb_debugmon_set_redirect(1, 0x08003000, 0x08004001);

    fpb_debugmon_deinit();

    TEST_ASSERT_FALSE(fpb_debugmon_is_active());
    TEST_ASSERT_EQUAL(0, nuttx_mock_get_debugpoint_count());

    nuttx_mock_reset();
}

/* ============================================================================
 * Test Runner
 * ============================================================================ */

void run_fpb_debugmon_nuttx_tests(void) {
    TEST_SUITE_BEGIN("fpb_debugmon_nuttx - Initialization");
    RUN_TEST(test_nuttx_debugmon_init_success);
    RUN_TEST(test_nuttx_debugmon_init_enables_debugmon);
    RUN_TEST(test_nuttx_debugmon_init_idempotent);
    RUN_TEST(test_nuttx_debugmon_not_active_before_init);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_debugmon_nuttx - Set Redirect");
    RUN_TEST(test_nuttx_debugmon_set_redirect_success);
    RUN_TEST(test_nuttx_debugmon_set_redirect_with_thumb_bit);
    RUN_TEST(test_nuttx_debugmon_set_redirect_invalid_comp_id);
    RUN_TEST(test_nuttx_debugmon_set_redirect_not_initialized);
    RUN_TEST(test_nuttx_debugmon_set_redirect_multiple);
    RUN_TEST(test_nuttx_debugmon_set_redirect_replace_existing);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_debugmon_nuttx - Clear Redirect");
    RUN_TEST(test_nuttx_debugmon_clear_redirect_success);
    RUN_TEST(test_nuttx_debugmon_clear_redirect_nonexistent);
    RUN_TEST(test_nuttx_debugmon_clear_redirect_invalid_comp_id);
    RUN_TEST(test_nuttx_debugmon_clear_redirect_multiple);
    RUN_TEST(test_nuttx_debugmon_clear_redirect_double);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_debugmon_nuttx - Get Redirect");
    RUN_TEST(test_nuttx_debugmon_get_redirect_existing);
    RUN_TEST(test_nuttx_debugmon_get_redirect_with_thumb_bit);
    RUN_TEST(test_nuttx_debugmon_get_redirect_nonexistent);
    RUN_TEST(test_nuttx_debugmon_get_redirect_after_clear);
    RUN_TEST(test_nuttx_debugmon_get_redirect_multiple);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_debugmon_nuttx - Callback");
    RUN_TEST(test_nuttx_debugmon_callback_triggers);
    RUN_TEST(test_nuttx_debugmon_callback_with_thumb_bit);
    RUN_TEST(test_nuttx_debugmon_callback_no_breakpoint);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_debugmon_nuttx - Handler");
    RUN_TEST(test_nuttx_debugmon_handler_is_noop);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_debugmon_nuttx - Deinit");
    RUN_TEST(test_nuttx_debugmon_deinit_clears_all);
    TEST_SUITE_END();
}

/* ============================================================================
 * Main Entry Point (for standalone test executable)
 * ============================================================================ */

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    printf("\n");
    printf("╔══════════════════════════════════════════════════════════════╗\n");
    printf("║        FPBInject NuttX DebugMon Unit Tests                   ║\n");
    printf("╚══════════════════════════════════════════════════════════════╝\n");
    printf("\n");

    test_framework_init();

    run_fpb_debugmon_nuttx_tests();

    return test_framework_report();
}
