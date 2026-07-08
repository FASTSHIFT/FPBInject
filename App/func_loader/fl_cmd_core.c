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
 * @file   fl_cmd_core.c
 * @brief  Core command handlers (ping/echo/echoback/info/hello)
 */

#include "fl_cmd.h"
#include "fpb_attributes.h"
#include "fpbinject_version.h"
#include <string.h>

fl_error_t fl_cmd_ping(fl_context_t* ctx, const cmd_args_t* args) {
    (void)ctx;
    (void)args;
    fl_response(true, "PONG");
    return FL_OK;
}

fl_error_t fl_cmd_echo(fl_context_t* ctx, const cmd_args_t* args) {
    (void)ctx;
    /* Echo command for serial throughput testing.
     * Echoes back the data length and CRC for verification.
     * The data is hex-encoded, so actual byte count is strlen/2.
     */
    const char* data_str = args->data;
    size_t len = data_str ? strlen(data_str) / 2 : 0;
    uint16_t crc = 0;

    if (data_str && len > 0) {
        /* Calculate CRC of the hex string (not decoded bytes) */
        crc = fl_crc16(data_str, strlen(data_str));
    }

    fl_response(true, "ECHO %u Bytes, CRC 0x%04X", (unsigned)len, crc);
    return FL_OK;
}

fl_error_t fl_cmd_echoback(fl_context_t* ctx, const cmd_args_t* args) {
    /* Echoback command for download direction throughput testing.
     * Fills the send buffer with a deterministic pattern (i % 256),
     * base64-encodes it, and sends it back with CRC.
     * PC sends: fl -c echoback --len N
     */
    int len = args->len;
    if (len <= 0 || (size_t)len > FL_BUF_SIZE) {
        fl_response(false, "Invalid length %d (max %d)", len, (int)FL_BUF_SIZE);
        return FL_ERR_RANGE;
    }

    /* Fill buffer with deterministic pattern */
    for (int i = 0; i < len; i++) {
        ctx->buf[i] = (uint8_t)(i % 256);
    }

    /* Base64 encode */
    if (fl_base64_encode(ctx->buf, len, ctx->b64_buf, FL_B64_BUF_SIZE) < 0) {
        fl_response(false, "Base64 encode failed");
        return FL_ERR_ENCODE;
    }

    /* CRC over raw pattern bytes */
    uint16_t crc = fl_crc16(ctx->buf, len);

    /* Output in parts to avoid buffer overflow */
    fl_print("[FLOK] ECHOBACK %d bytes crc=0x%04X data=", len, (unsigned)crc);
    fl_print_raw(ctx->b64_buf);
    fl_print_raw("\n[FLEND]\n");
    return FL_OK;
}

fl_error_t fl_cmd_info(fl_context_t* ctx, const cmd_args_t* args) {
    (void)args;

    fl_println("FPBInject " FPBINJECT_VERSION_STRING);
    fl_println("Build: " __DATE__ " " __TIME__);

    fl_cmd_print_fpb_info(ctx);

#if FL_USE_FILE
    fl_println("FileTransfer: %s", ctx->file_ctx.fs ? "enabled" : "disabled");
#else
    fl_println("FileTransfer: not compiled");
#endif

    fl_response(true, "Info complete");
    return FL_OK;
}

FPB_NOINLINE void fl_hello(void) {
    fl_response(true, "HELLO from original fl_hello(%p) function!", (void*)fl_hello);
}

fl_error_t fl_cmd_hello(fl_context_t* ctx, const cmd_args_t* args) {
    (void)ctx;
    (void)args;
    fl_hello();
    return FL_OK;
}
