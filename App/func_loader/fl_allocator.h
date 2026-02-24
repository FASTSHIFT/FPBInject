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
 * @file   fl_allocator.h
 * @brief  Safe fixed-block memory allocator for FL_ALLOC_STATIC mode
 *
 * Uses bitmap for allocation tracking, separating metadata from user data.
 *
 * Buffer layout:
 *   [bitmap (ceil(n/8) bytes)] [size_table (n bytes)] [block0] [block1] ... [blockN-1]
 */

#ifndef FL_ALLOCATOR_H
#define FL_ALLOCATOR_H

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
    uint32_t magic;      /* Magic number for validation */
    uint8_t* bitmap;     /* Bitmap: 1 bit per block */
    uint8_t* size_table; /* Size table: block count per allocation */
    uint8_t* blocks;     /* Actual data blocks */
    size_t block_count;  /* Total number of blocks */
    size_t bitmap_size;  /* Size of bitmap in bytes */
} func_alloc_t;

/**
 * @brief Initialize the allocator with a buffer
 * @param alloc Allocator context
 * @param buf Buffer to use for allocation
 * @param size Size of buffer in bytes
 */
void func_alloc_init(func_alloc_t* alloc, void* buf, size_t size);

/**
 * @brief Allocate memory from the pool
 * @param alloc Allocator context
 * @param size Size in bytes to allocate
 * @return Pointer to allocated memory, or NULL on failure
 */
void* func_malloc(func_alloc_t* alloc, size_t size);

/**
 * @brief Free previously allocated memory
 * @param alloc Allocator context
 * @param ptr Pointer returned by func_malloc
 */
void func_free(func_alloc_t* alloc, void* ptr);

/**
 * @brief Get allocation statistics
 * @param alloc Allocator context
 * @param total_blocks Output: total blocks available
 * @param used_blocks Output: blocks currently in use
 * @param free_blocks Output: blocks currently free
 */
void func_alloc_stats(const func_alloc_t* alloc, size_t* total_blocks, size_t* used_blocks, size_t* free_blocks);

/**
 * @brief Check if allocator is valid and initialized
 * @param alloc Allocator context
 * @return true if valid, false otherwise
 */
bool func_alloc_is_valid(const func_alloc_t* alloc);

/**
 * @brief Get the size of an allocation in bytes
 * @param alloc Allocator context
 * @param ptr Pointer returned by func_malloc
 * @return Size in bytes (block-aligned), or 0 if invalid
 */
size_t func_alloc_size(const func_alloc_t* alloc, const void* ptr);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* FL_ALLOCATOR_H */
