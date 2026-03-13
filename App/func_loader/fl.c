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
 * @file   func_loader.c
 * @brief  Function loader core implementation
 */

#include "fl.h"
#include "fl_log.h"
#include "fpbinject_version.h"

/* External argparse support */
#ifdef FL_USE_EXTERNAL_ARGPARSE
#include FL_USE_EXTERNAL_ARGPARSE
#define fl_argparse_init argparse_init
#define fl_argparse_parse argparse_parse
#define fl_argparse_usage argparse_usage
#define fl_argparse_describe argparse_describe
#define fl_argparse_help_cb argparse_help_cb
#define fl_argparse_help_cb_no_exit argparse_help_cb_no_exit
#else
#include "argparse/argparse.h"
#endif

#include "fpb_inject.h"
#include "fpb_trampoline.h"
#include "fpb_debugmon.h"
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

static uint16_t calc_crc16_base(uint16_t crc, const void* data, size_t len) {
    static const uint16_t s_crc16_table[256] = {
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7, 0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD,
        0xE1CE, 0xF1EF, 0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6, 0x9339, 0x8318, 0xB37B, 0xA35A,
        0xD3BD, 0xC39C, 0xF3FF, 0xE3DE, 0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485, 0xA56A, 0xB54B,
        0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D, 0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
        0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC, 0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861,
        0x2802, 0x3823, 0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B, 0x5AF5, 0x4AD4, 0x7AB7, 0x6A96,
        0x1A71, 0x0A50, 0x3A33, 0x2A12, 0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A, 0x6CA6, 0x7C87,
        0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41, 0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
        0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70, 0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A,
        0x9F59, 0x8F78, 0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F, 0x1080, 0x00A1, 0x30C2, 0x20E3,
        0x5004, 0x4025, 0x7046, 0x6067, 0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E, 0x02B1, 0x1290,
        0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256, 0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
        0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405, 0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E,
        0xC71D, 0xD73C, 0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634, 0xD94C, 0xC96D, 0xF90E, 0xE92F,
        0x99C8, 0x89E9, 0xB98A, 0xA9AB, 0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3, 0xCB7D, 0xDB5C,
        0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A, 0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
        0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9, 0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83,
        0x1CE0, 0x0CC1, 0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8, 0x6E17, 0x7E36, 0x4E55, 0x5E74,
        0x2E93, 0x3EB2, 0x0ED1, 0x1EF0,
    };

    const uint8_t* ptr = data;
    while (len--) {
        crc = (crc << 8) ^ s_crc16_table[(crc >> 8) ^ *ptr++];
    }
    return crc;
}

static uint16_t calc_crc16(const void* data, size_t len) {
    return calc_crc16_base(0xFFFF, data, len);
}

static int base64_to_bytes(const char* b64, uint8_t* out, size_t max) {
    /* Base64 decoding table: ASCII -> 6-bit value, 255 = invalid, 64 = padding */
    static const uint8_t s_b64_dec[128] = {
        255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, /* 0-15 */
        255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, /* 16-31 */
        255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 62,  255, 255, 255, 63,  /* 32-47: +,/ */
        52,  53,  54,  55,  56,  57,  58,  59,  60,  61,  255, 255, 255, 64,  255, 255, /* 48-63: 0-9,= */
        255, 0,   1,   2,   3,   4,   5,   6,   7,   8,   9,   10,  11,  12,  13,  14,  /* 64-79: A-O */
        15,  16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  255, 255, 255, 255, 255, /* 80-95: P-Z */
        255, 26,  27,  28,  29,  30,  31,  32,  33,  34,  35,  36,  37,  38,  39,  40,  /* 96-111: a-o */
        41,  42,  43,  44,  45,  46,  47,  48,  49,  50,  51,  255, 255, 255, 255, 255, /* 112-127: p-z */
    };

    if (!b64 || !out)
        return -1;

    size_t b64_len = strlen(b64);
    if (b64_len == 0 || b64_len % 4 != 0)
        return -1;

    size_t out_len = (b64_len / 4) * 3;
    /* Adjust for padding */
    if (b64[b64_len - 1] == '=')
        out_len--;
    if (b64_len >= 2 && b64[b64_len - 2] == '=')
        out_len--;

    if (out_len > max)
        return -1;

    size_t i = 0, j = 0;
    while (i < b64_len) {
        uint8_t c0 = (uint8_t)b64[i];
        uint8_t c1 = (uint8_t)b64[i + 1];
        uint8_t c2 = (uint8_t)b64[i + 2];
        uint8_t c3 = (uint8_t)b64[i + 3];

        if (c0 >= 128 || c1 >= 128 || c2 >= 128 || c3 >= 128)
            return -1;

        uint8_t v0 = s_b64_dec[c0];
        uint8_t v1 = s_b64_dec[c1];
        uint8_t v2 = s_b64_dec[c2];
        uint8_t v3 = s_b64_dec[c3];

        if (v0 == 255 || v1 == 255 || (v2 == 255 && v2 != 64) || (v3 == 255 && v3 != 64))
            return -1;

        /* Decode 4 base64 chars -> up to 3 bytes */
        out[j++] = (v0 << 2) | (v1 >> 4);
        if (j < out_len && v2 != 64) {
            out[j++] = ((v1 & 0x0F) << 4) | (v2 >> 2);
            if (j < out_len && v3 != 64) {
                out[j++] = ((v2 & 0x03) << 6) | v3;
            }
        }
        i += 4;
    }

    return (int)out_len;
}

