/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Tests for func_allocator.c - Fixed-block memory allocator
 */

#include "test_framework.h"
#include "mock_hardware.h"
#include "func_allocator.h"

/* Test buffer - large enough for multiple blocks */
static uint8_t test_buffer[4096];
static func_alloc_t test_alloc;

/* ============================================================================
 * Setup/Teardown
 * ============================================================================ */

static void setup_allocator(void) {
    memset(test_buffer, 0, sizeof(test_buffer));
    memset(&test_alloc, 0, sizeof(test_alloc));
    func_alloc_init(&test_alloc, test_buffer, sizeof(test_buffer));
}

/* ============================================================================
 * Initialization Tests
 * ============================================================================ */

void test_allocator_init_valid(void) {
    setup_allocator();
    TEST_ASSERT_TRUE(func_alloc_is_valid(&test_alloc));
}

void test_allocator_init_null_buffer(void) {
    func_alloc_t alloc;
    memset(&alloc, 0, sizeof(alloc));
    func_alloc_init(&alloc, NULL, 1024);
    TEST_ASSERT_FALSE(func_alloc_is_valid(&alloc));
}

void test_allocator_init_zero_size(void) {
    func_alloc_t alloc;
    memset(&alloc, 0, sizeof(alloc));
    func_alloc_init(&alloc, test_buffer, 0);
    TEST_ASSERT_FALSE(func_alloc_is_valid(&alloc));
}

void test_allocator_init_small_buffer(void) {
    func_alloc_t alloc;
    uint8_t small_buf[32];
    memset(&alloc, 0, sizeof(alloc));
    func_alloc_init(&alloc, small_buf, sizeof(small_buf));
    /* Small buffer may or may not be valid depending on block size */
    /* Just check it doesn't crash */
}

/* ============================================================================
 * Allocation Tests
 * ============================================================================ */

void test_allocator_malloc_simple(void) {
    setup_allocator();
    void* ptr = func_malloc(&test_alloc, 32);
    TEST_ASSERT_NOT_NULL(ptr);
}

void test_allocator_malloc_multiple(void) {
    setup_allocator();
    void* ptr1 = func_malloc(&test_alloc, 32);
    void* ptr2 = func_malloc(&test_alloc, 32);
    void* ptr3 = func_malloc(&test_alloc, 32);

    TEST_ASSERT_NOT_NULL(ptr1);
    TEST_ASSERT_NOT_NULL(ptr2);
    TEST_ASSERT_NOT_NULL(ptr3);
    TEST_ASSERT(ptr1 != ptr2);
    TEST_ASSERT(ptr2 != ptr3);
    TEST_ASSERT(ptr1 != ptr3);
}

void test_allocator_malloc_various_sizes(void) {
    setup_allocator();
    void* ptr1 = func_malloc(&test_alloc, 16);
    void* ptr2 = func_malloc(&test_alloc, 64);
    void* ptr3 = func_malloc(&test_alloc, 128);

    TEST_ASSERT_NOT_NULL(ptr1);
    TEST_ASSERT_NOT_NULL(ptr2);
    TEST_ASSERT_NOT_NULL(ptr3);
}

void test_allocator_malloc_zero(void) {
    setup_allocator();
    void* ptr = func_malloc(&test_alloc, 0);
    /* Zero-size allocation behavior is implementation-defined */
    (void)ptr;
}

void test_allocator_malloc_too_large(void) {
    setup_allocator();
    /* Try to allocate more than the pool size */
    void* ptr = func_malloc(&test_alloc, sizeof(test_buffer) * 2);
    TEST_ASSERT_NULL(ptr);
}

void test_allocator_malloc_exhaust(void) {
    setup_allocator();

    /* Allocate until exhausted */
    int count = 0;
    while (func_malloc(&test_alloc, FUNC_ALLOC_BLOCK_SIZE) != NULL) {
        count++;
        if (count > 1000)
            break; /* Safety limit */
    }

    TEST_ASSERT(count > 0);
    TEST_ASSERT(count < 1000);

    /* Next allocation should fail */
    TEST_ASSERT_NULL(func_malloc(&test_alloc, FUNC_ALLOC_BLOCK_SIZE));
}

