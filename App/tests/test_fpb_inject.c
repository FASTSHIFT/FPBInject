/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Tests for fpb_inject.c - FPB Unit Driver
 */

#include "test_framework.h"
#include "mock_hardware.h"
#include "fpb_mock_regs.h"
#include "fpb_inject.h"

/* ============================================================================
 * Setup/Teardown
 * ============================================================================ */

static void setup_fpb(void) {
    fpb_deinit();             /* Ensure clean state */
    fpb_mock_configure(6, 2); /* Configure 6 code + 2 literal comparators */
}

/* ============================================================================
 * fpb_init Tests
 * ============================================================================ */

void test_fpb_init_success(void) {
    setup_fpb();
    int ret = fpb_init();
    TEST_ASSERT_EQUAL(0, ret);
}

void test_fpb_init_idempotent(void) {
    setup_fpb();
    int ret1 = fpb_init();
    int ret2 = fpb_init();
    TEST_ASSERT_EQUAL(0, ret1);
    TEST_ASSERT_EQUAL(0, ret2);
}

void test_fpb_init_enables_fpb(void) {
    setup_fpb();
    fpb_init();
    TEST_ASSERT_TRUE(mock_fpb_is_enabled());
}

void test_fpb_init_no_comparators(void) {
    setup_fpb();
    fpb_mock_configure(0, 0);
    int ret = fpb_init();
    TEST_ASSERT(ret != 0); /* Should fail with no comparators */
}

/* ============================================================================
 * fpb_deinit Tests
 * ============================================================================ */

void test_fpb_deinit_basic(void) {
    setup_fpb();
    fpb_init();
    fpb_deinit();
    /* Should not crash, state should be cleared */
}

void test_fpb_deinit_disables_fpb(void) {
    setup_fpb();
    fpb_init();
    fpb_deinit();
    TEST_ASSERT_FALSE(mock_fpb_is_enabled());
}

void test_fpb_deinit_clears_comparators(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08001000, 0x20002000);
    fpb_deinit();

    for (int i = 0; i < 8; i++) {
        TEST_ASSERT_FALSE(mock_fpb_comp_is_enabled(i));
    }
}

/* ============================================================================
 * fpb_set_patch Tests
 * ============================================================================ */

void test_fpb_set_patch_basic(void) {
    setup_fpb();
    fpb_init();

    int ret = fpb_set_patch(0, 0x08001000, 0x20002000);
    TEST_ASSERT_EQUAL(0, ret);
}

void test_fpb_set_patch_enables_comparator(void) {
    setup_fpb();
    fpb_init();

    fpb_set_patch(0, 0x08001000, 0x20002000);
    TEST_ASSERT_TRUE(mock_fpb_comp_is_enabled(0));
}

void test_fpb_set_patch_invalid_comp(void) {
    setup_fpb();
    fpb_init();

    int ret = fpb_set_patch(99, 0x08001000, 0x20002000);
    TEST_ASSERT(ret != 0);
}

void test_fpb_set_patch_not_initialized(void) {
    setup_fpb();
    /* Don't call fpb_init() */

    int ret = fpb_set_patch(0, 0x08001000, 0x20002000);
    TEST_ASSERT(ret != 0);
}

void test_fpb_set_patch_ram_address(void) {
    setup_fpb();
    fpb_init();

    /* Original address in RAM region should fail */
    int ret = fpb_set_patch(0, 0x20001000, 0x20002000);
    TEST_ASSERT(ret != 0);
}

void test_fpb_set_patch_multiple(void) {
    setup_fpb();
    fpb_init();

    TEST_ASSERT_EQUAL(0, fpb_set_patch(0, 0x08001000, 0x20002000));
    TEST_ASSERT_EQUAL(0, fpb_set_patch(1, 0x08002000, 0x20003000));
    TEST_ASSERT_EQUAL(0, fpb_set_patch(2, 0x08003000, 0x20004000));
}

/* ============================================================================
 * fpb_clear_patch Tests
 * ============================================================================ */

void test_fpb_clear_patch_basic(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08001000, 0x20002000);

    int ret = fpb_clear_patch(0);
    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT_FALSE(mock_fpb_comp_is_enabled(0));
}

void test_fpb_clear_patch_invalid_comp(void) {
    setup_fpb();
    fpb_init();

    int ret = fpb_clear_patch(99);
    TEST_ASSERT(ret != 0);
}

void test_fpb_clear_patch_not_set(void) {
    setup_fpb();
    fpb_init();

    /* Clearing unset patch should be OK */
    int ret = fpb_clear_patch(0);
    TEST_ASSERT_EQUAL(0, ret);
}

