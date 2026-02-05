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
 * @file   func_allocator.c
 * @brief  Safe fixed-block memory allocator implementation
 */

#include "func_allocator.h"
#include <string.h>

/* Magic number for validation */
#define FUNC_ALLOC_MAGIC 0xFA110CA7

/* Helper: set bit in bitmap */
static inline void set_bit(uint8_t* bitmap, size_t idx) {
    bitmap[idx / 8] |= (1U << (idx % 8));
}

/* Helper: clear bit in bitmap */
static inline void clear_bit(uint8_t* bitmap, size_t idx) {
    bitmap[idx / 8] &= ~(1U << (idx % 8));
}

/* Helper: test bit in bitmap */
static inline bool test_bit(const uint8_t* bitmap, size_t idx) {
    return (bitmap[idx / 8] & (1U << (idx % 8))) != 0;
}

void func_alloc_init(func_alloc_t* alloc, void* buf, size_t size) {
    if (alloc == NULL || buf == NULL || size == 0) {
        if (alloc) {
            alloc->magic = 0;
            alloc->block_count = 0;
        }
        return;
    }

    uint8_t* ptr = (uint8_t*)buf;

    /*
     * Calculate layout:
     * Let n = block_count
     * bitmap_size = ceil(n/8)
     * size_table_size = n
     * blocks_size = n * FUNC_ALLOC_BLOCK_SIZE
     *
     * Total overhead = bitmap_size + size_table_size = ceil(n/8) + n
     *
     * We need: ceil(n/8) + n + n * BLOCK_SIZE <= size
     */
    size_t overhead_per_block = 1; /* size_table: 1 byte per block */
    size_t total_per_block = FUNC_ALLOC_BLOCK_SIZE + overhead_per_block;

    /* Initial estimate (ignoring bitmap for now) */
    size_t n = size / (total_per_block + 1); /* +1 for bitmap overhead estimate */

    /* Refine: account for actual bitmap size */
    while (n > 0) {
        size_t bitmap_sz = (n + 7) / 8;
        size_t needed = bitmap_sz + n + n * FUNC_ALLOC_BLOCK_SIZE;
        if (needed <= size) {
            break;
        }
        n--;
    }

    if (n == 0) {
        alloc->magic = 0;
        alloc->block_count = 0;
        return;
    }

    /* Setup layout */
    alloc->bitmap_size = (n + 7) / 8;
    alloc->bitmap = ptr;
    alloc->size_table = ptr + alloc->bitmap_size;
    alloc->blocks = alloc->size_table + n;
    alloc->block_count = n;
    alloc->magic = FUNC_ALLOC_MAGIC;

    /* Clear metadata */
    memset(alloc->bitmap, 0, alloc->bitmap_size);
    memset(alloc->size_table, 0, n);
}

void* func_malloc(func_alloc_t* alloc, size_t size) {
    if (alloc == NULL || alloc->magic != FUNC_ALLOC_MAGIC || size == 0 || alloc->block_count == 0) {
        return NULL;
    }

    /* Calculate blocks needed */
    size_t blocks_needed = (size + FUNC_ALLOC_BLOCK_SIZE - 1) / FUNC_ALLOC_BLOCK_SIZE;
    if (blocks_needed > alloc->block_count || blocks_needed > 255) {
        return NULL; /* size_table uses uint8_t, max 255 blocks per alloc */
    }

    /* Find contiguous free blocks using bitmap */
    for (size_t i = 0; i <= alloc->block_count - blocks_needed; i++) {
        bool found = true;

        /* Check if all needed blocks are free */
        for (size_t j = 0; j < blocks_needed; j++) {
            if (test_bit(alloc->bitmap, i + j)) {
                found = false;
                /* Skip to after this used block */
                i = i + j;
                break;
            }
        }

        if (found) {
            /* Mark blocks as used in bitmap */
            for (size_t j = 0; j < blocks_needed; j++) {
                set_bit(alloc->bitmap, i + j);
            }

            /* Store allocation size in size_table */
            alloc->size_table[i] = (uint8_t)blocks_needed;

            return alloc->blocks + i * FUNC_ALLOC_BLOCK_SIZE;
        }
    }

    return NULL;
}

void func_free(func_alloc_t* alloc, void* ptr) {
    if (alloc == NULL || alloc->magic != FUNC_ALLOC_MAGIC || ptr == NULL || alloc->block_count == 0) {
        return;
    }

    uint8_t* p = (uint8_t*)ptr;

    /* Validate pointer is within blocks region */
    if (p < alloc->blocks) {
        return;
    }

    size_t offset = (size_t)(p - alloc->blocks);

    /* Check alignment to block boundary */
    if (offset % FUNC_ALLOC_BLOCK_SIZE != 0) {
        return;
    }

    size_t idx = offset / FUNC_ALLOC_BLOCK_SIZE;
    if (idx >= alloc->block_count) {
        return;
    }

    /* Verify this is an allocation start (has size in size_table) */
    uint8_t blocks_used = alloc->size_table[idx];
    if (blocks_used == 0 || blocks_used > alloc->block_count - idx) {
        return;
    }

    /* Verify all blocks are actually marked as used */
    for (size_t j = 0; j < blocks_used; j++) {
        if (!test_bit(alloc->bitmap, idx + j)) {
            return; /* Corruption detected: block not marked as used */
        }
    }

    /* Clear bitmap bits and size_table entry */
    for (size_t j = 0; j < blocks_used; j++) {
        clear_bit(alloc->bitmap, idx + j);
    }
    alloc->size_table[idx] = 0;
}

void func_alloc_stats(const func_alloc_t* alloc, size_t* total_blocks, size_t* used_blocks, size_t* free_blocks) {
    if (alloc == NULL || alloc->magic != FUNC_ALLOC_MAGIC) {
        if (total_blocks)
            *total_blocks = 0;
        if (used_blocks)
            *used_blocks = 0;
        if (free_blocks)
            *free_blocks = 0;
        return;
    }

    size_t used = 0;
    for (size_t i = 0; i < alloc->block_count; i++) {
        if (test_bit(alloc->bitmap, i)) {
            used++;
        }
    }

    if (total_blocks)
        *total_blocks = alloc->block_count;
    if (used_blocks)
        *used_blocks = used;
    if (free_blocks)
        *free_blocks = alloc->block_count - used;
}

bool func_alloc_is_valid(const func_alloc_t* alloc) {
    return alloc != NULL && alloc->magic == FUNC_ALLOC_MAGIC && alloc->block_count > 0;
}

size_t func_alloc_size(const func_alloc_t* alloc, const void* ptr) {
    if (alloc == NULL || alloc->magic != FUNC_ALLOC_MAGIC || ptr == NULL || alloc->block_count == 0) {
        return 0;
    }

    const uint8_t* p = (const uint8_t*)ptr;

    if (p < alloc->blocks) {
        return 0;
    }

    size_t offset = (size_t)(p - alloc->blocks);
    if (offset % FUNC_ALLOC_BLOCK_SIZE != 0) {
        return 0;
    }

    size_t idx = offset / FUNC_ALLOC_BLOCK_SIZE;
    if (idx >= alloc->block_count) {
        return 0;
    }

    uint8_t blocks_used = alloc->size_table[idx];
    if (blocks_used == 0) {
        return 0;
    }

    return (size_t)blocks_used * FUNC_ALLOC_BLOCK_SIZE;
}
