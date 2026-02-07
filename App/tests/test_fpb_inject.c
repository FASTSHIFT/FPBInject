/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Tests for fpb_inject.c - FPB Unit Driver
 */

#include "test_framework.h"
#include "mock_hardware.h"
#include "stubs.h"

/* ============================================================================
 * Setup/Teardown
 * ============================================================================ */

static void setup_fpb(void) {
    mock_fpb_reset();
    fpb_deinit(); /* Ensure clean state */
}

/* ============================================================================
 * fpb_init/deinit Tests
 * ============================================================================ */

void test_fpb_init_success(void) {
    setup_fpb();

    int result = fpb_init();
    TEST_ASSERT_EQUAL(0, result);
}

void test_fpb_init_enables_fpb(void) {
    setup_fpb();

    fpb_init();

    /* Check FPB_CTRL ENABLE bit is set */
    TEST_ASSERT_TRUE(mock_fpb_regs.ctrl & 0x01);
}

void test_fpb_init_sets_key(void) {
    setup_fpb();

    fpb_init();

    /* Check KEY bit (bit 1) was written */
    TEST_ASSERT_TRUE(mock_fpb_regs.ctrl & 0x02);
}

void test_fpb_deinit_disables_fpb(void) {
    setup_fpb();
    fpb_init();

    fpb_deinit();

    /* Check ENABLE bit is cleared */
    TEST_ASSERT_FALSE(mock_fpb_regs.ctrl & 0x01);
}

void test_fpb_deinit_clears_comparators(void) {
    setup_fpb();
    fpb_init();

    /* Set up a patch */
    fpb_set_patch(0, 0x08000100, 0x20001000);

    fpb_deinit();

    /* All comparators should be cleared */
    for (int i = 0; i < FPB_MAX_CODE_COMP; i++) {
        TEST_ASSERT_EQUAL_HEX(0, mock_fpb_regs.comp[i]);
    }
}

void test_fpb_init_twice(void) {
    setup_fpb();

    fpb_init();
    int result = fpb_init();

    /* Should succeed or return already-initialized */
    TEST_ASSERT(result == 0 || result == 1);
}

/* ============================================================================
 * fpb_set_patch Tests
 * ============================================================================ */

void test_fpb_set_patch_success(void) {
    setup_fpb();
    fpb_init();

    int result = fpb_set_patch(0, 0x08000100, 0x20001000);

    TEST_ASSERT_EQUAL(0, result);
}

void test_fpb_set_patch_enables_comparator(void) {
    setup_fpb();
    fpb_init();

    fpb_set_patch(0, 0x08000100, 0x20001000);

    /* Check ENABLE bit in comparator register */
    TEST_ASSERT_TRUE(mock_fpb_regs.comp[0] & 0x01);
}

void test_fpb_set_patch_stores_address(void) {
    setup_fpb();
    fpb_init();

    fpb_set_patch(0, 0x08000100, 0x20001000);

    /* Check address is stored (bits 28:2 = address bits 28:2) */
    uint32_t stored_addr = (mock_fpb_regs.comp[0] & 0x1FFFFFFC);
    TEST_ASSERT_EQUAL_HEX(0x08000100, stored_addr);
}

void test_fpb_set_patch_invalid_comp_id(void) {
    setup_fpb();
    fpb_init();

    int result = fpb_set_patch(FPB_MAX_CODE_COMP, 0x08000100, 0x20001000);

    TEST_ASSERT_EQUAL(-1, result);
}

void test_fpb_set_patch_invalid_address_range(void) {
    setup_fpb();
    fpb_init();

    /* Address outside code region (>= 0x20000000) */
    int result = fpb_set_patch(0, 0x40000000, 0x20001000);

    TEST_ASSERT_EQUAL(-1, result);
}

void test_fpb_set_patch_all_comparators(void) {
    setup_fpb();
    fpb_init();

    for (int i = 0; i < FPB_MAX_CODE_COMP; i++) {
        int result = fpb_set_patch(i, 0x08000100 + (i * 4), 0x20001000 + (i * 0x100));
        TEST_ASSERT_EQUAL(0, result);
    }
}