static int bytes_to_base64(const uint8_t* data, size_t len, char* out, size_t max) {
    /* Base64 encoding table */
    static const char s_b64_enc[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

    if (!data || !out || max == 0)
        return -1;

    size_t out_len = ((len + 2) / 3) * 4;
    if (out_len + 1 > max)
        return -1;

    size_t j = 0;
    for (size_t i = 0; i < len; i += 3) {
        uint8_t b0 = data[i];
        uint8_t b1 = (i + 1 < len) ? data[i + 1] : 0;
        uint8_t b2 = (i + 2 < len) ? data[i + 2] : 0;

        out[j++] = s_b64_enc[b0 >> 2];
        out[j++] = s_b64_enc[((b0 & 0x03) << 4) | (b1 >> 4)];
        out[j++] = (i + 1 < len) ? s_b64_enc[((b1 & 0x0F) << 2) | (b2 >> 6)] : '=';
        out[j++] = (i + 2 < len) ? s_b64_enc[b2 & 0x3F] : '=';
    }
    out[j] = '\0';

    return (int)j;
}

void fl_init_default(fl_context_t* ctx) {
    memset(ctx, 0, sizeof(fl_context_t));
}

void fl_init(fl_context_t* ctx) {
    fpb_init();
    fl_log_init(ctx->output_cb, ctx->output_user);
    ctx->is_inited = true;
}

bool fl_is_inited(fl_context_t* ctx) {
    return ctx->is_inited;
}

static void fl_flush_dcache(fl_context_t* ctx, const void* addr, size_t len) {
    if (ctx->flush_dcache_cb) {
        ctx->flush_dcache_cb((uintptr_t)addr, (uintptr_t)addr + len);
    }
}

/**
 * @brief  Check if [addr, addr+len) is a safe memory range
 * @note   Rejects NULL pointer and address overflow (wrapping past 0xFFFFFFFF)
 * @return true if the range is safe to access
 */
static bool fl_check_addr_range(uintptr_t addr, size_t len) {
    if (addr == 0 || len == 0) {
        return false;
    }

    /* Check if addr + len - 1 overflows past 0xFFFFFFFF */
    if ((uint32_t)(addr + len - 1) < (uint32_t)addr) {
        return false;
    }

    return true;
}

/* ===========================
   COMMAND ARGS & HANDLER TYPE
   =========================== */

/**
 * @brief Parsed command arguments (shared by all handlers)
 */
typedef struct {
    const char* cmd;
    const char* data;
    uintptr_t addr;
    uintptr_t orig;
    uintptr_t target;
    int crc; /* -1 = no CRC provided */
    int len;
    int size;
    int comp;
    int all;
    int enable; /* -1 = not specified, 0 = disable, 1 = enable */
    int force;
    const char* path;
    const char* newpath;
    const char* mode;
} cmd_args_t;

/**
 * @brief Command handler function pointer
 * @return 0 on success, -1 on argument validation error
 */
typedef int (*cmd_handler_t)(fl_context_t* ctx, const cmd_args_t* args);

/* ===========================
   COMMAND IMPLEMENTATIONS
   =========================== */

static int cmd_ping(fl_context_t* ctx, const cmd_args_t* args) {
    (void)ctx;
    (void)args;
    fl_response(true, "PONG");
    return 0;
}

static int cmd_echo(fl_context_t* ctx, const cmd_args_t* args) {
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
        crc = calc_crc16(data_str, strlen(data_str));
    }

    fl_response(true, "ECHO %u Bytes, CRC 0x%04X", (unsigned)len, crc);
    return 0;
}

static int cmd_echoback(fl_context_t* ctx, const cmd_args_t* args) {
    /* Echoback command for download direction throughput testing.
     * Fills the send buffer with a deterministic pattern (i % 256),
     * base64-encodes it, and sends it back with CRC.
     * PC sends: fl -c echoback --len N
     */
    int len = args->len;
    if (len <= 0 || (size_t)len > FL_BUF_SIZE) {
        fl_response(false, "Invalid length %d (max %d)", len, (int)FL_BUF_SIZE);
        return 0;
    }

    /* Fill buffer with deterministic pattern */
    for (int i = 0; i < len; i++) {
        ctx->buf[i] = (uint8_t)(i % 256);
    }

    /* Base64 encode */
    if (bytes_to_base64(ctx->buf, len, ctx->b64_buf, FL_B64_BUF_SIZE) < 0) {
        fl_response(false, "Base64 encode failed");
        return 0;
    }

    /* CRC over raw pattern bytes */
    uint16_t crc = calc_crc16(ctx->buf, len);

    /* Output in parts to avoid buffer overflow */
    fl_print("[FLOK] ECHOBACK %d bytes crc=0x%04X data=", len, (unsigned)crc);
    fl_print_raw(ctx->b64_buf);
    fl_print_raw("\n[FLEND]\n");
    return 0;
}

