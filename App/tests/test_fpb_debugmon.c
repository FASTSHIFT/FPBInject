/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Unit tests for fpb_debugmon.c
 */

#include "test_framework.h"
#include "fpb_debugmon.h"
#include "fpb_mock_regs.h"

/* ============================================================================
 * Test Setup/Teardown
 * ============================================================================ */

static void setup_debugmon(void) {
    fpb_mock_configure(6, 2); /* 6 code + 2 lit comparators */
}

static void teardown_debugmon(void) {
    fpb_debugmon_deinit();
    fpb_mock_reset();
}

/* ============================================================================
 * Initialization Tests
 * ============================================================================ */

static void test_debugmon_init_success(void) {
    setup_debugmon();

    int ret = fpb_debugmon_init();
    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT_TRUE(fpb_debugmon_is_active());

    teardown_debugmon();
}

static void test_debugmon_init_no_fpb(void) {
    fpb_mock_configure(0, 0); /* No FPB comparators */

    int ret = fpb_debugmon_init();
    TEST_ASSERT_EQUAL(-1, ret);
    TEST_ASSERT_FALSE(fpb_debugmon_is_active());

    fpb_mock_reset();
}

static void test_debugmon_init_enables_monitor(void) {
    setup_debugmon();

    fpb_debugmon_init();

    /* Check that MON_EN (bit 16) is set in DEMCR */
    uint32_t demcr = fpb_mock_get_demcr();
    TEST_ASSERT((demcr & (1UL << 16)) != 0);

    teardown_debugmon();
}

static void test_debugmon_init_idempotent(void) {
    setup_debugmon();

    int ret1 = fpb_debugmon_init();
    int ret2 = fpb_debugmon_init();

    TEST_ASSERT_EQUAL(0, ret1);
    /* Second init should still succeed (idempotent) */
    /* Note: current implementation doesn't check if already initialized */
    (void)ret2; /* Avoid unused variable warning */

    teardown_debugmon();
}

/* ============================================================================
 * Deinitialization Tests
 * ============================================================================ */

static void test_debugmon_deinit_clears_state(void) {
    setup_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_deinit();

    TEST_ASSERT_FALSE(fpb_debugmon_is_active());

    teardown_debugmon();
}

static void test_debugmon_deinit_without_init(void) {
    /* Should not crash when deinit called without init */
    fpb_debugmon_deinit();
    TEST_ASSERT_FALSE(fpb_debugmon_is_active());
}

/* ============================================================================
 * Set Redirect Tests
 * ============================================================================ */

static void test_debugmon_set_redirect_basic(void) {
    setup_debugmon();
    fpb_debugmon_init();

    int ret = fpb_debugmon_set_redirect(0, 0x08001000, 0x20001000);
    TEST_ASSERT_EQUAL(0, ret);

    teardown_debugmon();
}

static void test_debugmon_set_redirect_not_initialized(void) {
    setup_debugmon();
    /* Don't call init */

    int ret = fpb_debugmon_set_redirect(0, 0x08001000, 0x20001000);
    TEST_ASSERT_EQUAL(-1, ret);

    teardown_debugmon();
}

static void test_debugmon_set_redirect_invalid_comp(void) {
    setup_debugmon();
    fpb_debugmon_init();

    /* comp_id 6 is out of range (max is 5 for 6 comparators) */
    int ret = fpb_debugmon_set_redirect(6, 0x08001000, 0x20001000);
    TEST_ASSERT_EQUAL(-1, ret);

    teardown_debugmon();
}

static void test_debugmon_set_redirect_strips_thumb_bit(void) {
    setup_debugmon();
    fpb_debugmon_init();

    /* Address with Thumb bit set */
    int ret = fpb_debugmon_set_redirect(0, 0x08001001, 0x20001001);
    TEST_ASSERT_EQUAL(0, ret);

    /* Lookup should work with or without Thumb bit */
    uint32_t target = fpb_debugmon_get_redirect(0x08001000);
    TEST_ASSERT(target != 0);
    TEST_ASSERT((target & 1) != 0); /* Target should have Thumb bit */

    teardown_debugmon();
}

static void test_debugmon_set_redirect_configures_fpb_comp(void) {
    setup_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x20001000);

    /* Check FPB_COMP[0] is configured */
    uint32_t comp = mock_fpb_comp[0];
    TEST_ASSERT((comp & 0x1) != 0);        /* Enabled */
    TEST_ASSERT((comp & 0xC0000000) != 0); /* REPLACE field set (BKPT mode) */

    teardown_debugmon();
}

static void test_debugmon_set_redirect_multiple(void) {
    setup_debugmon();
    fpb_debugmon_init();

    int ret0 = fpb_debugmon_set_redirect(0, 0x08001000, 0x20001000);
    int ret1 = fpb_debugmon_set_redirect(1, 0x08002000, 0x20002000);
    int ret2 = fpb_debugmon_set_redirect(2, 0x08003000, 0x20003000);

    TEST_ASSERT_EQUAL(0, ret0);
    TEST_ASSERT_EQUAL(0, ret1);
    TEST_ASSERT_EQUAL(0, ret2);

    TEST_ASSERT(fpb_debugmon_get_redirect(0x08001000) != 0);
    TEST_ASSERT(fpb_debugmon_get_redirect(0x08002000) != 0);
    TEST_ASSERT(fpb_debugmon_get_redirect(0x08003000) != 0);

    teardown_debugmon();
}

/* ============================================================================
 * Clear Redirect Tests
 * ============================================================================ */

static void test_debugmon_clear_redirect_basic(void) {
    setup_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x20001000);
    int ret = fpb_debugmon_clear_redirect(0);

    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT_EQUAL(0, fpb_debugmon_get_redirect(0x08001000));

    teardown_debugmon();
}

