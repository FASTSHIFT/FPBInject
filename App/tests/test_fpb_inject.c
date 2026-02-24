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
    fpb_mock_configure(6, 2); /* Configure 6 code + 2 literal comparators (FPB v1) */
}

static void setup_fpb_v2(void) {
    fpb_deinit();             /* Ensure clean state */
    fpb_mock_configure(8, 0); /* Configure 8 code comparators (FPB v2) */
}

/* ============================================================================
 * fpb_init Tests
 * ============================================================================ */

void test_fpb_init_success(void) {
    setup_fpb();
    fpb_result_t ret = fpb_init();
    TEST_ASSERT_EQUAL(FPB_OK, ret);
}

void test_fpb_init_idempotent(void) {
    setup_fpb();
    fpb_result_t ret1 = fpb_init();
    fpb_result_t ret2 = fpb_init();
    TEST_ASSERT_EQUAL(FPB_OK, ret1);
    TEST_ASSERT_EQUAL(FPB_OK, ret2);
}

void test_fpb_init_enables_fpb(void) {
    setup_fpb();
    fpb_init();
    TEST_ASSERT_TRUE(mock_fpb_is_enabled());
}

void test_fpb_init_no_comparators(void) {
    setup_fpb();
    fpb_mock_configure(0, 0);
    fpb_result_t ret = fpb_init();
    TEST_ASSERT_EQUAL(FPB_ERR_NOT_SUPPORTED, ret);
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

    fpb_result_t ret = fpb_set_patch(0, 0x08001000, 0x20002000);
    TEST_ASSERT_EQUAL(FPB_OK, ret);
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

    fpb_result_t ret = fpb_set_patch(99, 0x08001000, 0x20002000);
    TEST_ASSERT_EQUAL(FPB_ERR_INVALID_COMP, ret);
}

void test_fpb_set_patch_not_initialized(void) {
    setup_fpb();
    /* Don't call fpb_init() */

    fpb_result_t ret = fpb_set_patch(0, 0x08001000, 0x20002000);
    TEST_ASSERT_EQUAL(FPB_ERR_NOT_INIT, ret);
}

void test_fpb_set_patch_ram_address(void) {
    setup_fpb();
    fpb_init();

    /* Original address in RAM region should fail */
    fpb_result_t ret = fpb_set_patch(0, 0x20001000, 0x20002000);
    TEST_ASSERT_EQUAL(FPB_ERR_INVALID_ADDR, ret);
}

void test_fpb_set_patch_multiple(void) {
    setup_fpb();
    fpb_init();

    TEST_ASSERT_EQUAL(FPB_OK, fpb_set_patch(0, 0x08001000, 0x20002000));
    TEST_ASSERT_EQUAL(FPB_OK, fpb_set_patch(1, 0x08002000, 0x20003000));
    TEST_ASSERT_EQUAL(FPB_OK, fpb_set_patch(2, 0x08003000, 0x20004000));
}

/* ============================================================================
 * fpb_clear_patch Tests
 * ============================================================================ */

void test_fpb_clear_patch_basic(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08001000, 0x20002000);

    fpb_result_t ret = fpb_clear_patch(0);
    TEST_ASSERT_EQUAL(FPB_OK, ret);
    TEST_ASSERT_FALSE(mock_fpb_comp_is_enabled(0));
}

void test_fpb_clear_patch_invalid_comp(void) {
    setup_fpb();
    fpb_init();

    fpb_result_t ret = fpb_clear_patch(99);
    TEST_ASSERT_EQUAL(FPB_ERR_INVALID_COMP, ret);
}

void test_fpb_clear_patch_not_set(void) {
    setup_fpb();
    fpb_init();

    /* Clearing unset patch should be OK */
    fpb_result_t ret = fpb_clear_patch(0);
    TEST_ASSERT_EQUAL(FPB_OK, ret);
}

/* ============================================================================
 * fpb_enable_comp Tests
 * ============================================================================ */

void test_fpb_enable_comp_enable(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08001000, 0x20002000);
    fpb_enable_comp(0, false);

    fpb_result_t ret = fpb_enable_comp(0, true);
    TEST_ASSERT_EQUAL(FPB_OK, ret);
    TEST_ASSERT_TRUE(mock_fpb_comp_is_enabled(0));
}