static int cmd_info(fl_context_t* ctx, const cmd_args_t* args) {
    (void)args;
    const fpb_state_t* fpb = fpb_get_state();
    fpb_info_t fpb_info;
    uint32_t num_comps = fpb->num_code_comp;
    uint32_t active_count = 0;
    size_t total_used = 0;

    /* Count active slots and total code size */
    for (uint32_t i = 0; i < num_comps && i < FL_MAX_SLOTS; i++) {
        if (ctx->slots[i].active) {
            active_count++;
            total_used += ctx->slots[i].code_size;
        }
    }

    fl_println("FPBInject " FPBINJECT_VERSION_STRING);
    fl_println("Build: " __DATE__ " " __TIME__);
    fl_println("Used: %u", (unsigned)total_used);
    fl_println("Slots: %u/%u", (unsigned)active_count, (unsigned)num_comps);

#if FL_USE_FILE
    fl_println("FileTransfer: %s", ctx->file_ctx.fs ? "enabled" : "disabled");
#else
    fl_println("FileTransfer: not compiled");
#endif

    /* Get and print FPB detailed information */
    if (fpb_get_info(&fpb_info) == FPB_OK) {
        const char* rev_str = (fpb_info.rev == 0) ? "v1" : (fpb_info.rev == 1) ? "v2" : "unknown";
        fl_println("FPB: %s, %u code + %u lit = %u total, %s", rev_str, fpb_info.num_code_comp, fpb_info.num_lit_comp,
                   fpb_info.total_comp, fpb_info.enabled ? "enabled" : "disabled");

        /* Print FP_REMAP info */
        fl_println("FP_REMAP: 0x%08lX, base=0x%08lX, remap %s", (unsigned long)fpb_info.remap_raw,
                   (unsigned long)fpb_info.remap_base, fpb_info.remap_supported ? "supported" : "not supported");

        /* Print each comparator status with hardware register info */
        static const char* replace_mode_str[] = {"remap", "bp_lo", "bp_hi", "bp_both"};
        for (uint32_t i = 0; i < num_comps && i < FL_MAX_SLOTS && i < FPB_MAX_CODE_COMP; i++) {
            fl_slot_state_t* slot = &ctx->slots[i];
            fpb_comp_info_t* comp = &fpb_info.comp[i];
            const char* mode_str = (comp->replace < 4) ? replace_mode_str[comp->replace] : "?";

            if (slot->active) {
                fl_println("Slot[%u]: 0x%08lX -> 0x%08lX, %u bytes (COMP=0x%08lX, %s, %s)", (unsigned)i,
                           (unsigned long)slot->orig_addr, (unsigned long)slot->target_addr, (unsigned)slot->code_size,
                           (unsigned long)comp->comp_raw, mode_str, comp->enabled ? "on" : "off");
            } else {
                fl_println("Slot[%u]: empty (COMP=0x%08lX, %s)", (unsigned)i, (unsigned long)comp->comp_raw,
                           comp->enabled ? "on" : "off");
            }
        }
    } else {
        fl_println("FPB: not available");
    }

    fl_response(true, "Info complete");
    return 0;
}

static int cmd_alloc(fl_context_t* ctx, const cmd_args_t* args) {
    if (args->size == 0) {
        fl_response(false, "Missing --size");
        return -1;
    }

    if (!ctx->malloc_cb) {
        fl_response(false, "No malloc_cb");
        return 0;
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
        return 0;
    }

    ctx->last_alloc = (uintptr_t)p;
    ctx->last_alloc_size = args->size;
    fl_response(true, "Allocated %u at 0x%08lX", (unsigned)args->size, (unsigned long)p);
    return 0;
}

static int cmd_upload(fl_context_t* ctx, const cmd_args_t* args) {
    if (!args->data) {
        fl_response(false, "Missing --data");
        return -1;
    }

    uint8_t* buf = ctx->buf;
    bool verify = args->crc >= 0;

    int n = base64_to_bytes(args->data, buf, FL_BUF_SIZE);
    if (n < 0) {
        fl_response(false, "Invalid base64 data");
        return 0;
    }

    if (verify) {
        /* CRC covers: offset(4B) + len(4B) + data payload */
        uint32_t offset32 = (uint32_t)args->addr;
        uint32_t len32 = (uint32_t)n;
        uint16_t calc = 0xFFFF;
        calc = calc_crc16_base(calc, &offset32, sizeof(offset32));
        calc = calc_crc16_base(calc, &len32, sizeof(len32));
        calc = calc_crc16_base(calc, buf, n);
        if (calc != (uint16_t)args->crc) {
            /* CRC mismatch - free last_alloc in dynamic mode to prevent leak */
            if (ctx->last_alloc != 0 && ctx->free_cb) {
                ctx->free_cb((void*)ctx->last_alloc);
                ctx->last_alloc = 0;
                ctx->last_alloc_size = 0;
            }
            fl_response(false, "CRC mismatch: 0x%04X != 0x%04X", (unsigned)args->crc, (unsigned)calc);
            return 0;
        }
    }

    /* Upload to last_alloc */
    if (ctx->last_alloc == 0) {
        fl_response(false, "No allocation, call alloc first");
        return 0;
    }
    uint8_t* dest = (uint8_t*)(ctx->last_alloc + args->addr);

    memcpy(dest, buf, n);

    /* Flush data cache after upload to ensure code is visible to CPU */
    fl_flush_dcache(ctx, dest, n);

    fl_response(true, "Uploaded %d bytes to 0x%lX", n, (unsigned long)dest);
    return 0;
}

