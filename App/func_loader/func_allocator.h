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
 * @file   func_allocator.h
 * @brief  Simple fixed-block memory allocator for FL_ALLOC_STATIC mode
 *
 * Header-only implementation. Buffer layout:
 *   [used[0]..used[n-1]] [block0] [block1] ... [blockN-1]
 */

#ifndef FUNC_ALLOCATOR_H
#define FUNC_ALLOCATOR_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifndef FUNC_ALLOC_BLOCK_SIZE
#define FUNC_ALLOC_BLOCK_SIZE 64
#endif

typedef struct {
    uint8_t* buf;
    size_t block_count;
} func_alloc_t;

static inline void func_alloc_init(func_alloc_t* alloc, void* buf, size_t size) {
    alloc->buf = (uint8_t*)buf;

    /* header: 1 byte per block, blocks: FUNC_ALLOC_BLOCK_SIZE each */
    /* n + n * BLOCK_SIZE <= size => n <= size / (1 + BLOCK_SIZE) */
    alloc->block_count = size / (1 + FUNC_ALLOC_BLOCK_SIZE);

    /* Clear used flags */
    for (size_t i = 0; i < alloc->block_count; i++) {
        alloc->buf[i] = 0;
    }
}

static inline void* func_malloc(func_alloc_t* alloc, size_t size) {
    if (size == 0 || alloc->block_count == 0) {
        return NULL;
    }

    /* Calculate blocks needed */
    size_t blocks_needed = (size + FUNC_ALLOC_BLOCK_SIZE - 1) / FUNC_ALLOC_BLOCK_SIZE;
    if (blocks_needed > alloc->block_count) {
        return NULL;
    }

    /* Find contiguous free blocks */
    for (size_t i = 0; i <= alloc->block_count - blocks_needed; i++) {
        bool found = true;
        for (size_t j = 0; j < blocks_needed; j++) {
            if (alloc->buf[i + j] != 0) {
                found = false;
                break;
            }
        }

        if (found) {
            /* Mark first block with block count, rest with 0xFF */
            alloc->buf[i] = blocks_needed;
            for (size_t j = 1; j < blocks_needed; j++) {
                alloc->buf[i + j] = 0xFF;
            }

            return alloc->buf + alloc->block_count + i * FUNC_ALLOC_BLOCK_SIZE;
        }
    }

    return NULL;
}

static inline void func_free(func_alloc_t* alloc, void* ptr) {
    if (ptr == NULL || alloc->block_count == 0) {
        return;
    }

    uint8_t* blocks_start = alloc->buf + alloc->block_count;
    uint8_t* p = (uint8_t*)ptr;

    if (p < blocks_start) {
        return;
    }

    size_t idx = (p - blocks_start) / FUNC_ALLOC_BLOCK_SIZE;
    if (idx >= alloc->block_count || p != blocks_start + idx * FUNC_ALLOC_BLOCK_SIZE) {
        return;
    }

    uint8_t blocks_used = alloc->buf[idx];
    if (blocks_used == 0 || blocks_used > alloc->block_count) {
        return;
    }

    for (size_t j = 0; j < blocks_used; j++) {
        alloc->buf[idx + j] = 0;
    }
}

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* FUNC_ALLOCATOR_H */
