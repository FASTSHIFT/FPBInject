/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Unit tests for FL_NO_FPB mode
 *
 * When FL_NO_FPB is defined at compile time, all FPB-dependent commands
 * (patch/tpatch/dpatch/unpatch/enable) should return FL_ERR_DISABLED and
 * print "FPB disabled (FL_NO_FPB)". The info command should print
 * "FPB: disabled (FL_NO_FPB)".
 *
 * This test file is compiled WITH -DFL_NO_FPB to exercise the stub branch.
 */

#include "test_framework.h"
#include "mock_hardware.h"
#include "fl.h"
#include "fl_cmd.h"
#include "fl_error.h"
#include <string.h>

/* ============================================================================
 * Test Context
 * ============================================================================ */

static fl_context_t test_ctx;

static void setup_no_fpb(void) {
    mock_output_reset();
    mock_heap_reset();
    memset(&test_ctx, 0, sizeof(test_ctx));

    test_ctx.output_cb = mock_output_cb;
    test_ctx.output_user = NULL;
    test_ctx.malloc_cb = mock_malloc;
    test_ctx.free_cb = mock_free;

    fl_log_init(test_ctx.output_cb, test_ctx.output_user);
    test_ctx.is_inited = true;
}

/* ============================================================================
 * Helper: build args and exec a command
 * ============================================================================ */

static fl_error_t exec_simple_cmd(const char* cmd) {
    const char* argv[] = {"fl", "--cmd", cmd};
    return fl_exec_cmd(&test_ctx, 3, argv);
}

static fl_error_t exec_patch_cmd(const char* cmd) {
    const char* argv[] = {"fl", "--cmd", cmd, "--comp", "0", "--orig", "0x08001000", "--target", "0x20001000"};
    return fl_exec_cmd(&test_ctx, 9, argv);
}

static fl_error_t exec_comp_cmd(const char* cmd) {
    const char* argv[] = {"fl", "--cmd", cmd, "--comp", "0"};
    return fl_exec_cmd(&test_ctx, 5, argv);
}

static fl_error_t exec_enable_cmd(const char* cmd) {
    const char* argv[] = {"fl", "--cmd", cmd, "--comp", "0", "--enable", "1"};
    return fl_exec_cmd(&test_ctx, 7, argv);
}

/* ============================================================================
 * Patch Command Tests
 * ============================================================================ */

static void assert_cmd_disabled(const char* cmd, fl_error_t (*exec)(const char*)) {
    setup_no_fpb();
    fl_error_t ret = exec(cmd);
    TEST_ASSERT_EQUAL(FL_ERR_DISABLED, ret);
    TEST_ASSERT_TRUE(mock_output_contains("[FLERR]"));
    TEST_ASSERT_TRUE(mock_output_contains("FPB disabled"));
}

static void test_no_fpb_patch_returns_disabled(void) {
    assert_cmd_disabled("patch", exec_patch_cmd);
}

static void test_no_fpb_tpatch_returns_disabled(void) {
    assert_cmd_disabled("tpatch", exec_patch_cmd);
}

static void test_no_fpb_dpatch_returns_disabled(void) {
    assert_cmd_disabled("dpatch", exec_patch_cmd);
}

static void test_no_fpb_unpatch_returns_disabled(void) {
    assert_cmd_disabled("unpatch", exec_comp_cmd);
}

static void test_no_fpb_enable_returns_disabled(void) {
    assert_cmd_disabled("enable", exec_enable_cmd);
}

/* ============================================================================
 * Info Command Tests
 * ============================================================================ */

static void test_no_fpb_info_shows_disabled(void) {
    setup_no_fpb();
    exec_simple_cmd("info");
    TEST_ASSERT_TRUE(mock_output_contains("FPB: disabled"));
}

/* ============================================================================
 * Non-FPB Commands Still Work
 * ============================================================================ */

static void test_no_fpb_ping_still_works(void) {
    setup_no_fpb();
    fl_error_t ret = exec_simple_cmd("ping");
    TEST_ASSERT_EQUAL(FL_OK, ret);
    TEST_ASSERT_TRUE(mock_output_contains("[FLOK]"));
    TEST_ASSERT_TRUE(mock_output_contains("PONG"));
}

static void test_no_fpb_echo_still_works(void) {
    setup_no_fpb();
    const char* argv[] = {"fl", "--cmd", "echo", "-d", "AABB"};
    fl_error_t ret = fl_exec_cmd(&test_ctx, 5, argv);
    TEST_ASSERT_EQUAL(FL_OK, ret);
    TEST_ASSERT_TRUE(mock_output_contains("[FLOK]"));
}

static void test_no_fpb_alloc_still_works(void) {
    setup_no_fpb();
    const char* argv[] = {"fl", "--cmd", "alloc", "-s", "256"};
    fl_error_t ret = fl_exec_cmd(&test_ctx, 5, argv);
    TEST_ASSERT_EQUAL(FL_OK, ret);
    TEST_ASSERT_TRUE(mock_output_contains("[FLOK]"));
}

/* ============================================================================
 * Test Runner
 * ============================================================================ */

void run_no_fpb_tests(void) {
    TEST_SUITE_BEGIN("FL_NO_FPB - patch commands return disabled");
    RUN_TEST(test_no_fpb_patch_returns_disabled);
    RUN_TEST(test_no_fpb_tpatch_returns_disabled);
    RUN_TEST(test_no_fpb_dpatch_returns_disabled);
    RUN_TEST(test_no_fpb_unpatch_returns_disabled);
    RUN_TEST(test_no_fpb_enable_returns_disabled);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("FL_NO_FPB - info shows disabled");
    RUN_TEST(test_no_fpb_info_shows_disabled);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("FL_NO_FPB - non-FPB commands still work");
    RUN_TEST(test_no_fpb_ping_still_works);
    RUN_TEST(test_no_fpb_echo_still_works);
    RUN_TEST(test_no_fpb_alloc_still_works);
    TEST_SUITE_END();
}

/* ============================================================================
 * Main Entry Point
 * ============================================================================ */

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    printf("\n");
    printf("============================================================\n");
    printf("  FPBInject FL_NO_FPB Mode Unit Tests                       \n");
    printf("============================================================\n");
    printf("\n");

    test_framework_init();

    run_no_fpb_tests();

    return test_framework_report();
}