void test_fpb_set_patch_unaligned_address(void) {
    setup_fpb();
    fpb_init();

    /* Unaligned address (not word-aligned) */
    int result = fpb_set_patch(0, 0x08000101, 0x20001000);

    /* Should handle alignment appropriately */
    TEST_ASSERT(result == 0 || result == -1);
}

/* ============================================================================
 * fpb_clear_patch Tests
 * ============================================================================ */

void test_fpb_clear_patch_success(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08000100, 0x20001000);

    int result = fpb_clear_patch(0);

    TEST_ASSERT_EQUAL(0, result);
}

void test_fpb_clear_patch_disables_comparator(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08000100, 0x20001000);

    fpb_clear_patch(0);

    /* Check ENABLE bit is cleared */
    TEST_ASSERT_FALSE(mock_fpb_regs.comp[0] & 0x01);
}

void test_fpb_clear_patch_invalid_comp_id(void) {
    setup_fpb();
    fpb_init();

    int result = fpb_clear_patch(FPB_MAX_CODE_COMP);

    TEST_ASSERT_EQUAL(-1, result);
}

void test_fpb_clear_patch_already_cleared(void) {
    setup_fpb();
    fpb_init();

    /* Clear without setting first */
    int result = fpb_clear_patch(0);

    /* Should succeed */
    TEST_ASSERT_EQUAL(0, result);
}

/* ============================================================================
 * fpb_enable_comp Tests
 * ============================================================================ */

void test_fpb_enable_comp_enable(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08000100, 0x20001000);
    fpb_enable_comp(0, false); /* Disable first */

    int result = fpb_enable_comp(0, true);

    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_TRUE(mock_fpb_regs.comp[0] & 0x01);
}

void test_fpb_enable_comp_disable(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08000100, 0x20001000);

    int result = fpb_enable_comp(0, false);

    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_FALSE(mock_fpb_regs.comp[0] & 0x01);
}

void test_fpb_enable_comp_invalid_id(void) {
    setup_fpb();
    fpb_init();

    int result = fpb_enable_comp(FPB_MAX_CODE_COMP, true);

    TEST_ASSERT_EQUAL(-1, result);
}

/* ============================================================================
 * fpb_get_state Tests
 * ============================================================================ */

void test_fpb_get_state_not_null(void) {
    setup_fpb();
    fpb_init();

    const fpb_state_t* state = fpb_get_state();

    TEST_ASSERT(state != NULL);
}

void test_fpb_get_state_initialized(void) {
    setup_fpb();
    fpb_init();

    const fpb_state_t* state = fpb_get_state();

    TEST_ASSERT_TRUE(state->initialized);
}

void test_fpb_get_state_comp_count(void) {
    setup_fpb();
    fpb_init();

    const fpb_state_t* state = fpb_get_state();

    TEST_ASSERT_EQUAL(FPB_MAX_CODE_COMP, state->num_code_comp);
}

void test_fpb_get_state_reflects_patch(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08000100, 0x20001000);

    const fpb_state_t* state = fpb_get_state();

    TEST_ASSERT_TRUE(state->comp[0].enabled);
    TEST_ASSERT_EQUAL_HEX(0x08000100, state->comp[0].original_addr);
}

/* ============================================================================
 * fpb_is_supported Tests
 * ============================================================================ */

void test_fpb_is_supported(void) {
    setup_fpb();

    bool supported = fpb_is_supported();

    /* Mock always supports FPB */
    TEST_ASSERT_TRUE(supported);
}

/* ============================================================================
 * fpb_get_num_code_comp Tests
 * ============================================================================ */

void test_fpb_get_num_code_comp(void) {
    setup_fpb();
    fpb_init();

    uint8_t count = fpb_get_num_code_comp();

    TEST_ASSERT_EQUAL(FPB_MAX_CODE_COMP, count);
}

/* ============================================================================
 * fpb_set_instruction_patch Tests
 * ============================================================================ */

void test_fpb_set_instruction_patch_lower(void) {
    setup_fpb();
    fpb_init();

    /* Patch lower halfword */
    int result = fpb_set_instruction_patch(0, 0x08000100, 0xBEEF, false);

    TEST_ASSERT_EQUAL(0, result);
}

