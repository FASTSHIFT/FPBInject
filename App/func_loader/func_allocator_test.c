/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

/**
 * @file   func_allocator_test.c
 * @brief  Unit tests for func_allocator
 *
 * Compile: gcc -DFL_USE_ALLOCATOR_TEST -o func_allocator_test func_allocator_test.c
 * Run: ./func_allocator_test
 */

#ifdef FL_USE_ALLOCATOR_TEST

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include "func_allocator.h"

/* Test buffer size */
#define TEST_BUF_SIZE 4096

/* Test counters */
static int tests_run = 0;
static int tests_passed = 0;

/* Test macros */
#define TEST_ASSERT(cond, msg)                               \
    do {                                                     \
        tests_run++;                                         \
        if (!(cond)) {                                       \
            printf("  FAIL: %s (line %d)\n", msg, __LINE__); \
            return 0;                                        \
        }                                                    \
        tests_passed++;                                      \
    } while (0)

#define RUN_TEST(test_func)                    \
    do {                                       \
        printf("Running %s...\n", #test_func); \
        if (test_func()) {                     \
            printf("  PASS\n");                \
        } else {                               \
            printf("  FAILED\n");              \
        }                                      \
    } while (0)

/* ========== Test Cases ========== */

/**
 * Test basic initialization
 */
static int test_init(void) {
    uint8_t buf[TEST_BUF_SIZE];
    func_alloc_t alloc;

    func_alloc_init(&alloc, buf, TEST_BUF_SIZE);

    TEST_ASSERT(func_alloc_is_valid(&alloc), "Allocator should be valid after init");
    TEST_ASSERT(alloc.block_count > 0, "Should have blocks available");
    TEST_ASSERT(alloc.bitmap != NULL, "Bitmap should be set");
    TEST_ASSERT(alloc.size_table != NULL, "Size table should be set");
    TEST_ASSERT(alloc.blocks != NULL, "Blocks pointer should be set");

    size_t total, used, free_blks;
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(total == alloc.block_count, "Total should match block_count");
    TEST_ASSERT(used == 0, "No blocks should be used initially");
    TEST_ASSERT(free_blks == total, "All blocks should be free initially");

    return 1;
}

/**
 * Test initialization with NULL/invalid parameters
 */
static int test_init_invalid(void) {
    func_alloc_t alloc;
    uint8_t buf[TEST_BUF_SIZE];

    /* NULL alloc */
    func_alloc_init(NULL, buf, TEST_BUF_SIZE);
    /* Should not crash */

    /* NULL buffer */
    func_alloc_init(&alloc, NULL, TEST_BUF_SIZE);
    TEST_ASSERT(!func_alloc_is_valid(&alloc), "Should be invalid with NULL buffer");

    /* Zero size */
    func_alloc_init(&alloc, buf, 0);
    TEST_ASSERT(!func_alloc_is_valid(&alloc), "Should be invalid with zero size");

    /* Too small buffer */
    func_alloc_init(&alloc, buf, 10);
    TEST_ASSERT(!func_alloc_is_valid(&alloc), "Should be invalid with tiny buffer");

    return 1;
}

/**
 * Test basic allocation and free
 */
static int test_basic_alloc_free(void) {
    uint8_t buf[TEST_BUF_SIZE];
    func_alloc_t alloc;

    func_alloc_init(&alloc, buf, TEST_BUF_SIZE);

    /* Allocate one block */
    void* p1 = func_malloc(&alloc, 32);
    TEST_ASSERT(p1 != NULL, "First allocation should succeed");

    size_t total, used, free_blks;
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 1, "One block should be used");

    /* Free it */
    func_free(&alloc, p1);
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 0, "No blocks should be used after free");

    return 1;
}

/**
 * Test multiple allocations
 */
static int test_multiple_allocs(void) {
    uint8_t buf[TEST_BUF_SIZE];
    func_alloc_t alloc;

    func_alloc_init(&alloc, buf, TEST_BUF_SIZE);

    void* p1 = func_malloc(&alloc, 64);
    void* p2 = func_malloc(&alloc, 64);
    void* p3 = func_malloc(&alloc, 64);

    TEST_ASSERT(p1 != NULL, "First allocation should succeed");
    TEST_ASSERT(p2 != NULL, "Second allocation should succeed");
    TEST_ASSERT(p3 != NULL, "Third allocation should succeed");
    TEST_ASSERT(p1 != p2, "Allocations should be different");
    TEST_ASSERT(p2 != p3, "Allocations should be different");

    size_t total, used, free_blks;
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 3, "Three blocks should be used");

    /* Free middle one */
    func_free(&alloc, p2);
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 2, "Two blocks should be used after freeing middle");

    /* Allocate again - should reuse freed block */
    void* p4 = func_malloc(&alloc, 64);
    TEST_ASSERT(p4 != NULL, "Reallocation should succeed");
    TEST_ASSERT(p4 == p2, "Should reuse freed block");

    /* Free all */
    func_free(&alloc, p1);
    func_free(&alloc, p3);
    func_free(&alloc, p4);

    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 0, "All blocks should be free");

    return 1;
}

