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
 * @file   fl_cmd_mem.c
 * @brief  Memory command handlers (alloc/upload/read/write)
 */

#include "fl_cmd.h"
#include <string.h>

fl_error_t fl_cmd_alloc(fl_context_t* ctx, const cmd_args_t* args) {
    if (args->size == 0) {
        fl_response(false, "Missing --size");
        return FL_ERR_ARGS;
    }

    /* Verify CRC if provided: covers size(4B) */
    {
        uint32_t size32 = (uint32_t)args->size;
        if (!fl_verify_crc(args->crc, fl_crc16(&size32, sizeof(size32)))) {
            return FL_ERR_CRC;
        }
    }

    if (!ctx->malloc_cb) {
        fl_response(false, "No malloc_cb");
        return FL_ERR_STATE;
    }

    /* Free previous allocation if any */
    if (ctx->last_alloc != 0 && ctx->free_cb) {
        ctx->free_cb((void*)ctx->last_alloc);
        ctx->last_alloc = 0;
        ctx->last_alloc_size = 0;
    }

    void* p = ctx->malloc_cb(args->size);
    if (!p) {
        fl_response(false, "Alloc failed");
        return FL_ERR_ALLOC;
    }

    ctx->last_alloc = (uintptr_t)p;
    ctx->last_alloc_size = args->size;
    fl_response(true, "Allocated %u at 0x%08lX", (unsigned)args->size, (unsigned long)p);
    return FL_OK;
}

fl_error_t fl_cmd_upload(fl_context_t* ctx, const cmd_args_t* args) {
    if (!args->data) {
        fl_response(false, "Missing --data");
        return FL_ERR_ARGS;
    }

    uint8_t* buf = ctx->buf;
    bool verify = args->crc >= 0;

    ssize_t n = fl_base64_decode(args->data, buf, FL_BUF_SIZE);
    if (n < 0) {
        fl_response(false, "Invalid base64 data");
        return FL_ERR_ENCODE;
    }

    if (verify) {
        /* CRC covers: offset(4B) + len(4B) + data payload */
        uint32_t offset32 = (uint32_t)args->addr;
        uint32_t len32 = (uint32_t)n;
        uint16_t calc = 0xFFFF;
        calc = fl_crc16_base(calc, &offset32, sizeof(offset32));
        calc = fl_crc16_base(calc, &len32, sizeof(len32));
        calc = fl_crc16_base(calc, buf, n);
        if (!fl_verify_crc(args->crc, calc)) {
            /* CRC mismatch - free last_alloc in dynamic mode to prevent leak */
            if (ctx->last_alloc != 0 && ctx->free_cb) {
                ctx->free_cb((void*)ctx->last_alloc);
                ctx->last_alloc = 0;
                ctx->last_alloc_size = 0;
            }
            return FL_ERR_CRC;
        }
    }

    /* Upload to last_alloc */
    if (ctx->last_alloc == 0) {
        fl_response(false, "No allocation, call alloc first");
        return FL_ERR_STATE;
    }

    /* Bounds check: offset + data must fit within allocation */
    if (args->addr + (size_t)n > ctx->last_alloc_size) {
        fl_response(false, "Upload overflow: offset %lu + %d > alloc %u", (unsigned long)args->addr, n,
                    (unsigned)ctx->last_alloc_size);
        return FL_ERR_RANGE;
    }

    uint8_t* dest = (uint8_t*)(ctx->last_alloc + args->addr);

    memcpy(dest, buf, n);

    /* Flush data cache after upload to ensure code is visible to CPU */
    fl_flush_dcache(ctx, dest, n);

    /* Invalidate instruction cache to prevent stale code execution */
    fl_invalidate_icache(ctx, dest, n);

    fl_response(true, "Uploaded %d bytes to 0x%lX", n, (unsigned long)dest);
    return FL_OK;
}

