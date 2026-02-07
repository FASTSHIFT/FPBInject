/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Tests for func_loader.c - Function loader core
 */

#include "test_framework.h"
#include "mock_hardware.h"
#include "stubs.h"

/* Test context */
static fl_context_t test_ctx;

/* ============================================================================
 * Setup/Teardown
 * ============================================================================ */

static void setup_loader(void) {
    mock_output_reset();
    mock_heap_reset();
    memset(&test_ctx, 0, sizeof(test_ctx));

    test_ctx.output_cb = mock_output_cb;
    test_ctx.output_user = NULL;
    test_ctx.malloc_cb = mock_malloc;
    test_ctx.free_cb = mock_free;
}

/* ============================================================================
 * fl_init Tests
 * ============================================================================ */

void test_loader_init_default(void) {
    fl_context_t ctx;
    memset(&ctx, 0, sizeof(ctx));
    fl_init_default(&ctx);
    /* Should not crash, sets defaults */
}

void test_loader_init_basic(void) {
    setup_loader();
    fl_init(&test_ctx);
    TEST_ASSERT_TRUE(fl_is_inited(&test_ctx));
}

void test_loader_init_clears_slots(void) {
    setup_loader();
    /* Pre-dirty slots */
    for (int i = 0; i < FL_MAX_SLOTS; i++) {
        test_ctx.slots[i].active = true;
        test_ctx.slots[i].orig_addr = 0xDEADBEEF;
    }

    fl_init(&test_ctx);

    for (int i = 0; i < FL_MAX_SLOTS; i++) {
        TEST_ASSERT_FALSE(test_ctx.slots[i].active);
        TEST_ASSERT_EQUAL_HEX(0, test_ctx.slots[i].orig_addr);
    }
}

void test_loader_init_idempotent(void) {
    setup_loader();
    fl_init(&test_ctx);
    fl_init(&test_ctx); /* Second call */
    TEST_ASSERT_TRUE(fl_is_inited(&test_ctx));
}

/* ============================================================================
 * fl_is_inited Tests
 * ============================================================================ */

void test_loader_not_inited(void) {
    fl_context_t ctx;
    memset(&ctx, 0, sizeof(ctx));
    TEST_ASSERT_FALSE(fl_is_inited(&ctx));
}

void test_loader_is_inited_after_init(void) {
    setup_loader();
    fl_init(&test_ctx);
    TEST_ASSERT_TRUE(fl_is_inited(&test_ctx));
}

/* ============================================================================
 * fl_exec_cmd Tests - Basic Commands
 * ============================================================================ */

void test_loader_cmd_help(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"help"};
    int result = fl_exec_cmd(&test_ctx, 1, argv);

    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_TRUE(mock_output_contains("Usage") || mock_output_contains("help"));
}

void test_loader_cmd_info(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"info"};
    int result = fl_exec_cmd(&test_ctx, 1, argv);

    TEST_ASSERT_EQUAL(0, result);
}

void test_loader_cmd_unknown(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"unknown_command"};
    int result = fl_exec_cmd(&test_ctx, 1, argv);

    /* Unknown command should return error */
    TEST_ASSERT(result != 0 || mock_output_contains("Unknown") || mock_output_contains("Error"));
}

void test_loader_cmd_empty(void) {
    setup_loader();
    fl_init(&test_ctx);

    int result = fl_exec_cmd(&test_ctx, 0, NULL);
    /* Empty command should be handled gracefully */
    TEST_ASSERT_EQUAL(0, result);
}

/* ============================================================================
 * fl_exec_cmd Tests - Slot Commands
 * ============================================================================ */

void test_loader_cmd_list_empty(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"list"};
    int result = fl_exec_cmd(&test_ctx, 1, argv);

    TEST_ASSERT_EQUAL(0, result);
}

void test_loader_cmd_clear_invalid_slot(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"clear", "99"};
    int result = fl_exec_cmd(&test_ctx, 2, argv);

    /* Invalid slot should error */
    TEST_ASSERT(result != 0 || mock_output_contains("Invalid") || mock_output_contains("Error"));
}

void test_loader_cmd_clear_valid_slot(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"clear", "0"};
    int result = fl_exec_cmd(&test_ctx, 2, argv);

    /* Should succeed even if slot is empty */
    TEST_ASSERT_EQUAL(0, result);
}

void test_loader_cmd_clearall(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Mark some slots as active */
    test_ctx.slots[0].active = true;
    test_ctx.slots[1].active = true;

    const char* argv[] = {"clearall"};
    int result = fl_exec_cmd(&test_ctx, 1, argv);

    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_FALSE(test_ctx.slots[0].active);
    TEST_ASSERT_FALSE(test_ctx.slots[1].active);
}

/* ============================================================================
 * fl_exec_cmd Tests - Memory Commands
 * ============================================================================ */

void test_loader_cmd_meminfo(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"meminfo"};
    int result = fl_exec_cmd(&test_ctx, 1, argv);

    TEST_ASSERT_EQUAL(0, result);
}

/* ============================================================================
 * Slot State Tests
 * ============================================================================ */

void test_loader_slot_state_initial(void) {
    setup_loader();
    fl_init(&test_ctx);

    for (int i = 0; i < FL_MAX_SLOTS; i++) {
        TEST_ASSERT_FALSE(test_ctx.slots[i].active);
        TEST_ASSERT_EQUAL_HEX(0, test_ctx.slots[i].orig_addr);
        TEST_ASSERT_EQUAL_HEX(0, test_ctx.slots[i].target_addr);
        TEST_ASSERT_EQUAL(0, test_ctx.slots[i].code_size);
    }
}

void test_loader_max_slots(void) {
    TEST_ASSERT_EQUAL(6, FL_MAX_SLOTS);
}

/* ============================================================================
 * Test Runner
 * ============================================================================ */

void run_loader_tests(void) {
    TEST_SUITE_BEGIN("func_loader - Initialization");
    RUN_TEST(test_loader_init_default);
    RUN_TEST(test_loader_init_basic);
    RUN_TEST(test_loader_init_clears_slots);
    RUN_TEST(test_loader_init_idempotent);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - State Checks");
    RUN_TEST(test_loader_not_inited);
    RUN_TEST(test_loader_is_inited_after_init);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Basic Commands");
    RUN_TEST(test_loader_cmd_help);
    RUN_TEST(test_loader_cmd_info);
    RUN_TEST(test_loader_cmd_unknown);
    RUN_TEST(test_loader_cmd_empty);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Slot Commands");
    RUN_TEST(test_loader_cmd_list_empty);
    RUN_TEST(test_loader_cmd_clear_invalid_slot);
    RUN_TEST(test_loader_cmd_clear_valid_slot);
    RUN_TEST(test_loader_cmd_clearall);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Memory Commands");
    RUN_TEST(test_loader_cmd_meminfo);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Slot State");
    RUN_TEST(test_loader_slot_state_initial);
    RUN_TEST(test_loader_max_slots);
    TEST_SUITE_END();
}
