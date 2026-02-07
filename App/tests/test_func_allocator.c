/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Tests for func_allocator.c - Fixed-block memory allocator
 */

#include "test_framework.h"
#include "mock_hardware.h"
#include "stubs.h"

/* Test constants */
#define TEST_BLOCK_SIZE 32

/* Test buffer */
static uint8_t test_buffer[2048];
static func_alloc_t test_alloc;

/* ============================================================================
 * Setup/Teardown
 * ============================================================================ */

static void setup_allocator(void) {
    memset(test_buffer, 0, sizeof(test_buffer));
    func_alloc_init(&test_alloc, test_buffer, sizeof(test_buffer), 32);
}

/* Helper to check if allocator is valid */
static bool func_alloc_is_valid(func_alloc_t* a) {
    return a && a->pool && a->pool_size > 0 && a->block_size > 0;
}

/* ============================================================================
 * func_alloc_init Tests
 * ============================================================================ */

void test_allocator_init_valid(void) {
    setup_allocator();
    TEST_ASSERT_TRUE(func_alloc_is_valid(&test_alloc));
}

void test_allocator_init_null_buffer(void) {
    func_alloc_t alloc;
    memset(&alloc, 0, sizeof(alloc));
    func_alloc_init(&alloc, NULL, 1024, 32);
    TEST_ASSERT_FALSE(func_alloc_is_valid(&alloc));
}

void test_allocator_init_zero_size(void) {
    func_alloc_t alloc;
    memset(&alloc, 0, sizeof(alloc));
    func_alloc_init(&alloc, test_buffer, 0, 32);
    TEST_ASSERT_FALSE(func_alloc_is_valid(&alloc));
}

void test_allocator_init_small_buffer(void) {
    uint8_t small_buf[32];
    func_alloc_t alloc;
    memset(&alloc, 0, sizeof(alloc));
    func_alloc_init(&alloc, small_buf, sizeof(small_buf), 32);
    /* Should still be valid with 1 block */
    TEST_ASSERT_TRUE(func_alloc_is_valid(&alloc));
}

/* ============================================================================
 * func_malloc Tests
 * ============================================================================ */

void test_allocator_malloc_simple(void) {
    setup_allocator();
    void* ptr = func_malloc(&test_alloc, 64);
    TEST_ASSERT_NOT_NULL(ptr);
}

void test_allocator_malloc_multiple(void) {
    setup_allocator();
    void* ptr1 = func_malloc(&test_alloc, 64);
    void* ptr2 = func_malloc(&test_alloc, 64);
    void* ptr3 = func_malloc(&test_alloc, 64);

    TEST_ASSERT_NOT_NULL(ptr1);
    TEST_ASSERT_NOT_NULL(ptr2);
    TEST_ASSERT_NOT_NULL(ptr3);
    TEST_ASSERT(ptr1 != ptr2);
    TEST_ASSERT(ptr2 != ptr3);
}

void test_allocator_malloc_various_sizes(void) {
    setup_allocator();
    void* ptr1 = func_malloc(&test_alloc, 32);
    void* ptr2 = func_malloc(&test_alloc, 128);
    void* ptr3 = func_malloc(&test_alloc, 64);

    TEST_ASSERT_NOT_NULL(ptr1);
    TEST_ASSERT_NOT_NULL(ptr2);
    TEST_ASSERT_NOT_NULL(ptr3);
}

void test_allocator_malloc_zero(void) {
    setup_allocator();
    void* ptr = func_malloc(&test_alloc, 0);
    /* Zero-size allocation behavior is implementation-defined */
    /* Just ensure no crash, result can be NULL or valid */
    (void)ptr;
}

void test_allocator_malloc_too_large(void) {
    setup_allocator();
    void* ptr = func_malloc(&test_alloc, 10000); /* Larger than buffer */
    TEST_ASSERT_NULL(ptr);
}

void test_allocator_malloc_exhaust(void) {
    setup_allocator();
    int count = 0;
    while (func_malloc(&test_alloc, TEST_BLOCK_SIZE) != NULL) {
        count++;
        if (count > 100)
            break; /* Safety limit */
    }
    TEST_ASSERT(count > 0);
    TEST_ASSERT(count <= 100);
}

/* ============================================================================
 * func_free Tests
 * ============================================================================ */

void test_allocator_free_simple(void) {
    setup_allocator();
    void* ptr = func_malloc(&test_alloc, 64);
    TEST_ASSERT_NOT_NULL(ptr);
    func_free(&test_alloc, ptr, 64);
    /* Should not crash */
}

void test_allocator_free_null(void) {
    setup_allocator();
    func_free(&test_alloc, NULL, 0);
    /* Should not crash */
}

void test_allocator_free_reuse(void) {
    setup_allocator();

    /* Allocate until full */
    void* ptrs[32];
    int count = 0;
    while (count < 32) {
        ptrs[count] = func_malloc(&test_alloc, TEST_BLOCK_SIZE);
        if (ptrs[count] == NULL)
            break;
        count++;
    }

    if (count > 0) {
        /* Free first allocation */
        func_free(&test_alloc, ptrs[0], TEST_BLOCK_SIZE);

        /* Should be able to allocate again */
        void* new_ptr = func_malloc(&test_alloc, TEST_BLOCK_SIZE);
        TEST_ASSERT_NOT_NULL(new_ptr);
    }
}

void test_allocator_free_multiple(void) {
    setup_allocator();
    void* ptr1 = func_malloc(&test_alloc, 64);
    void* ptr2 = func_malloc(&test_alloc, 64);
    void* ptr3 = func_malloc(&test_alloc, 64);

    func_free(&test_alloc, ptr2, 64);
    func_free(&test_alloc, ptr1, 64);
    func_free(&test_alloc, ptr3, 64);
    /* Should not crash */
}

/* ============================================================================
 * func_alloc_stats Tests
 * ============================================================================ */

void test_allocator_stats_initial(void) {
    setup_allocator();
    size_t used, free_blocks, total;
    func_alloc_stats(&test_alloc, &used, &free_blocks, &total);

    TEST_ASSERT(total > 0);
    TEST_ASSERT_EQUAL(0, used);
    TEST_ASSERT(free_blocks == total);
}

void test_allocator_stats_after_alloc(void) {
    setup_allocator();
    size_t used, free_blocks, total;

    func_alloc_stats(&test_alloc, &used, &free_blocks, &total);
    size_t initial_free = free_blocks;

    func_malloc(&test_alloc, TEST_BLOCK_SIZE);
    func_alloc_stats(&test_alloc, &used, &free_blocks, &total);

    TEST_ASSERT(used >= 1);
    TEST_ASSERT(free_blocks < initial_free);
}

void test_allocator_stats_after_free(void) {
    setup_allocator();
    size_t used, free_blocks, total;

    void* ptr = func_malloc(&test_alloc, TEST_BLOCK_SIZE);
    func_alloc_stats(&test_alloc, &used, &free_blocks, &total);
    size_t used_before = used;

    func_free(&test_alloc, ptr, TEST_BLOCK_SIZE);
    func_alloc_stats(&test_alloc, &used, &free_blocks, &total);

    TEST_ASSERT(used < used_before);
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
}