static int cmd_read(fl_context_t* ctx, const cmd_args_t* args) {
    uint8_t* buf = ctx->buf;
    char* b64_buf = ctx->b64_buf;
    int len = args->len;

    if (len <= 0 || (size_t)len > FL_BUF_SIZE) {
        fl_response(false, "Invalid length %d (max %d)", len, (int)FL_BUF_SIZE);
        return 0;
    }

    /* Verify request CRC if provided: covers addr(4B) + len(4B) */
    if (args->crc >= 0) {
        uint32_t addr32 = (uint32_t)args->addr;
        uint32_t len32 = (uint32_t)len;
        uint16_t calc = 0xFFFF;
        calc = calc_crc16_base(calc, &addr32, sizeof(addr32));
        calc = calc_crc16_base(calc, &len32, sizeof(len32));
        if (calc != (uint16_t)args->crc) {
            fl_response(false, "Request CRC mismatch: 0x%04X != 0x%04X", (unsigned)args->crc, (unsigned)calc);
            return 0;
        }
    }

    if (!args->force && !fl_check_addr_range(args->addr, len)) {
        fl_response(false, "Invalid address range 0x%08lX+%d (use --force to override)", (unsigned long)args->addr,
                    len);
        return 0;
    }

    /* Read memory at the given address */
    const uint8_t* src = (const uint8_t*)args->addr;
    memcpy(buf, src, len);

    /* Base64 encode */
    if (bytes_to_base64(buf, len, b64_buf, FL_B64_BUF_SIZE) < 0) {
        fl_response(false, "Base64 encode failed");
        return 0;
    }

    /* CRC-16 covers: addr(4B) + len(4B) + data payload */
    uint32_t resp_addr32 = (uint32_t)args->addr;
    uint32_t resp_len32 = (uint32_t)len;
    uint16_t resp_crc = 0xFFFF;
    resp_crc = calc_crc16_base(resp_crc, &resp_addr32, sizeof(resp_addr32));
    resp_crc = calc_crc16_base(resp_crc, &resp_len32, sizeof(resp_len32));
    resp_crc = calc_crc16_base(resp_crc, buf, len);

    /* Output in segments to avoid buffer overflow */
    fl_print("[FLOK] READ %d bytes crc=0x%04X data=", len, (unsigned)resp_crc);
    fl_print_raw(b64_buf);
    fl_print_raw("\n[FLEND]\n");
    return 0;
}

static int cmd_write(fl_context_t* ctx, const cmd_args_t* args) {
    if (!args->data) {
        fl_response(false, "Missing --data");
        return -1;
    }

    uint8_t* buf = ctx->buf;
    bool verify = args->crc >= 0;

    int n = base64_to_bytes(args->data, buf, FL_BUF_SIZE);
    if (n < 0) {
        fl_response(false, "Invalid base64 data");
        return 0;
    }

    if (!args->force && !fl_check_addr_range(args->addr, n)) {
        fl_response(false, "Invalid address range 0x%08lX+%d (use --force to override)", (unsigned long)args->addr, n);
        return 0;
    }

    if (verify) {
        /* CRC covers: addr(4B) + len(4B) + data payload */
        uint32_t addr32 = (uint32_t)args->addr;
        uint32_t len32 = (uint32_t)n;
        uint16_t calc = 0xFFFF;
        calc = calc_crc16_base(calc, &addr32, sizeof(addr32));
        calc = calc_crc16_base(calc, &len32, sizeof(len32));
        calc = calc_crc16_base(calc, buf, n);
        if (calc != (uint16_t)args->crc) {
            fl_response(false, "CRC mismatch: 0x%04X != 0x%04X", (unsigned)args->crc, (unsigned)calc);
            return 0;
        }
    }

    /* Write to the specified address */
    uint8_t* dest = (uint8_t*)args->addr;
    memcpy(dest, buf, n);

    /* Flush data cache */
    fl_flush_dcache(ctx, dest, n);

    fl_response(true, "WRITE %d bytes to 0x%lX", n, (unsigned long)args->addr);
    return 0;
}

/**
 * @brief  Verify CRC for patch commands: covers comp(4B) + orig(4B) + target(4B)
 * @return true if CRC matches or no CRC provided (crc < 0)
 */
static bool verify_patch_crc(int crc, uint32_t comp, uintptr_t orig, uintptr_t target) {
    if (crc < 0)
        return true;
    uint32_t comp32 = comp;
    uint32_t orig32 = (uint32_t)orig;
    uint32_t target32 = (uint32_t)target;
    uint16_t calc = 0xFFFF;
    calc = calc_crc16_base(calc, &comp32, sizeof(comp32));
    calc = calc_crc16_base(calc, &orig32, sizeof(orig32));
    calc = calc_crc16_base(calc, &target32, sizeof(target32));
    if (calc != (uint16_t)crc) {
        fl_response(false, "CRC mismatch: 0x%04X != 0x%04X", (unsigned)crc, (unsigned)calc);
        return false;
    }
    return true;
}