/**
 * Test multi-block allocation
 */
static int test_multiblock_alloc(void) {
    uint8_t buf[TEST_BUF_SIZE];
    func_alloc_t alloc;

    func_alloc_init(&alloc, buf, TEST_BUF_SIZE);

    /* Allocate 3 blocks worth */
    size_t alloc_size = FUNC_ALLOC_BLOCK_SIZE * 3 - 10;
    void* p1 = func_malloc(&alloc, alloc_size);
    TEST_ASSERT(p1 != NULL, "Multi-block allocation should succeed");

    size_t total, used, free_blks;
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 3, "Three blocks should be used");

    /* Check reported size */
    size_t reported_size = func_alloc_size(&alloc, p1);
    TEST_ASSERT(reported_size == 3 * FUNC_ALLOC_BLOCK_SIZE, "Size should be 3 blocks");

    func_free(&alloc, p1);
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 0, "All blocks should be free after free");

    return 1;
}

/**
 * Test allocation failure when full
 */
static int test_alloc_full(void) {
    uint8_t buf[TEST_BUF_SIZE];
    func_alloc_t alloc;

    func_alloc_init(&alloc, buf, TEST_BUF_SIZE);

    size_t total, used, free_blks;
    func_alloc_stats(&alloc, &total, &used, &free_blks);

    /* Allocate all blocks */
    void** ptrs = (void**)malloc(total * sizeof(void*));
    TEST_ASSERT(ptrs != NULL, "Test setup malloc should succeed");

    for (size_t i = 0; i < total; i++) {
        ptrs[i] = func_malloc(&alloc, 1);
        TEST_ASSERT(ptrs[i] != NULL, "Allocation should succeed until full");
    }

    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(free_blks == 0, "No free blocks should remain");

    /* Next allocation should fail */
    void* p_fail = func_malloc(&alloc, 1);
    TEST_ASSERT(p_fail == NULL, "Allocation should fail when full");

    /* Free one and try again */
    func_free(&alloc, ptrs[0]);
    void* p_ok = func_malloc(&alloc, 1);
    TEST_ASSERT(p_ok != NULL, "Allocation should succeed after free");

    /* Cleanup */
    for (size_t i = 1; i < total; i++) {
        func_free(&alloc, ptrs[i]);
    }
    func_free(&alloc, p_ok);
    free(ptrs);

    return 1;
}

/**
 * Test that user data doesn't corrupt allocator metadata
 * This is the key test for the new safe implementation
 */
static int test_data_isolation(void) {
    uint8_t buf[TEST_BUF_SIZE];
    func_alloc_t alloc;

    func_alloc_init(&alloc, buf, TEST_BUF_SIZE);

    /* Allocate a block */
    void* p1 = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE);
    TEST_ASSERT(p1 != NULL, "Allocation should succeed");

    /* Fill with 0xFF (old implementation used this as marker) */
    memset(p1, 0xFF, FUNC_ALLOC_BLOCK_SIZE);

    /* Allocate another block */
    void* p2 = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE);
    TEST_ASSERT(p2 != NULL, "Second allocation should succeed");
    TEST_ASSERT(p2 != p1, "Should be different block");

    /* Fill with zeros (old implementation used this as free marker) */
    memset(p2, 0x00, FUNC_ALLOC_BLOCK_SIZE);

    /* Verify allocator still works correctly */
    size_t total, used, free_blks;
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 2, "Two blocks should still be marked as used");

    /* Free should still work */
    func_free(&alloc, p1);
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 1, "One block should be used after free");

    func_free(&alloc, p2);
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 0, "No blocks should be used after freeing all");

    return 1;
}

/**
 * Test writing various patterns to allocated memory
 */
