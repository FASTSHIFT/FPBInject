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

#include "func_loader.h"
#include "argparse/argparse.h"
#include "fpb_inject.h"
#include "fpb_trampoline.h"
#include "fpb_debugmon.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#ifndef FL_MAX_ARGC
#define FL_MAX_ARGC 32
#endif

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

static uint16_t calc_crc16(const uint8_t* data, size_t len) {
    uint16_t crc = 0xFFFF;
    while (len--) {
        crc = (crc << 8) ^ s_crc16_table[(crc >> 8) ^ *data++];
    }
    return crc;
}

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

static int base64_to_bytes(const char* b64, uint8_t* out, size_t max) {
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

static int hex_to_bytes(const char* hex, uint8_t* out, size_t max) {
    if (!hex || !out)
        return -1;
    if (hex[0] == '0' && (hex[1] == 'x' || hex[1] == 'X'))
        hex += 2;

    size_t hex_len = strlen(hex);
    if (hex_len % 2 != 0)
        return -1;

    size_t n = hex_len / 2;
    if (n > max)
        return -1;

    for (size_t i = 0; i < n; i++) {
        uint8_t hi, lo;
        char c = hex[i * 2];
        if (c >= '0' && c <= '9')
            hi = c - '0';
        else if (c >= 'a' && c <= 'f')
            hi = c - 'a' + 10;
        else if (c >= 'A' && c <= 'F')
            hi = c - 'A' + 10;
        else
            return -1;

        c = hex[i * 2 + 1];
        if (c >= '0' && c <= '9')
            lo = c - '0';
        else if (c >= 'a' && c <= 'f')
            lo = c - 'a' + 10;
        else if (c >= 'A' && c <= 'F')
            lo = c - 'A' + 10;
        else
            return -1;

        out[i] = (hi << 4) | lo;
    }
    return (int)n;
}

static int bytes_to_hex(const uint8_t* data, size_t len, char* out, size_t max) {
    static const char hc[] = "0123456789ABCDEF";
    if (!data || !out || max < len * 2 + 1)
        return -1;

    for (size_t i = 0; i < len; i++) {
        out[i * 2] = hc[(data[i] >> 4) & 0x0F];
        out[i * 2 + 1] = hc[data[i] & 0x0F];
    }
    out[len * 2] = '\0';
    return (int)(len * 2);
}

static void output(fl_context_t* ctx, const char* str) {
    if (ctx->output_cb) {
        ctx->output_cb(ctx->output_user, str);
    }
}

static void fl_response(fl_context_t* ctx, bool ok, const char* fmt, ...) {
    char buf[256];
    va_list args;

    output(ctx, ok ? "[OK] " : "[ERR] ");
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    output(ctx, buf);
    output(ctx, "\n");
}

static void fl_print(fl_context_t* ctx, const char* fmt, ...) {
    char buf[256];
    va_list args;

    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    output(ctx, buf);
    output(ctx, "\n");
}

static uint8_t* get_buf(fl_context_t* ctx) {
    if (ctx->dyn_base != 0)
        return (uint8_t*)ctx->dyn_base;
    return ctx->static_buf;
}

static size_t get_buf_size(fl_context_t* ctx) {
    if (ctx->dyn_base != 0)
        return ctx->dyn_size;
    return ctx->static_size;
}

static size_t* get_used_ptr(fl_context_t* ctx) {
    if (ctx->dyn_base != 0)
        return &ctx->dyn_used;
    return &ctx->static_used;
}

static uintptr_t fl_get_base(fl_context_t* ctx) {
    return (uintptr_t)get_buf(ctx);
}

static size_t fl_get_size(fl_context_t* ctx) {
    return get_buf_size(ctx);
}

void fl_init(fl_context_t* ctx) {
    ctx->static_used = 0;
    ctx->dyn_base = 0;
    ctx->dyn_size = 0;
    ctx->dyn_used = 0;
    fpb_init();
}

static int write_code(fl_context_t* ctx, uint32_t off, const uint8_t* data, size_t len) {
    if (off + len > get_buf_size(ctx))
        return -1;
    memcpy(get_buf(ctx) + off, data, len);
    size_t* used = get_used_ptr(ctx);
    if (off + len > *used)
        *used = off + len;
    return 0;
}

static int exec_code(fl_context_t* ctx, uint32_t entry_off, int argc, const char** argv) {
    size_t used = *get_used_ptr(ctx);
    if (entry_off >= used)
        return -1;

    uint32_t addr = (uint32_t)(get_buf(ctx) + entry_off) | 1;
    typedef int (*fn_t)(int, const char**);
    fn_t fn = (fn_t)addr;

    __asm volatile("dsb");
    __asm volatile("isb");

    return fn(argc, argv);
}

static void cmd_ping(fl_context_t* ctx) {
    fl_response(ctx, true, "PONG");
}

static void cmd_info(fl_context_t* ctx) {
    const char* mode = ctx->malloc_cb ? "dynamic" : "static";

    fl_print(ctx, "FPBInject v1.0");
    fl_print(ctx, "Alloc: %s", mode);
    fl_print(ctx, "Base: 0x%08lX", (unsigned long)fl_get_base(ctx));
    fl_print(ctx, "Size: %u", (unsigned)fl_get_size(ctx));
    fl_print(ctx, "Used: %u", (unsigned)*get_used_ptr(ctx));
    fl_print(ctx, "FPB: %u comps", (unsigned)fpb_get_state()->num_code_comp);
    fl_response(ctx, true, "Info complete");
}

static void cmd_alloc(fl_context_t* ctx, size_t size) {
    if (!ctx->malloc_cb) {
        fl_response(ctx, false, "No malloc_cb");
        return;
    }

    if (ctx->dyn_base != 0 && ctx->free_cb) {
        ctx->free_cb((void*)ctx->dyn_base);
        ctx->dyn_base = 0;
    }

    void* p = ctx->malloc_cb(size);
    if (!p) {
        ctx->dyn_base = 0;
        ctx->dyn_size = 0;
        fl_response(ctx, false, "Alloc failed");
        return;
    }

    ctx->dyn_base = (uintptr_t)p;
    ctx->dyn_size = size;
    ctx->dyn_used = 0;
    fl_response(ctx, true, "Allocated %u at 0x%08lX", (unsigned)size, (unsigned long)p);
}

static void cmd_free(fl_context_t* ctx) {
    if (ctx->dyn_base == 0) {
        fl_response(ctx, false, "Nothing allocated");
        return;
    }
    if (ctx->free_cb) {
        ctx->free_cb((void*)ctx->dyn_base);
    }
    ctx->dyn_base = 0;
    ctx->dyn_size = 0;
    ctx->dyn_used = 0;
    fl_response(ctx, true, "Freed");
}

static void cmd_upload(fl_context_t* ctx, uint32_t off, const char* data_str, uintptr_t crc, bool verify) {
    static uint8_t buf[2048];
    int n;

    /* Try base64 first (contains uppercase and lowercase letters), then hex */
    /* Base64 strings typically have length multiple of 4 and may contain A-Z, a-z, 0-9, +, /, = */
    size_t len = strlen(data_str);
    bool is_base64 = (len > 0) && (len % 4 == 0);

    /* Check if it looks like base64 (contains lowercase letters or + or /) */
    if (is_base64) {
        for (size_t i = 0; i < len && is_base64; i++) {
            char c = data_str[i];
            if ((c >= 'a' && c <= 'z') || c == '+' || c == '/') {
                break; /* Definitely base64 */
            }
            if (c == '=' && i >= len - 2) {
                break; /* Padding at end - base64 */
            }
        }
    }

    if (is_base64) {
        n = base64_to_bytes(data_str, buf, sizeof(buf));
    }

    /* Fallback to hex if base64 failed or data looks like hex */
    if (!is_base64 || n < 0) {
        n = hex_to_bytes(data_str, buf, sizeof(buf));
        if (n < 0) {
            fl_response(ctx, false, "Invalid data encoding");
            return;
        }
    }

    if (verify) {
        uint16_t calc = calc_crc16(buf, n);
        if (calc != (uint16_t)crc) {
            fl_response(ctx, false, "CRC mismatch: 0x%04X != 0x%04X", (unsigned)crc, (unsigned)calc);
            return;
        }
    }

    if (write_code(ctx, off, buf, n) != 0) {
        fl_response(ctx, false, "Overflow at 0x%lX", (unsigned long)off);
        return;
    }

    /* Flush data cache after upload to ensure code is visible to CPU */
    if (ctx->flush_dcache_cb) {
        uint8_t* code_buf = get_buf(ctx);
        size_t buf_size = get_buf_size(ctx);
        if (code_buf && buf_size > 0) {
            ctx->flush_dcache_cb((uintptr_t)code_buf, (uintptr_t)code_buf + buf_size);
        }
    }

    fl_response(ctx, true, "Uploaded %d bytes to 0x%lX", n, (unsigned long)off);
}

static void cmd_clear(fl_context_t* ctx) {
    memset(get_buf(ctx), 0, get_buf_size(ctx));
    *get_used_ptr(ctx) = 0;
    fl_response(ctx, true, "Cleared");
}

static int parse_args(const char* str, char* buf, size_t sz, char** av, int max) {
    int ac = 0;
    if (!str || !*str)
        return 0;

    strncpy(buf, str, sz - 1);
    buf[sz - 1] = '\0';

    char* p = buf;
    bool in_q = false, in_a = false;

    while (*p && ac < max) {
        if (*p == '"') {
            in_q = !in_q;
            memmove(p, p + 1, strlen(p));
            continue;
        }
        if (!in_q && (*p == ' ' || *p == '\t')) {
            if (in_a) {
                *p = '\0';
                in_a = false;
            }
        } else if (!in_a) {
            av[ac++] = p;
            in_a = true;
        }
        p++;
    }
    return ac;
}

static void cmd_exec(fl_context_t* ctx, uint32_t entry, const char* args) {
    static char buf[256];
    static char* av[FL_MAX_ARGC];
    int ac = parse_args(args, buf, sizeof(buf), av, FL_MAX_ARGC);

    fl_print(ctx, "Exec at 0x%lX, %d args", (unsigned long)entry, ac);
    int ret = exec_code(ctx, entry, ac, (const char**)av);
    fl_response(ctx, true, "Returned %d (0x%08lX)", ret, (unsigned long)ret);
}

static void cmd_call(fl_context_t* ctx, uintptr_t addr, const char* args) {
    static char buf[256];
    static char* av[FL_MAX_ARGC];
    int ac = parse_args(args, buf, sizeof(buf), av, FL_MAX_ARGC);

    fl_print(ctx, "Call 0x%08lX, %d args", (unsigned long)addr, ac);

    typedef int (*fn_t)(int, const char**);
    fn_t fn = (fn_t)(addr | 1);
    int ret = fn(ac, (const char**)av);
    fl_response(ctx, true, "Returned %d (0x%08lX)", ret, (unsigned long)ret);
}

static void cmd_read(fl_context_t* ctx, uintptr_t addr, size_t len) {
    static char hex[1024];
    if (len > sizeof(hex) / 2)
        len = sizeof(hex) / 2;

    bytes_to_hex((const uint8_t*)addr, len, hex, sizeof(hex));
    fl_print(ctx, "Data: %s", hex);
    fl_response(ctx, true, "Read %u from 0x%08lX", (unsigned)len, (unsigned long)addr);
}

static void cmd_write(fl_context_t* ctx, uintptr_t addr, const char* hex, uintptr_t crc, bool verify) {
    static uint8_t buf[512];
    int n = hex_to_bytes(hex, buf, sizeof(buf));
    if (n < 0) {
        fl_response(ctx, false, "Invalid hex");
        return;
    }

    if (verify) {
        uint16_t calc = calc_crc16(buf, n);
        if (calc != (uint16_t)crc) {
            fl_response(ctx, false, "CRC mismatch");
            return;
        }
    }

    memcpy((void*)addr, buf, n);
    fl_response(ctx, true, "Wrote %d to 0x%08lX", n, (unsigned long)addr);
}

static void cmd_patch(fl_context_t* ctx, uint32_t comp, uintptr_t orig, uintptr_t target) {
    if (comp >= fpb_get_state()->num_code_comp) {
        fl_response(ctx, false, "Invalid comp %lu", (unsigned long)comp);
        return;
    }

    int ret = fpb_set_patch(comp, orig, target);
    if (ret != 0) {
        fl_response(ctx, false, "fpb_set_patch failed: %d", ret);
        return;
    }

    fl_response(ctx, true, "Patch %lu: 0x%08lX -> 0x%08lX", (unsigned long)comp, (unsigned long)orig,
                (unsigned long)target);
}

static void cmd_tpatch(fl_context_t* ctx, uint32_t comp, uintptr_t orig, uintptr_t target) {
#ifndef FPB_NO_TRAMPOLINE
    if (comp >= FPB_TRAMPOLINE_COUNT) {
        fl_response(ctx, false, "Invalid comp %lu (max %d)", (unsigned long)comp, FPB_TRAMPOLINE_COUNT - 1);
        return;
    }

    /* Set trampoline target in RAM */
    fpb_trampoline_set_target(comp, target);

    /* Get trampoline address in Flash */
    uint32_t tramp_addr = fpb_trampoline_get_address(comp);

    /* Use FPB to redirect original function to trampoline */
    int ret = fpb_set_patch(comp, orig, tramp_addr);
    if (ret != 0) {
        fpb_trampoline_clear_target(comp);
        fl_response(ctx, false, "fpb_set_patch failed: %d", ret);
        return;
    }

    fl_response(ctx, true, "Trampoline %lu: 0x%08lX -> tramp(0x%08lX) -> 0x%08lX", (unsigned long)comp,
                (unsigned long)orig, (unsigned long)tramp_addr, (unsigned long)target);
#else
    (void)comp;
    (void)orig;
    (void)target;
    fl_response(ctx, false, "Trampoline disabled (FPB_NO_TRAMPOLINE)");
#endif
}

static void cmd_dpatch(fl_context_t* ctx, uint32_t comp, uintptr_t orig, uintptr_t target) {
#ifndef FPB_NO_DEBUGMON
    if (comp >= FPB_DEBUGMON_MAX_REDIRECTS) {
        fl_response(ctx, false, "Invalid comp %lu (max %d)", (unsigned long)comp, FPB_DEBUGMON_MAX_REDIRECTS - 1);
        return;
    }

    /* Initialize DebugMonitor if not already done */
    if (!fpb_debugmon_is_active()) {
        if (fpb_debugmon_init() != 0) {
            fl_response(ctx, false, "DebugMonitor init failed");
            return;
        }
    }

    /* Set redirect via DebugMonitor */
    int ret = fpb_debugmon_set_redirect(comp, orig, target);
    if (ret != 0) {
        fl_response(ctx, false, "fpb_debugmon_set_redirect failed: %d", ret);
        return;
    }

    fl_response(ctx, true, "DebugMon %lu: 0x%08lX -> 0x%08lX", (unsigned long)comp, (unsigned long)orig,
                (unsigned long)target);
#else
    (void)comp;
    (void)orig;
    (void)target;
    fl_response(ctx, false, "DebugMonitor disabled (FPB_NO_DEBUGMON)");
#endif
}

static void cmd_unpatch(fl_context_t* ctx, uint32_t comp) {
    if (comp >= fpb_get_state()->num_code_comp) {
        fl_response(ctx, false, "Invalid comp %lu", (unsigned long)comp);
        return;
    }

#ifndef FPB_NO_TRAMPOLINE
    fpb_trampoline_clear_target(comp);
#endif
#ifndef FPB_NO_DEBUGMON
    fpb_debugmon_clear_redirect(comp);
#endif
    fpb_clear_patch(comp);
    fl_response(ctx, true, "Cleared %lu", (unsigned long)comp);
}

int fl_exec_cmd(fl_context_t* ctx, int argc, const char** argv) {
    if (argc == 0)
        return -1;

    const char* cmd = NULL;
    const char* data = NULL;
    const char* args = NULL;
    uintptr_t addr = 0;
    uintptr_t crc = 0xFFFFFFFF; /* Invalid CRC marker */
    uintptr_t len = 64;
    uintptr_t size = 0;
    uintptr_t comp = 0;
    uintptr_t orig = 0;
    uintptr_t target = 0;
    uintptr_t entry = 0;

    struct argparse_option opts[] = {
        OPT_HELP(),
        OPT_STRING('c', "cmd", &cmd, "Command", NULL, 0, 0),
        OPT_POINTER(0, "size", &size, "Alloc size", NULL, 0, 0),
        OPT_POINTER('a', "addr", &addr, "Address/offset (hex)", NULL, 0, 0),
        OPT_STRING('d', "data", &data, "Hex data", NULL, 0, 0),
        OPT_POINTER(0, "crc", &crc, "CRC-16 (hex)", NULL, 0, 0),
        OPT_POINTER('e', "entry", &entry, "Entry offset", NULL, 0, 0),
        OPT_STRING(0, "args", &args, "Arguments", NULL, 0, 0),
        OPT_POINTER('l', "len", &len, "Read length", NULL, 0, 0),
        OPT_POINTER(0, "comp", &comp, "Comparator ID", NULL, 0, 0),
        OPT_POINTER(0, "orig", &orig, "Original addr", NULL, 0, 0),
        OPT_POINTER(0, "target", &target, "Target addr", NULL, 0, 0),
        OPT_END(),
    };

    struct argparse ap;
    static const char* const usage[] = {"fl --cmd <cmd> [opts]", NULL};

    fl_argparse_init(&ap, opts, usage, ARGPARSE_IGNORE_UNKNOWN_ARGS);
    int ret = fl_argparse_parse(&ap, argc, argv);
    if (ret < 0) {
        fl_response(ctx, false, "Invalid arguments");
        return -1;
    }

    if (!cmd) {
        fl_response(ctx, false, "Missing --cmd");
        return -1;
    }

    if (strcmp(cmd, "ping") == 0) {
        cmd_ping(ctx);
    } else if (strcmp(cmd, "info") == 0) {
        cmd_info(ctx);
    } else if (strcmp(cmd, "alloc") == 0) {
        if (size == 0) {
            fl_response(ctx, false, "Missing --size");
            return -1;
        }
        cmd_alloc(ctx, size);
    } else if (strcmp(cmd, "free") == 0) {
        cmd_free(ctx);
    } else if (strcmp(cmd, "upload") == 0) {
        if (!data) {
            fl_response(ctx, false, "Missing --data");
            return -1;
        }
        cmd_upload(ctx, addr, data, crc, crc != 0xFFFFFFFF);
    } else if (strcmp(cmd, "clear") == 0) {
        cmd_clear(ctx);
    } else if (strcmp(cmd, "exec") == 0) {
        cmd_exec(ctx, entry, args);
    } else if (strcmp(cmd, "call") == 0) {
        if (addr == 0) {
            fl_response(ctx, false, "Missing --addr");
            return -1;
        }
        cmd_call(ctx, addr, args);
    } else if (strcmp(cmd, "read") == 0) {
        if (addr == 0) {
            fl_response(ctx, false, "Missing --addr");
            return -1;
        }
        cmd_read(ctx, addr, len);
    } else if (strcmp(cmd, "write") == 0) {
        if (addr == 0 || !data) {
            fl_response(ctx, false, "Missing --addr/--data");
            return -1;
        }
        cmd_write(ctx, addr, data, crc, crc != 0xFFFFFFFF);
    } else if (strcmp(cmd, "patch") == 0) {
        if (orig == 0 || target == 0) {
            fl_response(ctx, false, "Missing --orig/--target");
            return -1;
        }
        cmd_patch(ctx, comp, orig, target);
    } else if (strcmp(cmd, "tpatch") == 0) {
        if (orig == 0 || target == 0) {
            fl_response(ctx, false, "Missing --orig/--target");
            return -1;
        }
        cmd_tpatch(ctx, comp, orig, target);
    } else if (strcmp(cmd, "dpatch") == 0) {
        if (orig == 0 || target == 0) {
            fl_response(ctx, false, "Missing --orig/--target");
            return -1;
        }
        cmd_dpatch(ctx, comp, orig, target);
    } else if (strcmp(cmd, "unpatch") == 0) {
        cmd_unpatch(ctx, comp);
    } else {
        fl_response(ctx, false, "Unknown: %s", cmd);
        return -1;
    }

    return 0;
}