static int cmd_patch(fl_context_t* ctx, const cmd_args_t* args) {
    if (args->orig == 0 || args->target == 0) {
        fl_response(false, "Missing --orig/--target");
        return -1;
    }

    if (!verify_patch_crc(args->crc, args->comp, args->orig, args->target))
        return 0;

    if ((uint32_t)args->comp >= fpb_get_state()->num_code_comp || (uint32_t)args->comp >= FL_MAX_SLOTS) {
        fl_response(false, "Invalid comp %lu", (unsigned long)args->comp);
        return 0;
    }

    fpb_result_t ret = fpb_set_patch(args->comp, args->orig, args->target);
    if (ret != FPB_OK) {
        fl_response(false, "fpb_set_patch failed: %d", ret);
        return 0;
    }

    /* Record slot state, transfer last_alloc ownership to slot */
    ctx->slots[args->comp].active = true;
    ctx->slots[args->comp].orig_addr = args->orig;
    ctx->slots[args->comp].target_addr = args->target;
    ctx->slots[args->comp].code_size = ctx->last_alloc_size;
    ctx->slots[args->comp].alloc_addr = ctx->last_alloc;
    ctx->last_alloc = 0; /* Ownership transferred */
    ctx->last_alloc_size = 0;

    fl_response(true, "Patch %lu: 0x%08lX -> 0x%08lX", (unsigned long)args->comp, (unsigned long)args->orig,
                (unsigned long)args->target);
    return 0;
}

static int cmd_tpatch(fl_context_t* ctx, const cmd_args_t* args) {
    if (args->orig == 0 || args->target == 0) {
        fl_response(false, "Missing --orig/--target");
        return -1;
    }

#ifndef FPB_NO_TRAMPOLINE
    if (!verify_patch_crc(args->crc, args->comp, args->orig, args->target))
        return 0;

    if ((uint32_t)args->comp >= FPB_TRAMPOLINE_COUNT || (uint32_t)args->comp >= FL_MAX_SLOTS) {
        fl_response(false, "Invalid comp %lu (max %d)", (unsigned long)args->comp, FPB_TRAMPOLINE_COUNT - 1);
        return 0;
    }

    /* Set trampoline target in RAM */
    fpb_trampoline_set_target(args->comp, args->target);

    /* Get trampoline address in Flash */
    uint32_t tramp_addr = fpb_trampoline_get_address(args->comp);

    /* Use FPB to redirect original function to trampoline */
    fpb_result_t ret = fpb_set_patch(args->comp, args->orig, tramp_addr);
    if (ret != FPB_OK) {
        fpb_trampoline_clear_target(args->comp);
        fl_response(false, "fpb_set_patch failed: %d", ret);
        return 0;
    }

    /* Record slot state, transfer last_alloc ownership to slot */
    ctx->slots[args->comp].active = true;
    ctx->slots[args->comp].orig_addr = args->orig;
    ctx->slots[args->comp].target_addr = args->target;
    ctx->slots[args->comp].code_size = ctx->last_alloc_size;
    ctx->slots[args->comp].alloc_addr = ctx->last_alloc;
    ctx->last_alloc = 0; /* Ownership transferred */
    ctx->last_alloc_size = 0;

    fl_response(true, "Trampoline %lu: 0x%08lX -> tramp(0x%08lX) -> 0x%08lX", (unsigned long)args->comp,
                (unsigned long)args->orig, (unsigned long)tramp_addr, (unsigned long)args->target);
#else
    (void)ctx;
    fl_response(false, "Trampoline disabled (FPB_NO_TRAMPOLINE)");
#endif
    return 0;
}

static int cmd_dpatch(fl_context_t* ctx, const cmd_args_t* args) {
    if (args->orig == 0 || args->target == 0) {
        fl_response(false, "Missing --orig/--target");
        return -1;
    }

#ifndef FPB_NO_DEBUGMON
    if (!verify_patch_crc(args->crc, args->comp, args->orig, args->target))
        return 0;

    if ((uint32_t)args->comp >= FPB_DEBUGMON_MAX_REDIRECTS || (uint32_t)args->comp >= FL_MAX_SLOTS) {
        fl_response(false, "Invalid comp %lu (max %d)", (unsigned long)args->comp, FPB_DEBUGMON_MAX_REDIRECTS - 1);
        return 0;
    }

    /* Initialize DebugMonitor if not already done */
    if (!fpb_debugmon_is_active()) {
        if (fpb_debugmon_init() != 0) {
            fl_response(false, "DebugMonitor init failed");
            return 0;
        }
    }

    /* Set redirect via DebugMonitor */
    int ret = fpb_debugmon_set_redirect(args->comp, args->orig, args->target);
    if (ret != 0) {
        fl_response(false, "fpb_debugmon_set_redirect failed: %d", ret);
        return 0;
    }

    /* Record slot state, transfer last_alloc ownership to slot */
    ctx->slots[args->comp].active = true;
    ctx->slots[args->comp].orig_addr = args->orig;
    ctx->slots[args->comp].target_addr = args->target;
    ctx->slots[args->comp].code_size = ctx->last_alloc_size;
    ctx->slots[args->comp].alloc_addr = ctx->last_alloc;
    ctx->last_alloc = 0; /* Ownership transferred */
    ctx->last_alloc_size = 0;

    fl_response(true, "DebugMon %lu: 0x%08lX -> 0x%08lX", (unsigned long)args->comp, (unsigned long)args->orig,
                (unsigned long)args->target);
#else
    (void)ctx;
    fl_response(false, "DebugMonitor disabled (FPB_NO_DEBUGMON)");
#endif
    return 0;
}