/* ============================================================================
 * fpb_enable_comp Tests
 * ============================================================================ */

void test_fpb_enable_comp_enable(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08001000, 0x20002000);
    fpb_enable_comp(0, false);

    int ret = fpb_enable_comp(0, true);
    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT_TRUE(mock_fpb_comp_is_enabled(0));
}

void test_fpb_enable_comp_disable(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08001000, 0x20002000);

    int ret = fpb_enable_comp(0, false);
    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT_FALSE(mock_fpb_comp_is_enabled(0));
}

void test_fpb_enable_comp_invalid(void) {
    setup_fpb();
    fpb_init();

    int ret = fpb_enable_comp(99, true);
    TEST_ASSERT(ret != 0);
}

/* ============================================================================
 * fpb_get_state Tests
 * ============================================================================ */

void test_fpb_get_state_basic(void) {
    setup_fpb();
    fpb_init();

    const fpb_state_t* state = fpb_get_state();
    TEST_ASSERT_NOT_NULL(state);
    TEST_ASSERT_TRUE(state->initialized);
}

void test_fpb_get_state_num_comp(void) {
    setup_fpb();
    fpb_init();

    const fpb_state_t* state = fpb_get_state();
    TEST_ASSERT_EQUAL(6, state->num_code_comp);
    TEST_ASSERT_EQUAL(2, state->num_lit_comp);
}

void test_fpb_get_state_after_patch(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08001000, 0x20002000);

    const fpb_state_t* state = fpb_get_state();
    TEST_ASSERT_TRUE(state->comp[0].enabled);
    TEST_ASSERT_EQUAL_HEX(0x08001000, state->comp[0].original_addr);
}

/* ============================================================================
 * fpb_is_supported Tests
 * ============================================================================ */

void test_fpb_is_supported_with_comps(void) {
    setup_fpb();
    fpb_init();
    TEST_ASSERT_TRUE(fpb_is_supported());
}

/* ============================================================================
 * fpb_get_num_code_comp Tests
 * ============================================================================ */

void test_fpb_get_num_code_comp(void) {
    setup_fpb();
    fpb_init();
    TEST_ASSERT_EQUAL(6, fpb_get_num_code_comp());
}

/* ============================================================================
 * fpb_get_info Tests
 * ============================================================================ */

void test_fpb_get_info_basic(void) {
    setup_fpb();
    fpb_init();

    fpb_info_t info;
    int ret = fpb_get_info(&info);
    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT_NOT_NULL(&info);
}

void test_fpb_get_info_num_comp(void) {
    setup_fpb();
    fpb_init();

    fpb_info_t info;
    fpb_get_info(&info);
    TEST_ASSERT_EQUAL(6, info.num_code_comp);
    TEST_ASSERT_EQUAL(2, info.num_lit_comp);
    TEST_ASSERT_EQUAL(8, info.total_comp);
}

void test_fpb_get_info_enabled(void) {
    setup_fpb();
    fpb_init();

    fpb_info_t info;
    fpb_get_info(&info);
    TEST_ASSERT_TRUE(info.enabled);
}

void test_fpb_get_info_disabled(void) {
    setup_fpb();
    fpb_init();
    fpb_deinit();

    fpb_info_t info;
    int ret = fpb_get_info(&info);
    /* Should still succeed, but FPB is disabled */
    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT_FALSE(info.enabled); /* FPB should be disabled after deinit */
}

void test_fpb_get_info_null_pointer(void) {
    setup_fpb();
    fpb_init();

    int ret = fpb_get_info(NULL);
    TEST_ASSERT(ret != 0);
}

void test_fpb_get_info_revision(void) {
    setup_fpb();
    fpb_init();

    fpb_info_t info;
    fpb_get_info(&info);
    /* STM32F103 has FPB v1 */
    TEST_ASSERT_EQUAL(0, info.rev);
}

/* ============================================================================
 * fpb_generate_thumb_jump Tests
 * ============================================================================ */

void test_fpb_generate_thumb_jump_short(void) {
    uint8_t instr[4];
    uint8_t len = fpb_generate_thumb_jump(0x08001000, 0x08001100, instr);
    TEST_ASSERT(len == 2 || len == 4);
}

void test_fpb_generate_thumb_jump_long(void) {
    uint8_t instr[4];
    uint8_t len = fpb_generate_thumb_jump(0x08001000, 0x08100000, instr);
    TEST_ASSERT_EQUAL(4, len);
}

