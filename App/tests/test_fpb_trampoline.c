/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Unit tests for fpb_trampoline.c
 */

#include "test_framework.h"
#include "fpb_trampoline.h"

/* ============================================================================
 * Test Setup/Teardown
 * ============================================================================ */

static void setup_trampoline(void) {
    /* Clear all trampoline targets */
    for (uint32_t i = 0; i < FPB_TRAMPOLINE_COUNT; i++) {
        fpb_trampoline_clear_target(i);
    }
}

/* ============================================================================
 * Set Target Tests
 * ============================================================================ */

static void test_trampoline_set_target_basic(void) {
    setup_trampoline();

    fpb_trampoline_set_target(0, 0x20001001);

    /* Verify via get_target (host testing only) */
    extern uint32_t fpb_trampoline_get_target(uint32_t comp);
    TEST_ASSERT_EQUAL(0x20001001, fpb_trampoline_get_target(0));
}

static void test_trampoline_set_target_multiple(void) {
    setup_trampoline();
    extern uint32_t fpb_trampoline_get_target(uint32_t comp);

    fpb_trampoline_set_target(0, 0x20001000);
    fpb_trampoline_set_target(1, 0x20002000);
    fpb_trampoline_set_target(2, 0x20003000);

    TEST_ASSERT_EQUAL(0x20001000, fpb_trampoline_get_target(0));
    TEST_ASSERT_EQUAL(0x20002000, fpb_trampoline_get_target(1));
    TEST_ASSERT_EQUAL(0x20003000, fpb_trampoline_get_target(2));
}

static void test_trampoline_set_target_overwrite(void) {
    setup_trampoline();
    extern uint32_t fpb_trampoline_get_target(uint32_t comp);

    fpb_trampoline_set_target(0, 0x20001000);
    fpb_trampoline_set_target(0, 0x20009000);

    TEST_ASSERT_EQUAL(0x20009000, fpb_trampoline_get_target(0));
}

static void test_trampoline_set_target_invalid_comp(void) {
    setup_trampoline();
    extern uint32_t fpb_trampoline_get_target(uint32_t comp);

    /* Setting target for invalid comp should be ignored */
    fpb_trampoline_set_target(10, 0x20001000);

    /* Should return 0 for invalid comp */
    TEST_ASSERT_EQUAL(0, fpb_trampoline_get_target(10));
}

static void test_trampoline_set_target_all_slots(void) {
    setup_trampoline();
    extern uint32_t fpb_trampoline_get_target(uint32_t comp);

    /* Set targets for all 6 slots */
    for (uint32_t i = 0; i < FPB_TRAMPOLINE_COUNT; i++) {
        fpb_trampoline_set_target(i, 0x20000000 + i * 0x1000);
    }

    /* Verify all slots */
    for (uint32_t i = 0; i < FPB_TRAMPOLINE_COUNT; i++) {
        TEST_ASSERT_EQUAL(0x20000000 + i * 0x1000, fpb_trampoline_get_target(i));
    }
}

/* ============================================================================
 * Clear Target Tests
 * ============================================================================ */

static void test_trampoline_clear_target_basic(void) {
    setup_trampoline();
    extern uint32_t fpb_trampoline_get_target(uint32_t comp);

    fpb_trampoline_set_target(0, 0x20001000);
    fpb_trampoline_clear_target(0);

    TEST_ASSERT_EQUAL(0, fpb_trampoline_get_target(0));
}

static void test_trampoline_clear_target_preserves_others(void) {
    setup_trampoline();
    extern uint32_t fpb_trampoline_get_target(uint32_t comp);

    fpb_trampoline_set_target(0, 0x20001000);
    fpb_trampoline_set_target(1, 0x20002000);
    fpb_trampoline_set_target(2, 0x20003000);

    fpb_trampoline_clear_target(1);

    TEST_ASSERT_EQUAL(0x20001000, fpb_trampoline_get_target(0));
    TEST_ASSERT_EQUAL(0, fpb_trampoline_get_target(1));
    TEST_ASSERT_EQUAL(0x20003000, fpb_trampoline_get_target(2));
}

static void test_trampoline_clear_target_invalid_comp(void) {
    setup_trampoline();

    /* Should not crash when clearing invalid comp */
    fpb_trampoline_clear_target(10);

    /* Test passes if no crash */
    TEST_ASSERT_TRUE(1);
}

static void test_trampoline_clear_target_already_clear(void) {
    setup_trampoline();
    extern uint32_t fpb_trampoline_get_target(uint32_t comp);

    /* Clearing already-clear target should be safe */
    fpb_trampoline_clear_target(0);

    TEST_ASSERT_EQUAL(0, fpb_trampoline_get_target(0));
}