static int test_pattern_write(void) {
    uint8_t buf[TEST_BUF_SIZE];
    func_alloc_t alloc;

    func_alloc_init(&alloc, buf, TEST_BUF_SIZE);

    /* Allocate multiple blocks */
    void* p1 = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE * 2);
    void* p2 = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE);
    void* p3 = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE * 3);

    TEST_ASSERT(p1 != NULL && p2 != NULL && p3 != NULL, "Allocations should succeed");

    /* Write various patterns */
    memset(p1, 0xAA, FUNC_ALLOC_BLOCK_SIZE * 2);
    memset(p2, 0x55, FUNC_ALLOC_BLOCK_SIZE);
    memset(p3, 0x00, FUNC_ALLOC_BLOCK_SIZE * 3);

    /* Verify sizes are still correct */
    TEST_ASSERT(func_alloc_size(&alloc, p1) == FUNC_ALLOC_BLOCK_SIZE * 2, "p1 size correct");
    TEST_ASSERT(func_alloc_size(&alloc, p2) == FUNC_ALLOC_BLOCK_SIZE, "p2 size correct");
    TEST_ASSERT(func_alloc_size(&alloc, p3) == FUNC_ALLOC_BLOCK_SIZE * 3, "p3 size correct");

    /* Free in different order */
    func_free(&alloc, p2);
    func_free(&alloc, p1);
    func_free(&alloc, p3);

    size_t total, used, free_blks;
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 0, "All blocks should be free");

    return 1;
}

/**
 * Test invalid free operations
 */
static int test_invalid_free(void) {
    uint8_t buf[TEST_BUF_SIZE];
    func_alloc_t alloc;

    func_alloc_init(&alloc, buf, TEST_BUF_SIZE);

    void* p1 = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE);
    TEST_ASSERT(p1 != NULL, "Allocation should succeed");

    /* Free NULL - should not crash */
    func_free(&alloc, NULL);

    /* Free invalid pointer - should not crash */
    func_free(&alloc, (void*)0x12345678);

    /* Free pointer not aligned to block - should not crash */
    func_free(&alloc, (uint8_t*)p1 + 1);

    /* Double free - should not crash or corrupt */
    func_free(&alloc, p1);
    func_free(&alloc, p1); /* Second free should be no-op */

    size_t total, used, free_blks;
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 0, "Block should be free after valid free");

    return 1;
}

/**
 * Test allocation with invalid parameters
 */
static int test_invalid_alloc(void) {
    uint8_t buf[TEST_BUF_SIZE];
    func_alloc_t alloc;
    func_alloc_t invalid_alloc = {0};

    func_alloc_init(&alloc, buf, TEST_BUF_SIZE);

    /* Allocate from NULL allocator */
    void* p = func_malloc(NULL, 64);
    TEST_ASSERT(p == NULL, "Should fail with NULL allocator");

    /* Allocate from uninitialized allocator */
    p = func_malloc(&invalid_alloc, 64);
    TEST_ASSERT(p == NULL, "Should fail with invalid allocator");

    /* Allocate zero bytes */
    p = func_malloc(&alloc, 0);
    TEST_ASSERT(p == NULL, "Should fail with zero size");

    /* Allocate too much */
    p = func_malloc(&alloc, TEST_BUF_SIZE * 2);
    TEST_ASSERT(p == NULL, "Should fail with oversized request");

    return 1;
}

/**
 * Test fragmentation and coalescing
 */
static int test_fragmentation(void) {
    uint8_t buf[TEST_BUF_SIZE];
    func_alloc_t alloc;

    func_alloc_init(&alloc, buf, TEST_BUF_SIZE);

    /* Allocate several single blocks */
    void* p1 = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE);
    void* p2 = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE);
    void* p3 = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE);
    void* p4 = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE);

    TEST_ASSERT(p1 && p2 && p3 && p4, "All allocations should succeed");

    /* Free alternating blocks to create fragmentation */
    func_free(&alloc, p2);
    func_free(&alloc, p4);

    /* Try to allocate 2 contiguous blocks - should fail due to fragmentation */
    void* p_big = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE * 2);
    /* This might succeed or fail depending on layout - just verify no crash */

    /* Free remaining to create contiguous space */
    func_free(&alloc, p1);
    func_free(&alloc, p3);
    if (p_big)
        func_free(&alloc, p_big);

    /* Now 2-block allocation should succeed */
    p_big = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE * 2);
    TEST_ASSERT(p_big != NULL, "Should succeed with contiguous free space");

    func_free(&alloc, p_big);

    return 1;
}