static int cmd_unpatch(fl_context_t* ctx, const cmd_args_t* args) {
    uint32_t comp = (uint32_t)args->comp;
    bool all = args->all;
    uint32_t num_comps = fpb_get_state()->num_code_comp;
    uint32_t start = all ? 0 : comp;
    uint32_t end = all ? num_comps : comp + 1;

    if (!all && (comp >= num_comps || comp >= FL_MAX_SLOTS)) {
        fl_response(false, "Invalid comp %lu", (unsigned long)comp);
        return 0;
    }

    uint32_t cleared = 0;
    for (uint32_t i = start; i < end && i < FL_MAX_SLOTS; i++) {
        if (ctx->slots[i].active || all) {
#ifndef FPB_NO_TRAMPOLINE
            fpb_trampoline_clear_target(i);
#endif
#ifndef FPB_NO_DEBUGMON
            fpb_debugmon_clear_redirect(i);
#endif
            fpb_clear_patch(i);

            /* Free slot's allocated memory if any */
            if (ctx->slots[i].alloc_addr != 0 && ctx->free_cb) {
                ctx->free_cb((void*)ctx->slots[i].alloc_addr);
            }

            /* Clear slot state */
            ctx->slots[i].active = false;
            ctx->slots[i].orig_addr = 0;
            ctx->slots[i].target_addr = 0;
            ctx->slots[i].code_size = 0;
            ctx->slots[i].alloc_addr = 0;
            cleared++;
        }
    }

    if (all) {
        fl_response(true, "Cleared all %u slots, memory freed", (unsigned)cleared);
    } else {
        fl_response(true, "Cleared slot %lu", (unsigned long)comp);
    }
    return 0;
}

static int cmd_enable(fl_context_t* ctx, const cmd_args_t* args) {
    if (args->enable < 0) {
        fl_response(false, "Missing --enable (0 or 1)");
        return -1;
    }

    (void)ctx;
    bool en = args->enable != 0;
    bool all = args->all;
    uint32_t comp = (uint32_t)args->comp;
    uint32_t num_comps = fpb_get_state()->num_code_comp;
    uint32_t start = all ? 0 : comp;
    uint32_t end = all ? num_comps : comp + 1;

    if (!all && (comp >= num_comps || comp >= FL_MAX_SLOTS)) {
        fl_response(false, "Invalid comp %lu", (unsigned long)comp);
        return 0;
    }

    uint32_t changed = 0;
    for (uint32_t i = start; i < end && i < FL_MAX_SLOTS; i++) {
        fpb_result_t ret = fpb_enable_patch(i, en);
        if (ret == FPB_OK) {
            changed++;
        }
    }

    if (all) {
        fl_response(true, "%s %u patches", en ? "Enabled" : "Disabled", (unsigned)changed);
    } else {
        fl_response(true, "%s patch %lu", en ? "Enabled" : "Disabled", (unsigned long)comp);
    }
    return 0;
}

__attribute__((noinline)) void fl_hello(void) {
    fl_response(true, "HELLO from original fl_hello(%p) function!", (void*)fl_hello);
}

static int cmd_hello(fl_context_t* ctx, const cmd_args_t* args) {
    (void)ctx;
    (void)args;
    fl_hello();
    return 0;
}

/* ===========================
   FILE TRANSFER COMMANDS
   =========================== */

#if FL_USE_FILE

static int cmd_fopen(fl_context_t* ctx, const cmd_args_t* args) {
    const char* mode = args->mode ? args->mode : "r";
    if (!ctx->file_ctx.fs) {
        fl_response(false, "File context not initialized");
        return 0;
    }

    if (!args->path || !mode) {
        fl_response(false, "Missing path or mode");
        return 0;
    }

    if (fl_file_open(&ctx->file_ctx, args->path, mode) != 0) {
        fl_response(false, "Failed to open: %s", args->path);
        return 0;
    }

    fl_response(true, "FOPEN %s mode=%s", args->path, mode);
    return 0;
}

static int cmd_fwrite(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fp) {
        fl_response(false, "No file open");
        return 0;
    }

    if (!args->data) {
        fl_response(false, "Missing data");
        return 0;
    }

    /* Decode base64 data */
    int n = base64_to_bytes(args->data, ctx->buf, FL_BUF_SIZE);
    if (n < 0) {
        fl_response(false, "Invalid base64 data");
        return 0;
    }

    /* Verify CRC if provided */
    if (args->crc >= 0) {
        uint16_t calc = calc_crc16(ctx->buf, n);
        if (calc != (uint16_t)args->crc) {
            fl_response(false, "CRC mismatch: 0x%04X != 0x%04X", (unsigned)args->crc, (unsigned)calc);
            return 0;
        }
    }

    /* Write to file */
    ssize_t written = fl_file_write(&ctx->file_ctx, ctx->buf, n);
    if (written < 0) {
        fl_response(false, "Write failed");
        return 0;
    }

    fl_response(true, "FWRITE %d bytes", (int)written);
    return 0;
}

static int cmd_fread(fl_context_t* ctx, const cmd_args_t* args) {
    int len = args->len;
    if (!ctx->file_ctx.fp) {
        fl_response(false, "No file open");
        return 0;
    }

    if (len <= 0 || len > (int)FL_BUF_SIZE) {
        len = FL_BUF_SIZE;
    }

    ssize_t nread = fl_file_read(&ctx->file_ctx, ctx->buf, len);
    if (nread < 0) {
        fl_response(false, "Read failed");
        return 0;
    }

    if (nread == 0) {
        fl_response(true, "FREAD 0 bytes EOF");
        return 0;
    }

    /* Encode to base64 */
    if (bytes_to_base64(ctx->buf, nread, ctx->b64_buf, FL_B64_BUF_SIZE) < 0) {
        fl_response(false, "Base64 encode failed");
        return 0;
    }

    /* Calculate CRC */
    uint16_t crc = calc_crc16(ctx->buf, nread);

    /* Output in parts to avoid buffer overflow */
    fl_print("[FLOK] FREAD %d bytes crc=0x%04X data=", (int)nread, (unsigned)crc);
    fl_print_raw(ctx->b64_buf);
    fl_print_raw("\n[FLEND]\n");
    return 0;
}