fl_error_t fl_cmd_read(fl_context_t* ctx, const cmd_args_t* args) {
    uint8_t* buf = ctx->buf;
    char* b64_buf = ctx->b64_buf;
    int len = args->len;

    if (len <= 0 || (size_t)len > FL_BUF_SIZE) {
        fl_response(false, "Invalid length %d (max %d)", len, (int)FL_BUF_SIZE);
        return FL_ERR_RANGE;
    }

    /* Verify request CRC if provided: covers addr(4B) + len(4B) */
    {
        uint32_t addr32 = (uint32_t)args->addr;
        uint32_t len32 = (uint32_t)len;
        uint16_t calc = 0xFFFF;
        calc = fl_crc16_base(calc, &addr32, sizeof(addr32));
        calc = fl_crc16_base(calc, &len32, sizeof(len32));
        if (!fl_verify_crc(args->crc, calc)) {
            return FL_ERR_CRC;
        }
    }

    if (!args->force && !fl_check_addr_range(args->addr, len)) {
        fl_response(false, "Invalid address range 0x%08lX+%d (use --force to override)", (unsigned long)args->addr,
                    len);
        return FL_ERR_RANGE;
    }

    /* Read memory at the given address */
    const uint8_t* src = (const uint8_t*)args->addr;
    memcpy(buf, src, len);

    /* Base64 encode */
    if (fl_base64_encode(buf, len, b64_buf, FL_B64_BUF_SIZE) < 0) {
        fl_response(false, "Base64 encode failed");
        return FL_ERR_ENCODE;
    }

    /* CRC-16 covers: addr(4B) + len(4B) + data payload */
    uint32_t resp_addr32 = (uint32_t)args->addr;
    uint32_t resp_len32 = (uint32_t)len;
    uint16_t resp_crc = 0xFFFF;
    resp_crc = fl_crc16_base(resp_crc, &resp_addr32, sizeof(resp_addr32));
    resp_crc = fl_crc16_base(resp_crc, &resp_len32, sizeof(resp_len32));
    resp_crc = fl_crc16_base(resp_crc, buf, len);

    /* Output in segments to avoid buffer overflow */
    fl_print("[FLOK] READ %d bytes crc=0x%04X data=", len, (unsigned)resp_crc);
    fl_print_raw(b64_buf);
    fl_print_raw("\n[FLEND]\n");
    return FL_OK;
}

fl_error_t fl_cmd_write(fl_context_t* ctx, const cmd_args_t* args) {
    if (!args->data) {
        fl_response(false, "Missing --data");
        return FL_ERR_ARGS;
    }

    uint8_t* buf = ctx->buf;
    bool verify = args->crc >= 0;

    ssize_t n = fl_base64_decode(args->data, buf, FL_BUF_SIZE);
    if (n < 0) {
        fl_response(false, "Invalid base64 data");
        return FL_ERR_ENCODE;
    }

    if (!args->force && !fl_check_addr_range(args->addr, n)) {
        fl_response(false, "Invalid address range 0x%08lX+%d (use --force to override)", (unsigned long)args->addr, n);
        return FL_ERR_RANGE;
    }

    if (verify) {
        /* CRC covers: addr(4B) + len(4B) + data payload */
        uint32_t addr32 = (uint32_t)args->addr;
        uint32_t len32 = (uint32_t)n;
        uint16_t calc = 0xFFFF;
        calc = fl_crc16_base(calc, &addr32, sizeof(addr32));
        calc = fl_crc16_base(calc, &len32, sizeof(len32));
        calc = fl_crc16_base(calc, buf, n);
        if (!fl_verify_crc(args->crc, calc)) {
            return FL_ERR_CRC;
        }
    }

    /* Write to the specified address */
    uint8_t* dest = (uint8_t*)args->addr;
    memcpy(dest, buf, n);

    /* Flush data cache */
    fl_flush_dcache(ctx, dest, n);

    /* Invalidate instruction cache */
    fl_invalidate_icache(ctx, dest, n);

    fl_response(true, "WRITE %d bytes to 0x%lX", n, (unsigned long)args->addr);
    return FL_OK;
}