void test_fpb_generate_thumb_jump_backward(void) {
    uint8_t instr[4];
    uint8_t len = fpb_generate_thumb_jump(0x08001100, 0x08001000, instr);
    TEST_ASSERT(len == 2 || len == 4);
}

/* ============================================================================
 * fpb_set_instruction_patch Tests
 * ============================================================================ */

void test_fpb_set_instruction_patch_basic(void) {
    setup_fpb();
    fpb_init();

    int ret = fpb_set_instruction_patch(0, 0x08001000, 0x4770, false); /* BX LR */
    TEST_ASSERT_EQUAL(0, ret);
}

void test_fpb_set_instruction_patch_upper(void) {
    setup_fpb();
    fpb_init();

    int ret = fpb_set_instruction_patch(0, 0x08001000, 0x4770, true); /* Upper half */
    TEST_ASSERT_EQUAL(0, ret);
}

void test_fpb_set_instruction_patch_not_initialized(void) {
    setup_fpb();
    /* Don't init FPB */

    int ret = fpb_set_instruction_patch(0, 0x08001000, 0x4770, false);
    TEST_ASSERT(ret != 0);
}

void test_fpb_set_instruction_patch_invalid_comp(void) {
    setup_fpb();
    fpb_init();

    int ret = fpb_set_instruction_patch(100, 0x08001000, 0x4770, false);
    TEST_ASSERT(ret != 0);
}

void test_fpb_set_instruction_patch_ram_address(void) {
    setup_fpb();
    fpb_init();

    /* RAM address should fail */
    int ret = fpb_set_instruction_patch(0, 0x20001000, 0x4770, false);
    TEST_ASSERT(ret != 0);
}

/* ============================================================================
 * Test Runner
 * ============================================================================ */

void run_fpb_tests(void) {
    TEST_SUITE_BEGIN("fpb_inject - Initialization");
    RUN_TEST(test_fpb_init_success);
    RUN_TEST(test_fpb_init_idempotent);
    RUN_TEST(test_fpb_init_enables_fpb);
    RUN_TEST(test_fpb_init_no_comparators);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Deinitialization");
    RUN_TEST(test_fpb_deinit_basic);
    RUN_TEST(test_fpb_deinit_disables_fpb);
    RUN_TEST(test_fpb_deinit_clears_comparators);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Set Patch");
    RUN_TEST(test_fpb_set_patch_basic);
    RUN_TEST(test_fpb_set_patch_enables_comparator);
    RUN_TEST(test_fpb_set_patch_invalid_comp);
    RUN_TEST(test_fpb_set_patch_not_initialized);
    RUN_TEST(test_fpb_set_patch_ram_address);
    RUN_TEST(test_fpb_set_patch_multiple);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Clear Patch");
    RUN_TEST(test_fpb_clear_patch_basic);
    RUN_TEST(test_fpb_clear_patch_invalid_comp);
    RUN_TEST(test_fpb_clear_patch_not_set);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Enable/Disable");
    RUN_TEST(test_fpb_enable_comp_enable);
    RUN_TEST(test_fpb_enable_comp_disable);
    RUN_TEST(test_fpb_enable_comp_invalid);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - State Query");
    RUN_TEST(test_fpb_get_state_basic);
    RUN_TEST(test_fpb_get_state_num_comp);
    RUN_TEST(test_fpb_get_state_after_patch);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Support Query");
    RUN_TEST(test_fpb_is_supported_with_comps);
    RUN_TEST(test_fpb_get_num_code_comp);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Device Info");
    RUN_TEST(test_fpb_get_info_basic);
    RUN_TEST(test_fpb_get_info_num_comp);
    RUN_TEST(test_fpb_get_info_enabled);
    RUN_TEST(test_fpb_get_info_disabled);
    RUN_TEST(test_fpb_get_info_null_pointer);
    RUN_TEST(test_fpb_get_info_revision);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Thumb Jump Generation");
    RUN_TEST(test_fpb_generate_thumb_jump_short);
    RUN_TEST(test_fpb_generate_thumb_jump_long);
    RUN_TEST(test_fpb_generate_thumb_jump_backward);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Instruction Patch");
    RUN_TEST(test_fpb_set_instruction_patch_basic);
    RUN_TEST(test_fpb_set_instruction_patch_upper);
    RUN_TEST(test_fpb_set_instruction_patch_not_initialized);
    RUN_TEST(test_fpb_set_instruction_patch_invalid_comp);
    RUN_TEST(test_fpb_set_instruction_patch_ram_address);
    TEST_SUITE_END();
}