static int cmd_fclose(fl_context_t* ctx, const cmd_args_t* args) {
    (void)args;
    if (!ctx->file_ctx.fp) {
        fl_response(false, "No file open");
        return 0;
    }

    if (fl_file_close(&ctx->file_ctx) != 0) {
        fl_response(false, "Close failed");
        return 0;
    }

    fl_response(true, "FCLOSE");
    return 0;
}

static int cmd_fcrc(fl_context_t* ctx, const cmd_args_t* args) {
    off_t size = (off_t)args->len;
    if (!ctx->file_ctx.fp) {
        fl_response(false, "No file open");
        return 0;
    }

    /* Save current position */
    off_t saved_pos = fl_file_seek(&ctx->file_ctx, 0, FL_SEEK_CUR);
    if (saved_pos < 0) {
        fl_response(false, "Failed to get current position");
        return 0;
    }

    /* Seek to beginning */
    if (fl_file_seek(&ctx->file_ctx, 0, FL_SEEK_SET) < 0) {
        fl_response(false, "Failed to seek to beginning");
        return 0;
    }

    /* Calculate CRC of entire file (or specified size) */
    uint16_t crc = 0xFFFF;
    off_t total_read = 0;
    off_t remaining = size > 0 ? size : LLONG_MAX;

    while (remaining > 0) {
        size_t to_read = FL_BUF_SIZE;
        if ((off_t)to_read > remaining) {
            to_read = (size_t)remaining;
        }

        ssize_t nread = fl_file_read(&ctx->file_ctx, ctx->buf, to_read);
        if (nread < 0) {
            fl_response(false, "Read failed during CRC calculation");
            return 0;
        }
        if (nread == 0) {
            break; /* EOF */
        }

        /* Update CRC incrementally (same algorithm as calc_crc16) */
        crc = calc_crc16_base(crc, ctx->buf, nread);
        total_read += nread;
        remaining -= nread;
    }

    /* Restore original position */
    fl_file_seek(&ctx->file_ctx, saved_pos, FL_SEEK_SET);

    fl_response(true, "FCRC size=%ld crc=0x%04X", (long)total_read, (unsigned)crc);
    return 0;
}

static int cmd_fseek(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fp) {
        fl_response(false, "No file open");
        return 0;
    }

    off_t new_pos = fl_file_seek(&ctx->file_ctx, (off_t)args->addr, FL_SEEK_SET);
    if (new_pos < 0) {
        fl_response(false, "Seek failed");
        return 0;
    }

    fl_response(true, "FSEEK %ld", (long)new_pos);
    return 0;
}

static int cmd_fstat(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fs) {
        fl_response(false, "File context not initialized");
        return 0;
    }

    if (!args->path) {
        fl_response(false, "Missing path");
        return 0;
    }

    fl_file_stat_t st;
    if (fl_file_stat(&ctx->file_ctx, args->path, &st) != 0) {
        fl_response(false, "Stat failed: %s", args->path);
        return 0;
    }

    const char* type_str = (st.type == FL_FILE_TYPE_DIR) ? "dir" : "file";
    fl_response(true, "FSTAT %s size=%u mtime=%u type=%s", args->path, (unsigned)st.size, (unsigned)st.mtime, type_str);
    return 0;
}

/* Callback context for flist count pass */
typedef struct {
    int dir_count;
    int file_count;
} flist_count_ctx_t;

/* Callback for printing entries */
static int flist_print_cb(const fl_dirent_t* entry, void* user_data) {
    flist_count_ctx_t* c = user_data;
    const char* type_char = (entry->type == FL_FILE_TYPE_DIR) ? "D" : "F";
    if (entry->type == FL_FILE_TYPE_DIR) {
        fl_println("  %s %s", type_char, entry->name);
        c->dir_count++;
    } else {
        fl_println("  %s %s %u", type_char, entry->name, (unsigned)entry->size);
        c->file_count++;
    }
    return 0;
}

static int cmd_flist(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fs) {
        fl_response(false, "File context not initialized");
        return 0;
    }

    if (!args->path) {
        fl_response(false, "Missing path");
        return 0;
    }

    /* First pass: count dirs and files */
    flist_count_ctx_t count_ctx = {0, 0};
    int total = fl_file_list_cb(&ctx->file_ctx, args->path, flist_print_cb, &count_ctx);
    if (total < 0) {
        fl_response(false, "List failed: %s", args->path);
        return 0;
    }

    fl_response(true, "FLIST dir=%d file=%d", count_ctx.dir_count, count_ctx.file_count);
    return 0;
}

static int cmd_fremove(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fs) {
        fl_response(false, "File context not initialized");
        return 0;
    }

    if (!args->path) {
        fl_response(false, "Missing path");
        return 0;
    }

    if (fl_file_remove(&ctx->file_ctx, args->path) != 0) {
        fl_response(false, "Remove failed: %s", args->path);
        return 0;
    }

    fl_response(true, "FREMOVE %s", args->path);
    return 0;
}