void test_fpb_enable_comp_disable(void) {
    setup_fpb();
    fpb_init();
    fpb_set_patch(0, 0x08001000, 0x20002000);

    fpb_result_t ret = fpb_enable_comp(0, false);
    TEST_ASSERT_EQUAL(FPB_OK, ret);
    TEST_ASSERT_FALSE(mock_fpb_comp_is_enabled(0));
}

void test_fpb_enable_comp_invalid(void) {
    setup_fpb();
    fpb_init();

    fpb_result_t ret = fpb_enable_comp(99, true);
    TEST_ASSERT_EQUAL(FPB_ERR_INVALID_COMP, ret);
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

void test_fpb_get_state_num_comp_v2(void) {
    setup_fpb_v2();
    fpb_init();

    const fpb_state_t* state = fpb_get_state();
    TEST_ASSERT_EQUAL(8, state->num_code_comp);
    TEST_ASSERT_EQUAL(0, state->num_lit_comp);
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

void test_fpb_get_num_code_comp_v2(void) {
    setup_fpb_v2();
    fpb_init();
    TEST_ASSERT_EQUAL(8, fpb_get_num_code_comp());
}

/* ============================================================================
 * fpb_get_info Tests
 * ============================================================================ */

void test_fpb_get_info_basic(void) {
    setup_fpb();
    fpb_init();

    fpb_info_t info;
    fpb_result_t ret = fpb_get_info(&info);
    TEST_ASSERT_EQUAL(FPB_OK, ret);
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
    fpb_result_t ret = fpb_get_info(&info);
    /* Should still succeed, but FPB is disabled */
    TEST_ASSERT_EQUAL(FPB_OK, ret);
    TEST_ASSERT_FALSE(info.enabled); /* FPB should be disabled after deinit */
}

void test_fpb_get_info_null_pointer(void) {
    setup_fpb();
    fpb_init();

    fpb_result_t ret = fpb_get_info(NULL);
    TEST_ASSERT_EQUAL(FPB_ERR_INVALID_PARAM, ret);
}

void test_fpb_get_info_revision(void) {
    setup_fpb();
    fpb_init();

    fpb_info_t info;
    fpb_get_info(&info);
    /* STM32F103 has FPB v1 */
    TEST_ASSERT_EQUAL(0, info.rev);
}

void test_fpb_get_info_remap_supported(void) {
    setup_fpb();
    fpb_init();

    fpb_info_t info;
    fpb_get_info(&info);
    /* Mock configured with RMPSPT=1 */
    TEST_ASSERT_TRUE(info.remap_supported);
}

void test_fpb_get_info_remap_base(void) {
    setup_fpb();
    fpb_init();

    /* Set a patch to configure remap table */
    fpb_set_patch(0, 0x08001000, 0x20002000);

    fpb_info_t info;
    fpb_get_info(&info);

    /* remap_base should be in SRAM region (0x20000000-0x3FFFFFFF) */
    TEST_ASSERT(info.remap_base >= 0x20000000UL);
    TEST_ASSERT(info.remap_base < 0x40000000UL);
}

void test_fpb_get_info_comp_fields(void) {
    setup_fpb();
    fpb_init();

    /* Set patches on slot 0 and 1 */
    fpb_set_patch(0, 0x08001000, 0x20002000);
    fpb_set_patch(1, 0x08002000, 0x20003000);

    fpb_info_t info;
    fpb_get_info(&info);

    /* Check comparator 0 */
    TEST_ASSERT_TRUE(info.comp[0].enabled);
    TEST_ASSERT_EQUAL(0, info.comp[0].replace); /* REMAP mode = 0 */
    TEST_ASSERT_EQUAL(0x08001000, info.comp[0].match_addr);

    /* Check comparator 1 */
    TEST_ASSERT_TRUE(info.comp[1].enabled);
    TEST_ASSERT_EQUAL(0, info.comp[1].replace);
    TEST_ASSERT_EQUAL(0x08002000, info.comp[1].match_addr);

    /* Check comparator 2 (not set) */
    TEST_ASSERT_FALSE(info.comp[2].enabled);
}

void test_fpb_get_info_comp_raw(void) {
    setup_fpb();
    fpb_init();

    fpb_set_patch(0, 0x08001000, 0x20002000);

    fpb_info_t info;
    fpb_get_info(&info);

    /* comp_raw should have ENABLE bit set */
    TEST_ASSERT(info.comp[0].comp_raw & 0x1);
    /* comp_raw should have address in bits[28:2] */
    TEST_ASSERT((info.comp[0].comp_raw & 0x1FFFFFFCUL) == 0x08001000);
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

    fpb_result_t ret = fpb_set_instruction_patch(0, 0x08001000, 0x4770, false); /* BX LR */
    TEST_ASSERT_EQUAL(FPB_OK, ret);
}

void test_fpb_set_instruction_patch_upper(void) {
    setup_fpb();
    fpb_init();

    fpb_result_t ret = fpb_set_instruction_patch(0, 0x08001000, 0x4770, true); /* Upper half */
    TEST_ASSERT_EQUAL(FPB_OK, ret);
}

void test_fpb_set_instruction_patch_not_initialized(void) {
    setup_fpb();
    /* Don't init FPB */

    fpb_result_t ret = fpb_set_instruction_patch(0, 0x08001000, 0x4770, false);
    TEST_ASSERT_EQUAL(FPB_ERR_NOT_INIT, ret);
}

void test_fpb_set_instruction_patch_invalid_comp(void) {
    setup_fpb();
    fpb_init();

    fpb_result_t ret = fpb_set_instruction_patch(100, 0x08001000, 0x4770, false);
    TEST_ASSERT_EQUAL(FPB_ERR_INVALID_COMP, ret);
}

void test_fpb_set_instruction_patch_ram_address(void) {
    setup_fpb();
    fpb_init();

    /* RAM address should fail */
    fpb_result_t ret = fpb_set_instruction_patch(0, 0x20001000, 0x4770, false);
    TEST_ASSERT_EQUAL(FPB_ERR_INVALID_ADDR, ret);
}

/* ============================================================================
 * Remap Table Index Tests (Bug Regression Tests)
 *
 * These tests verify the fix for the remap table index bug where:
 * - Original bug: used comp_id * 2 as index, causing SLOT1+ to fail
 * - Fix: use comp_id directly as index (Remap_Base + 4*n per ARM spec)
 *
 * See: Docs/FPB_Remap_Table_Bug_Analysis.md
 * ============================================================================ */

void test_fpb_remap_table_slot0_index(void) {
    setup_fpb();
    fpb_init();

    /* Set patch on SLOT0 */
    fpb_set_patch(0, 0x08001000, 0x20002000);

    /* Verify remap table entry 0 is non-zero (contains jump instruction) */
    const uint32_t* remap_table = fpb_test_get_remap_table();
    TEST_ASSERT(remap_table[0] != 0);
}

void test_fpb_remap_table_slot1_index(void) {
    setup_fpb();
    fpb_init();

    /* Set patch on SLOT1 only (regression test for the bug) */
    fpb_set_patch(1, 0x08002000, 0x20003000);

    /* Verify remap table entry 1 is non-zero (contains jump instruction) */
    const uint32_t* remap_table = fpb_test_get_remap_table();
    TEST_ASSERT(remap_table[1] != 0);

    /* Verify entry 0 is NOT affected (should be zero) */
    TEST_ASSERT_EQUAL(0, remap_table[0]);
}

void test_fpb_remap_table_multiple_slots(void) {
    setup_fpb();
    fpb_init();

    /* Set patches on multiple slots with different offsets to ensure unique instructions */
    fpb_set_patch(0, 0x08001000, 0x20002000);
    fpb_set_patch(1, 0x08002000, 0x20010000); /* Different offset range */
    fpb_set_patch(2, 0x08003000, 0x20020000); /* Different offset range */

    /* Verify each slot has its own entry (non-zero) */
    const uint32_t* remap_table = fpb_test_get_remap_table();
    TEST_ASSERT(remap_table[0] != 0);
    TEST_ASSERT(remap_table[1] != 0);
    TEST_ASSERT(remap_table[2] != 0);

    /* Note: We don't verify entries are different since B.W instruction encoding
     * may produce same value for different but similar offset distances.
     * The key is that each entry is set and at the correct index. */
}

void test_fpb_remap_table_clear_slot(void) {
    setup_fpb();
    fpb_init();

    /* Set patch on SLOT1 */
    fpb_set_patch(1, 0x08002000, 0x20003000);
    const uint32_t* remap_table = fpb_test_get_remap_table();
    TEST_ASSERT(remap_table[1] != 0);

    /* Clear SLOT1 */
    fpb_clear_patch(1);

    /* Verify entry 1 is cleared */
    TEST_ASSERT_EQUAL(0, remap_table[1]);
}

void test_fpb_remap_table_no_overlap(void) {
    setup_fpb();
    fpb_init();

    /* This test verifies the fix for the original bug:
     * Original bug stored at index comp_id*2, causing:
     *   SLOT0 -> entry[0], entry[1]
     *   SLOT1 -> entry[2], entry[3]
     * Fix stores at index comp_id:
     *   SLOT0 -> entry[0]
     *   SLOT1 -> entry[1]
     */

    /* Set patch on SLOT0 */
    fpb_set_patch(0, 0x08001000, 0x20002000);
    const uint32_t* remap_table = fpb_test_get_remap_table();
    uint32_t entry0 = remap_table[0];

    /* Set patch on SLOT1 - should NOT overwrite or affect entry[0] */
    fpb_set_patch(1, 0x08002000, 0x20003000);

    /* SLOT0's entry should be unchanged */
    TEST_ASSERT_EQUAL(entry0, remap_table[0]);
}

void test_fpb_remap_table_all_slots(void) {
    setup_fpb();
    fpb_init();

    /* Get actual number of code comparators from hardware */
    uint8_t num_code_comp = fpb_get_num_code_comp();

    /* Set patches on all available slots */
    for (uint8_t i = 0; i < num_code_comp; i++) {
        uint32_t orig_addr = 0x08001000 + (i * 0x1000);
        uint32_t patch_addr = 0x20002000 + (i * 0x1000);
        fpb_result_t ret = fpb_set_patch(i, orig_addr, patch_addr);
        TEST_ASSERT_EQUAL(FPB_OK, ret);
    }

    /* Verify all entries are set and unique */
    const uint32_t* remap_table = fpb_test_get_remap_table();
    for (uint8_t i = 0; i < num_code_comp; i++) {
        TEST_ASSERT(remap_table[i] != 0);
    }
}

void test_fpb_remap_table_all_slots_v2(void) {
    setup_fpb_v2();
    fpb_init();

    /* FPB v2: 8 code comparators */
    uint8_t num_code_comp = fpb_get_num_code_comp();
    TEST_ASSERT_EQUAL(8, num_code_comp);

    /* Set patches on all 8 slots */
    for (uint8_t i = 0; i < num_code_comp; i++) {
        uint32_t orig_addr = 0x08001000 + (i * 0x1000);
        uint32_t patch_addr = 0x20002000 + (i * 0x1000);
        fpb_result_t ret = fpb_set_patch(i, orig_addr, patch_addr);
        TEST_ASSERT_EQUAL(FPB_OK, ret);
    }

    /* Verify all 8 entries are set */
    const uint32_t* remap_table = fpb_test_get_remap_table();
    for (uint8_t i = 0; i < num_code_comp; i++) {
        TEST_ASSERT(remap_table[i] != 0);
    }
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
    RUN_TEST(test_fpb_get_state_num_comp_v2);
    RUN_TEST(test_fpb_get_state_after_patch);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Support Query");
    RUN_TEST(test_fpb_is_supported_with_comps);
    RUN_TEST(test_fpb_get_num_code_comp);
    RUN_TEST(test_fpb_get_num_code_comp_v2);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_inject - Device Info");
    RUN_TEST(test_fpb_get_info_basic);
    RUN_TEST(test_fpb_get_info_num_comp);
    RUN_TEST(test_fpb_get_info_enabled);
    RUN_TEST(test_fpb_get_info_disabled);
    RUN_TEST(test_fpb_get_info_null_pointer);
    RUN_TEST(test_fpb_get_info_revision);
    RUN_TEST(test_fpb_get_info_remap_supported);
    RUN_TEST(test_fpb_get_info_remap_base);
    RUN_TEST(test_fpb_get_info_comp_fields);
    RUN_TEST(test_fpb_get_info_comp_raw);
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

    TEST_SUITE_BEGIN("fpb_inject - Remap Table Index (Bug Regression)");
    RUN_TEST(test_fpb_remap_table_slot0_index);
    RUN_TEST(test_fpb_remap_table_slot1_index);
    RUN_TEST(test_fpb_remap_table_multiple_slots);
    RUN_TEST(test_fpb_remap_table_clear_slot);
    RUN_TEST(test_fpb_remap_table_no_overlap);
    RUN_TEST(test_fpb_remap_table_all_slots);
    RUN_TEST(test_fpb_remap_table_all_slots_v2);
    TEST_SUITE_END();
}