/**
 * Test func_alloc_size function
 */
static int test_alloc_size(void) {
    uint8_t buf[TEST_BUF_SIZE];
    func_alloc_t alloc;

    func_alloc_init(&alloc, buf, TEST_BUF_SIZE);

    /* Size of NULL */
    TEST_ASSERT(func_alloc_size(&alloc, NULL) == 0, "NULL should return 0");

    /* Size of invalid pointer */
    TEST_ASSERT(func_alloc_size(&alloc, (void*)0x12345678) == 0, "Invalid ptr should return 0");

    /* Size of valid allocations */
    void* p1 = func_malloc(&alloc, 1);
    TEST_ASSERT(func_alloc_size(&alloc, p1) == FUNC_ALLOC_BLOCK_SIZE, "1 byte alloc = 1 block");

    void* p2 = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE);
    TEST_ASSERT(func_alloc_size(&alloc, p2) == FUNC_ALLOC_BLOCK_SIZE, "Block size alloc = 1 block");

    void* p3 = func_malloc(&alloc, FUNC_ALLOC_BLOCK_SIZE + 1);
    TEST_ASSERT(func_alloc_size(&alloc, p3) == FUNC_ALLOC_BLOCK_SIZE * 2, "Block+1 alloc = 2 blocks");

    /* Size after free should be 0 */
    func_free(&alloc, p1);
    TEST_ASSERT(func_alloc_size(&alloc, p1) == 0, "Freed ptr should return 0");

    func_free(&alloc, p2);
    func_free(&alloc, p3);

    return 1;
}

/**
 * Stress test with many allocations
 */
static int test_stress(void) {
    uint8_t buf[TEST_BUF_SIZE];
    func_alloc_t alloc;

    func_alloc_init(&alloc, buf, TEST_BUF_SIZE);

#define STRESS_PTRS 100
    void* ptrs[STRESS_PTRS] = {0};

    /* Random-ish allocation and free pattern */
    for (int round = 0; round < 10; round++) {
        /* Allocate some */
        for (int i = 0; i < STRESS_PTRS; i++) {
            if (ptrs[i] == NULL) {
                size_t size = ((i * 17 + round * 31) % 3 + 1) * FUNC_ALLOC_BLOCK_SIZE;
                ptrs[i] = func_malloc(&alloc, size);
                if (ptrs[i]) {
                    /* Write pattern to verify no corruption */
                    memset(ptrs[i], (uint8_t)(i ^ round), size);
                }
            }
        }

        /* Free some */
        for (int i = 0; i < STRESS_PTRS; i++) {
            if (ptrs[i] && ((i + round) % 3 == 0)) {
                func_free(&alloc, ptrs[i]);
                ptrs[i] = NULL;
            }
        }
    }

    /* Free remaining */
    for (int i = 0; i < STRESS_PTRS; i++) {
        if (ptrs[i]) {
            func_free(&alloc, ptrs[i]);
        }
    }

    size_t total, used, free_blks;
    func_alloc_stats(&alloc, &total, &used, &free_blks);
    TEST_ASSERT(used == 0, "All blocks should be free after stress test");

    return 1;
}

/* ========== Main ========== */

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    printf("\n");
    printf("===========================================\n");
    printf("  func_allocator Unit Tests\n");
    printf("===========================================\n");
    printf("Block size: %d bytes\n", FUNC_ALLOC_BLOCK_SIZE);
    printf("Test buffer: %d bytes\n", TEST_BUF_SIZE);
    printf("\n");

    RUN_TEST(test_init);
    RUN_TEST(test_init_invalid);
    RUN_TEST(test_basic_alloc_free);
    RUN_TEST(test_multiple_allocs);
    RUN_TEST(test_multiblock_alloc);
    RUN_TEST(test_alloc_full);
    RUN_TEST(test_data_isolation);
    RUN_TEST(test_pattern_write);
    RUN_TEST(test_invalid_free);
    RUN_TEST(test_invalid_alloc);
    RUN_TEST(test_fragmentation);
    RUN_TEST(test_alloc_size);
    RUN_TEST(test_stress);

    printf("\n");
    printf("===========================================\n");
    printf("  Results: %d/%d tests passed\n", tests_passed, tests_run);
    printf("===========================================\n");
    printf("\n");

    return (tests_passed == tests_run) ? 0 : 1;
}

#endif /* FL_USE_ALLOCATOR_TEST */