static int cmd_fmkdir(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fs) {
        fl_response(false, "File context not initialized");
        return 0;
    }

    if (!args->path) {
        fl_response(false, "Missing path");
        return 0;
    }

    if (fl_file_mkdir(&ctx->file_ctx, args->path) != 0) {
        fl_response(false, "Mkdir failed: %s", args->path);
        return 0;
    }

    fl_response(true, "FMKDIR %s", args->path);
    return 0;
}

static int cmd_frename(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fs) {
        fl_response(false, "File context not initialized");
        return 0;
    }

    if (!args->path) {
        fl_response(false, "Missing path");
        return 0;
    }

    if (!args->newpath) {
        fl_response(false, "Missing newpath");
        return 0;
    }

    if (fl_file_rename(&ctx->file_ctx, args->path, args->newpath) != 0) {
        fl_response(false, "Rename failed: %s -> %s", args->path, args->newpath);
        return 0;
    }

    fl_response(true, "FRENAME %s -> %s", args->path, args->newpath);
    return 0;
}

#endif /* FL_USE_FILE */

/* ===========================
   COMMAND DISPATCH TABLE
   =========================== */

/**
 * @brief Command dispatch table entry
 */
typedef struct {
    const char* name;
    cmd_handler_t handler;
} cmd_entry_t;

/* clang-format off */
static const cmd_entry_t s_cmd_table[] = {
    /* Core commands */
    { "ping",     cmd_ping     },
    { "echo",     cmd_echo     },
    { "echoback", cmd_echoback },
    { "info",     cmd_info     },
    { "alloc",    cmd_alloc    },
    { "upload",   cmd_upload   },
    { "read",     cmd_read     },
    { "write",    cmd_write    },
    { "patch",    cmd_patch    },
    { "tpatch",   cmd_tpatch   },
    { "dpatch",   cmd_dpatch   },
    { "unpatch",  cmd_unpatch  },
    { "enable",   cmd_enable   },
    { "hello",    cmd_hello    },
#if FL_USE_FILE
    /* File transfer commands */
    { "fopen",    cmd_fopen    },
    { "fwrite",   cmd_fwrite   },
    { "fread",    cmd_fread    },
    { "fclose",   cmd_fclose   },
    { "fcrc",     cmd_fcrc     },
    { "fseek",    cmd_fseek    },
    { "fstat",    cmd_fstat    },
    { "flist",    cmd_flist    },
    { "fremove",  cmd_fremove  },
    { "fmkdir",   cmd_fmkdir   },
    { "frename",  cmd_frename  },
#endif
};
/* clang-format on */

#define CMD_TABLE_SIZE (sizeof(s_cmd_table) / sizeof(s_cmd_table[0]))

int fl_exec_cmd(fl_context_t* ctx, int argc, const char** argv) {
    if (argc == 0)
        return -1;

    cmd_args_t args = {0};
    args.crc = -1;
    args.len = 64;
    args.enable = -1;

    struct argparse_option opts[] = {
        OPT_HELP(),
        OPT_STRING('c', "cmd", &args.cmd, "Command", NULL, 0, 0),
        OPT_INTEGER('s', "size", &args.size, "Alloc size", NULL, 0, 0),
        OPT_POINTER('a', "addr", &args.addr, "Address/offset (hex)", NULL, 0, 0),
        OPT_STRING('d', "data", &args.data, "Hex data", NULL, 0, 0),
        OPT_INTEGER('r', "crc", &args.crc, "CRC-16 (hex)", NULL, 0, 0),
        OPT_INTEGER('l', "len", &args.len, "Read length", NULL, 0, 0),
        OPT_INTEGER(0, "comp", &args.comp, "Comparator ID", NULL, 0, 0),
        OPT_POINTER(0, "orig", &args.orig, "Original addr", NULL, 0, 0),
        OPT_POINTER(0, "target", &args.target, "Target addr", NULL, 0, 0),
        OPT_BOOLEAN(0, "all", &args.all, "Clear all", NULL, 0, 0),
        OPT_INTEGER(0, "enable", &args.enable, "Enable(1) or disable(0) patch", NULL, 0, 0),
        OPT_BOOLEAN(0, "force", &args.force, "Skip address range check", NULL, 0, 0),
        OPT_STRING(0, "path", &args.path, "File path", NULL, 0, 0),
        OPT_STRING(0, "newpath", &args.newpath, "New file path", NULL, 0, 0),
        OPT_STRING('m', "mode", &args.mode, "File mode (r/w/a)", NULL, 0, 0),
        OPT_END(),
    };

    struct argparse ap;
    fl_argparse_init(&ap, opts, NULL, 0);
    if (fl_argparse_parse(&ap, argc, argv) > 0) {
        fl_response(false, "Invalid arguments");
        return -1;
    }

    if (!args.cmd) {
        fl_println("Available commands:");
        for (size_t i = 0; i < CMD_TABLE_SIZE; i++) {
            fl_println("  %s", s_cmd_table[i].name);
        }
        fl_response(false, "Missing --cmd");
        return -1;
    }

    /* Lookup command in dispatch table */
    for (size_t i = 0; i < CMD_TABLE_SIZE; i++) {
        if (strcmp(args.cmd, s_cmd_table[i].name) == 0) {
            return s_cmd_table[i].handler(ctx, &args);
        }
    }

    fl_response(false, "Unknown: %s", args.cmd);
    return -1;
}