/* ============================================================================
 * Free Tests
 * ============================================================================ */

void test_allocator_free_simple(void) {
    setup_allocator();
    void* ptr = func_malloc(&test_alloc, 64);
    TEST_ASSERT_NOT_NULL(ptr);
    func_free(&test_alloc, ptr);
    /* Should not crash */
}

void test_allocator_free_null(void) {
    setup_allocator();
    func_free(&test_alloc, NULL);
    /* Should not crash */
}

void test_allocator_free_reuse(void) {
    setup_allocator();

    void* ptr1 = func_malloc(&test_alloc, 64);
    TEST_ASSERT_NOT_NULL(ptr1);
    func_free(&test_alloc, ptr1);

    void* ptr2 = func_malloc(&test_alloc, 64);
    TEST_ASSERT_NOT_NULL(ptr2);
    /* Memory should be reused */
}

void test_allocator_free_multiple(void) {
    setup_allocator();

    void* ptrs[10];
    for (int i = 0; i < 10; i++) {
        ptrs[i] = func_malloc(&test_alloc, 32);
        TEST_ASSERT_NOT_NULL(ptrs[i]);
    }

    for (int i = 0; i < 10; i++) {
        func_free(&test_alloc, ptrs[i]);
    }

    /* Should be able to allocate again */
    void* ptr = func_malloc(&test_alloc, 32);
    TEST_ASSERT_NOT_NULL(ptr);
}

/* ============================================================================
 * Statistics Tests
 * ============================================================================ */

void test_allocator_stats_initial(void) {
    setup_allocator();

    size_t total, used, free_blocks;
    func_alloc_stats(&test_alloc, &total, &used, &free_blocks);

    TEST_ASSERT(total > 0);
    TEST_ASSERT_EQUAL(0, used);
    TEST_ASSERT_EQUAL(total, free_blocks);
}

void test_allocator_stats_after_alloc(void) {
    setup_allocator();

    size_t total, used, free_blocks;
    func_alloc_stats(&test_alloc, &total, &used, &free_blocks);
    size_t initial_free = free_blocks;

    void* ptr = func_malloc(&test_alloc, FUNC_ALLOC_BLOCK_SIZE);
    TEST_ASSERT_NOT_NULL(ptr);

    func_alloc_stats(&test_alloc, &total, &used, &free_blocks);
    TEST_ASSERT(used > 0);
    TEST_ASSERT(free_blocks < initial_free);
}

void test_allocator_stats_after_free(void) {
    setup_allocator();

    void* ptr = func_malloc(&test_alloc, FUNC_ALLOC_BLOCK_SIZE);
    TEST_ASSERT_NOT_NULL(ptr);

    size_t total, used_before, free_before;
    func_alloc_stats(&test_alloc, &total, &used_before, &free_before);
    TEST_ASSERT(used_before > 0);

    func_free(&test_alloc, ptr);

    size_t used_after, free_after;
    func_alloc_stats(&test_alloc, &total, &used_after, &free_after);
    TEST_ASSERT(used_after < used_before);
    TEST_ASSERT(free_after > free_before);
}

/* ============================================================================
 * func_alloc_size Tests
 * ============================================================================ */

void test_allocator_size_basic(void) {
    setup_allocator();

    void* ptr = func_malloc(&test_alloc, 64);
    TEST_ASSERT_NOT_NULL(ptr);

    size_t size = func_alloc_size(&test_alloc, ptr);
    TEST_ASSERT(size >= 64);
}

void test_allocator_size_null_alloc(void) {
    void* ptr = (void*)0x1000;
    size_t size = func_alloc_size(NULL, ptr);
    TEST_ASSERT_EQUAL(0, size);
}

void test_allocator_size_null_ptr(void) {
    setup_allocator();

    size_t size = func_alloc_size(&test_alloc, NULL);
    TEST_ASSERT_EQUAL(0, size);
}

void test_allocator_size_invalid_ptr(void) {
    setup_allocator();

    /* Pointer outside of managed blocks */
    void* invalid_ptr = (void*)0x1000;
    size_t size = func_alloc_size(&test_alloc, invalid_ptr);
    TEST_ASSERT_EQUAL(0, size);
}