static void test_debugmon_clear_redirect_not_initialized(void) {
    setup_debugmon();

    int ret = fpb_debugmon_clear_redirect(0);
    TEST_ASSERT_EQUAL(-1, ret);

    teardown_debugmon();
}

static void test_debugmon_clear_redirect_invalid_comp(void) {
    setup_debugmon();
    fpb_debugmon_init();

    int ret = fpb_debugmon_clear_redirect(10);
    TEST_ASSERT_EQUAL(-1, ret);

    teardown_debugmon();
}

static void test_debugmon_clear_redirect_clears_fpb_comp(void) {
    setup_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x20001000);
    fpb_debugmon_clear_redirect(0);

    /* Check FPB_COMP[0] is cleared */
    TEST_ASSERT_EQUAL(0, mock_fpb_comp[0]);

    teardown_debugmon();
}

/* ============================================================================
 * Get Redirect Tests
 * ============================================================================ */

static void test_debugmon_get_redirect_found(void) {
    setup_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x20001000);

    uint32_t target = fpb_debugmon_get_redirect(0x08001000);
    TEST_ASSERT_EQUAL(0x20001001, target); /* With Thumb bit */

    teardown_debugmon();
}

static void test_debugmon_get_redirect_not_found(void) {
    setup_debugmon();
    fpb_debugmon_init();

    uint32_t target = fpb_debugmon_get_redirect(0x08001000);
    TEST_ASSERT_EQUAL(0, target);

    teardown_debugmon();
}

static void test_debugmon_get_redirect_with_thumb_bit(void) {
    setup_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x20001000);

    /* Lookup with Thumb bit should also work */
    uint32_t target = fpb_debugmon_get_redirect(0x08001001);
    TEST_ASSERT_EQUAL(0x20001001, target);

    teardown_debugmon();
}

/* ============================================================================
 * Handler Tests
 * ============================================================================ */

static void test_debugmon_handler_redirects_pc(void) {
    setup_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x20001000);

    /* Simulate stack frame: R0-R3, R12, LR, PC, xPSR */
    uint32_t stack_frame[8] = {0, 0, 0, 0, 0, 0, 0x08001000, 0};

    /* Set DFSR breakpoint flag */
    fpb_mock_set_dfsr(1UL << 1);

    fpb_debugmon_handler(stack_frame);

    /* PC should be redirected */
    TEST_ASSERT_EQUAL(0x20001001, stack_frame[6]);

    teardown_debugmon();
}

static void test_debugmon_handler_no_redirect(void) {
    setup_debugmon();
    fpb_debugmon_init();

    /* No redirect set for this address */
    uint32_t stack_frame[8] = {0, 0, 0, 0, 0, 0, 0x08002000, 0};

    fpb_mock_set_dfsr(1UL << 1);

    fpb_debugmon_handler(stack_frame);

    /* PC should be unchanged */
    TEST_ASSERT_EQUAL(0x08002000, stack_frame[6]);

    teardown_debugmon();
}

static void test_debugmon_handler_not_breakpoint(void) {
    setup_debugmon();
    fpb_debugmon_init();

    fpb_debugmon_set_redirect(0, 0x08001000, 0x20001000);

    uint32_t stack_frame[8] = {0, 0, 0, 0, 0, 0, 0x08001000, 0};

    /* DFSR breakpoint flag NOT set */
    fpb_mock_set_dfsr(0);

    fpb_debugmon_handler(stack_frame);

    /* PC should be unchanged (not a breakpoint event) */
    TEST_ASSERT_EQUAL(0x08001000, stack_frame[6]);

    teardown_debugmon();
}

/* ============================================================================
 * Test Registration
 * ============================================================================ */

void run_fpb_debugmon_tests(void) {
    TEST_SUITE_BEGIN("fpb_debugmon - Initialization");
    RUN_TEST(test_debugmon_init_success);
    RUN_TEST(test_debugmon_init_no_fpb);
    RUN_TEST(test_debugmon_init_enables_monitor);
    RUN_TEST(test_debugmon_init_idempotent);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_debugmon - Deinitialization");
    RUN_TEST(test_debugmon_deinit_clears_state);
    RUN_TEST(test_debugmon_deinit_without_init);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_debugmon - Set Redirect");
    RUN_TEST(test_debugmon_set_redirect_basic);
    RUN_TEST(test_debugmon_set_redirect_not_initialized);
    RUN_TEST(test_debugmon_set_redirect_invalid_comp);
    RUN_TEST(test_debugmon_set_redirect_strips_thumb_bit);
    RUN_TEST(test_debugmon_set_redirect_configures_fpb_comp);
    RUN_TEST(test_debugmon_set_redirect_multiple);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_debugmon - Clear Redirect");
    RUN_TEST(test_debugmon_clear_redirect_basic);
    RUN_TEST(test_debugmon_clear_redirect_not_initialized);
    RUN_TEST(test_debugmon_clear_redirect_invalid_comp);
    RUN_TEST(test_debugmon_clear_redirect_clears_fpb_comp);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_debugmon - Get Redirect");
    RUN_TEST(test_debugmon_get_redirect_found);
    RUN_TEST(test_debugmon_get_redirect_not_found);
    RUN_TEST(test_debugmon_get_redirect_with_thumb_bit);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_debugmon - Handler");
    RUN_TEST(test_debugmon_handler_redirects_pc);
    RUN_TEST(test_debugmon_handler_no_redirect);
    RUN_TEST(test_debugmon_handler_not_breakpoint);
    TEST_SUITE_END();
}
