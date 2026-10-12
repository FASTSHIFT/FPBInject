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
 * @file   fl_cmd_exec.c
 * @brief  exec command: run a command line on the target through a port callback
 *
 * Request (execute):  fl -c exec -d <base64> --seq <id> --timeout <ms> -r 0x<crc>
 * Request (query):    fl -c exec --seq <id> -r 0x<crc>          (no -d, never executes)
 *
 * Response (execute):
 *   [FLEXEC] seq=<id> crc=0x<crc>        <- before the command starts
 *   <command stdout / stderr>
 *   [FLOK] EXEC seq=<id> ret=<n> crc=0x<crc>
 *   [FLEND]
 *
 * CRC-16 (little-endian integers, init 0xFFFF):
 *   request : seq(4) + timeout(4) + len(4) + command bytes
 *   start   : seq(4)
 *   result  : seq(4) + ret(4)
 */

#include "fl_cmd.h"
#include <string.h>

static uint16_t exec_request_crc(int32_t seq, uint32_t timeout_ms, uint32_t len, const void* payload) {
    uint16_t crc = 0xFFFF;
    crc = fl_crc16_base(crc, &seq, sizeof(seq));
    crc = fl_crc16_base(crc, &timeout_ms, sizeof(timeout_ms));
    crc = fl_crc16_base(crc, &len, sizeof(len));
    if (len > 0) {
        crc = fl_crc16_base(crc, payload, len);
    }
    return crc;
}

static uint16_t exec_start_crc(int32_t seq) {
    return fl_crc16_base(0xFFFF, &seq, sizeof(seq));
}

static uint16_t exec_result_crc(int32_t seq, int32_t ret) {
    uint16_t crc = 0xFFFF;
    crc = fl_crc16_base(crc, &seq, sizeof(seq));
    crc = fl_crc16_base(crc, &ret, sizeof(ret));
    return crc;
}

/**
 * @brief Print the result line (+ [FLEND]) shared by execute, replay and failure
 * @note  A negative ret means the command could not be started: reported as [FLERR]
 */
static fl_error_t exec_report(int32_t seq, int32_t ret, bool replay) {
    const bool failed = ret < 0;

    fl_response(!failed, "EXEC seq=%d ret=%d crc=0x%04X%s%s", (int)seq, (int)ret, (unsigned)exec_result_crc(seq, ret),
                replay ? " replay=1" : "", failed ? " spawn failed" : "");
    return failed ? FL_ERR_IO : FL_OK;
}

/**
 * @brief Reply from the cached result if seq matches the last executed request
 * @return true if the reply was sent
 */
static bool exec_try_replay(const fl_context_t* ctx, int32_t seq, fl_error_t* result) {
    if (seq < 0 || !ctx->exec_seq_valid || ctx->exec_last_seq != seq) {
        return false;
    }
    *result = exec_report(seq, ctx->exec_last_ret, true);
    return true;
}

/* Query: no -d, report the cached result of a previous request, never execute */
static fl_error_t exec_query(fl_context_t* ctx, const cmd_args_t* args) {
    const int32_t seq = (int32_t)args->seq;
    fl_error_t result;

    if (args->seq < 0) {
        fl_response(false, "Missing --data");
        return FL_ERR_ARGS;
    }

    if (!fl_verify_crc(args->crc, exec_request_crc(seq, (uint32_t)args->timeout, 0, NULL))) {
        return FL_ERR_CRC;
    }

    if (exec_try_replay(ctx, seq, &result)) {
        return result;
    }

    fl_response(false, "EXEC seq=%d no record", (int)seq);
    return FL_ERR_STATE;
}

fl_error_t fl_cmd_exec(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->exec_cb) {
        fl_response(false, "No exec_cb");
        return FL_ERR_STATE;
    }

    /* A tampered command is far more harmful than tampered data: CRC is
     * mandatory unless the operator explicitly waives it (--force). */
    if (args->crc < 0 && !args->force) {
        fl_response(false, "Missing --crc");
        return FL_ERR_ARGS;
    }

    if (!args->data) {
        return exec_query(ctx, args);
    }

    /* Leave room for the terminating NUL */
    const ssize_t n = fl_base64_decode(args->data, ctx->buf, FL_BUF_SIZE - 1);
    if (n < 0) {
        fl_response(false, "Invalid base64 data");
        return FL_ERR_ENCODE;
    }

    const int32_t seq = (int32_t)args->seq;
    if (!fl_verify_crc(args->crc, exec_request_crc(seq, (uint32_t)args->timeout, (uint32_t)n, ctx->buf))) {
        return FL_ERR_CRC;
    }

    /* The command must be a real C string: a NUL inside would make the
     * executed text differ from the bytes the CRC protected. */
    if (n == 0 || memchr(ctx->buf, 0, (size_t)n) != NULL || args->timeout < 0) {
        fl_response(false, "Invalid command");
        return FL_ERR_ARGS;
    }
    ctx->buf[n] = '\0';

    fl_error_t result;
    if (exec_try_replay(ctx, seq, &result)) {
        return result;
    }

    /* Start marker: tells the host the request was accepted and the command
     * is about to run, so it must not resend the whole request any more. */
    fl_print("[FLEXEC] seq=%d crc=0x%04X\n", (int)seq, (unsigned)exec_start_crc(seq));

    const int ret = ctx->exec_cb(ctx->exec_user, (const char*)ctx->buf, (uint32_t)args->timeout);

    if (seq >= 0) {
        ctx->exec_seq_valid = true;
        ctx->exec_last_seq = seq;
        ctx->exec_last_ret = (int32_t)ret;
    }

    return exec_report(seq, (int32_t)ret, false);
}