void test_allocator_size_unaligned_ptr(void) {
    setup_allocator();

    void* ptr = func_malloc(&test_alloc, 64);
    TEST_ASSERT_NOT_NULL(ptr);

    /* Unaligned pointer */
    void* unaligned = (uint8_t*)ptr + 1;
    size_t size = func_alloc_size(&test_alloc, unaligned);
    TEST_ASSERT_EQUAL(0, size);
}

void test_allocator_size_freed_ptr(void) {
    setup_allocator();

    void* ptr = func_malloc(&test_alloc, 64);
    TEST_ASSERT_NOT_NULL(ptr);

    func_free(&test_alloc, ptr);

    size_t size = func_alloc_size(&test_alloc, ptr);
    TEST_ASSERT_EQUAL(0, size);
}

void test_allocator_size_various_sizes(void) {
    setup_allocator();

    void* ptr1 = func_malloc(&test_alloc, 32);
    void* ptr2 = func_malloc(&test_alloc, 128);
    void* ptr3 = func_malloc(&test_alloc, 256);

    TEST_ASSERT_NOT_NULL(ptr1);
    TEST_ASSERT_NOT_NULL(ptr2);
    TEST_ASSERT_NOT_NULL(ptr3);

    size_t size1 = func_alloc_size(&test_alloc, ptr1);
    size_t size2 = func_alloc_size(&test_alloc, ptr2);
    size_t size3 = func_alloc_size(&test_alloc, ptr3);

    TEST_ASSERT(size1 >= 32);
    TEST_ASSERT(size2 >= 128);
    TEST_ASSERT(size3 >= 256);
}

/* ============================================================================
 * func_alloc_is_valid Tests
 * ============================================================================ */

void test_allocator_is_valid_true(void) {
    setup_allocator();
    TEST_ASSERT_TRUE(func_alloc_is_valid(&test_alloc));
}

void test_allocator_is_valid_null(void) {
    TEST_ASSERT_FALSE(func_alloc_is_valid(NULL));
}

void test_allocator_is_valid_uninit(void) {
    func_alloc_t uninit;
    memset(&uninit, 0, sizeof(uninit));
    TEST_ASSERT_FALSE(func_alloc_is_valid(&uninit));
}

/* ============================================================================
 * Test Runner
 * ============================================================================ */

void run_allocator_tests(void) {
    TEST_SUITE_BEGIN("func_allocator - Initialization");
    RUN_TEST(test_allocator_init_valid);
    RUN_TEST(test_allocator_init_null_buffer);
    RUN_TEST(test_allocator_init_zero_size);
    RUN_TEST(test_allocator_init_small_buffer);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_allocator - Allocation");
    RUN_TEST(test_allocator_malloc_simple);
    RUN_TEST(test_allocator_malloc_multiple);
    RUN_TEST(test_allocator_malloc_various_sizes);
    RUN_TEST(test_allocator_malloc_zero);
    RUN_TEST(test_allocator_malloc_too_large);
    RUN_TEST(test_allocator_malloc_exhaust);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_allocator - Free");
    RUN_TEST(test_allocator_free_simple);
    RUN_TEST(test_allocator_free_null);
    RUN_TEST(test_allocator_free_reuse);
    RUN_TEST(test_allocator_free_multiple);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_allocator - Statistics");
    RUN_TEST(test_allocator_stats_initial);
    RUN_TEST(test_allocator_stats_after_alloc);
    RUN_TEST(test_allocator_stats_after_free);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_allocator - Size Query");
    RUN_TEST(test_allocator_size_basic);
    RUN_TEST(test_allocator_size_null_alloc);
    RUN_TEST(test_allocator_size_null_ptr);
    RUN_TEST(test_allocator_size_invalid_ptr);
    RUN_TEST(test_allocator_size_unaligned_ptr);
    RUN_TEST(test_allocator_size_freed_ptr);
    RUN_TEST(test_allocator_size_various_sizes);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_allocator - Validation");
    RUN_TEST(test_allocator_is_valid_true);
    RUN_TEST(test_allocator_is_valid_null);
    RUN_TEST(test_allocator_is_valid_uninit);
    TEST_SUITE_END();
}