void test_fpb_set_instruction_patch_upper(void) {
    setup_fpb();
    fpb_init();

    /* Patch upper halfword */
    int result = fpb_set_instruction_patch(0, 0x08000100, 0xDEAD, true);

    TEST_ASSERT_EQUAL(0, result);
}

void test_fpb_set_instruction_patch_invalid_id(void) {
    setup_fpb();
    fpb_init();

    int result = fpb_set_instruction_patch(FPB_MAX_CODE_COMP, 0x08000100, 0xBEEF, false);

    TEST_ASSERT_EQUAL(-1, result);
}

/* ============================================================================
 * fpb_generate_thumb_jump Tests
 * ============================================================================ */

void test_fpb_generate_thumb_jump_short(void) {
    setup_fpb();
    fpb_init();

    uint8_t instruction[4] = {0};

    /* Short jump (within ±2KB) */
    uint8_t len = fpb_generate_thumb_jump(0x08000100, 0x08000200, instruction);

    /* Should be 2-byte B instruction or 4-byte B.W */
    TEST_ASSERT(len == 2 || len == 4);
}

void test_fpb_generate_thumb_jump_long(void) {
    setup_fpb();
    fpb_init();

    uint8_t instruction[4] = {0};

    /* Long jump (beyond ±2KB) */
    uint8_t len = fpb_generate_thumb_jump(0x08000100, 0x08010000, instruction);

    /* Should be 4-byte instruction */
    TEST_ASSERT_EQUAL(4, len);
}

void test_fpb_generate_thumb_jump_backward(void) {
    setup_fpb();
    fpb_init();

    uint8_t instruction[4] = {0};

    /* Backward jump */
    uint8_t len = fpb_generate_thumb_jump(0x08000200, 0x08000100, instruction);

    TEST_ASSERT(len == 2 || len == 4);
}

/* ============================================================================
 * Test Runner
 * ============================================================================ */

void run_fpb_inject_tests(void) {
    TEST_SUITE_BEGIN("fpb_inject - Init/Deinit");
    RUN_TEST(test_fpb_init_success);
    RUN_TEST(test_fpb_init_enables_fpb);
    RUN_TEST(test_fpb_init_sets_key);
    RUN_TEST(test_fpb_deinit_disables_fpb);
    RUN_TEST(test_fpb_deinit_clears_comparators);
    RUN_TEST(test_fpb_init_twice);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Set Patch");
    RUN_TEST(test_fpb_set_patch_success);
    RUN_TEST(test_fpb_set_patch_enables_comparator);
    RUN_TEST(test_fpb_set_patch_stores_address);
    RUN_TEST(test_fpb_set_patch_invalid_comp_id);
    RUN_TEST(test_fpb_set_patch_invalid_address_range);
    RUN_TEST(test_fpb_set_patch_all_comparators);
    RUN_TEST(test_fpb_set_patch_unaligned_address);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Clear Patch");
    RUN_TEST(test_fpb_clear_patch_success);
    RUN_TEST(test_fpb_clear_patch_disables_comparator);
    RUN_TEST(test_fpb_clear_patch_invalid_comp_id);
    RUN_TEST(test_fpb_clear_patch_already_cleared);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Enable/Disable Comparator");
    RUN_TEST(test_fpb_enable_comp_enable);
    RUN_TEST(test_fpb_enable_comp_disable);
    RUN_TEST(test_fpb_enable_comp_invalid_id);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - State Query");
    RUN_TEST(test_fpb_get_state_not_null);
    RUN_TEST(test_fpb_get_state_initialized);
    RUN_TEST(test_fpb_get_state_comp_count);
    RUN_TEST(test_fpb_get_state_reflects_patch);
    RUN_TEST(test_fpb_is_supported);
    RUN_TEST(test_fpb_get_num_code_comp);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Instruction Patch");
    RUN_TEST(test_fpb_set_instruction_patch_lower);
    RUN_TEST(test_fpb_set_instruction_patch_upper);
    RUN_TEST(test_fpb_set_instruction_patch_invalid_id);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Thumb Jump Generation");
    RUN_TEST(test_fpb_generate_thumb_jump_short);
    RUN_TEST(test_fpb_generate_thumb_jump_long);
    RUN_TEST(test_fpb_generate_thumb_jump_backward);
    TEST_SUITE_END();
}