/* ============================================================================
 * Get Address Tests
 * ============================================================================ */

static void test_trampoline_get_address_valid(void) {
    uint32_t addr = fpb_trampoline_get_address(0);

    /* Should return non-zero address with Thumb bit set */
    TEST_ASSERT(addr != 0);
    TEST_ASSERT((addr & 1) != 0); /* Thumb bit set */
}

static void test_trampoline_get_address_all_slots(void) {
    /* All 6 trampolines should have unique addresses */
    uint32_t addrs[FPB_TRAMPOLINE_COUNT];

    for (uint32_t i = 0; i < FPB_TRAMPOLINE_COUNT; i++) {
        addrs[i] = fpb_trampoline_get_address(i);
        TEST_ASSERT(addrs[i] != 0);
        TEST_ASSERT((addrs[i] & 1) != 0);
    }

    /* Check all addresses are unique */
    for (uint32_t i = 0; i < FPB_TRAMPOLINE_COUNT; i++) {
        for (uint32_t j = i + 1; j < FPB_TRAMPOLINE_COUNT; j++) {
            TEST_ASSERT(addrs[i] != addrs[j]);
        }
    }
}

static void test_trampoline_get_address_invalid_comp(void) {
    uint32_t addr = fpb_trampoline_get_address(10);

    /* Invalid comp should return 0 */
    TEST_ASSERT_EQUAL(0, addr);
}

static void test_trampoline_get_address_in_flash(void) {
    /* Trampoline addresses should be in Flash region */
    uint32_t addr = fpb_trampoline_get_address(0);
    uint32_t addr_no_thumb = addr & ~1UL;

    /* Flash region is typically 0x08000000 - 0x1FFFFFFF */
    TEST_ASSERT(addr_no_thumb >= 0x08000000);
    TEST_ASSERT(addr_no_thumb < 0x20000000);
}

/* ============================================================================
 * Integration Tests
 * ============================================================================ */

static void test_trampoline_workflow(void) {
    setup_trampoline();
    extern uint32_t fpb_trampoline_get_target(uint32_t comp);

    /* Typical workflow:
     * 1. Get trampoline address for FPB remap
     * 2. Set target to RAM code address
     * 3. FPB redirects to trampoline, trampoline jumps to target
     */

    uint32_t trampoline_addr = fpb_trampoline_get_address(0);
    TEST_ASSERT(trampoline_addr != 0);

    /* Set RAM target */
    fpb_trampoline_set_target(0, 0x20001001);
    TEST_ASSERT_EQUAL(0x20001001, fpb_trampoline_get_target(0));

    /* Clear when done */
    fpb_trampoline_clear_target(0);
    TEST_ASSERT_EQUAL(0, fpb_trampoline_get_target(0));
}

static void test_trampoline_boundary_comp_ids(void) {
    setup_trampoline();
    extern uint32_t fpb_trampoline_get_target(uint32_t comp);

    /* Test boundary comp_ids */
    fpb_trampoline_set_target(0, 0x20000000);
    fpb_trampoline_set_target(5, 0x20005000); /* Last valid */

    TEST_ASSERT_EQUAL(0x20000000, fpb_trampoline_get_target(0));
    TEST_ASSERT_EQUAL(0x20005000, fpb_trampoline_get_target(5));

    /* comp 6 is out of range */
    fpb_trampoline_set_target(6, 0x20006000);
    TEST_ASSERT_EQUAL(0, fpb_trampoline_get_target(6));
}

/* ============================================================================
 * Test Registration
 * ============================================================================ */

void run_fpb_trampoline_tests(void) {
    TEST_SUITE_BEGIN("fpb_trampoline - Set Target");
    RUN_TEST(test_trampoline_set_target_basic);
    RUN_TEST(test_trampoline_set_target_multiple);
    RUN_TEST(test_trampoline_set_target_overwrite);
    RUN_TEST(test_trampoline_set_target_invalid_comp);
    RUN_TEST(test_trampoline_set_target_all_slots);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_trampoline - Clear Target");
    RUN_TEST(test_trampoline_clear_target_basic);
    RUN_TEST(test_trampoline_clear_target_preserves_others);
    RUN_TEST(test_trampoline_clear_target_invalid_comp);
    RUN_TEST(test_trampoline_clear_target_already_clear);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_trampoline - Get Address");
    RUN_TEST(test_trampoline_get_address_valid);
    RUN_TEST(test_trampoline_get_address_all_slots);
    RUN_TEST(test_trampoline_get_address_invalid_comp);
    RUN_TEST(test_trampoline_get_address_in_flash);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fpb_trampoline - Integration");
    RUN_TEST(test_trampoline_workflow);
    RUN_TEST(test_trampoline_boundary_comp_ids);
    TEST_SUITE_END();
}
