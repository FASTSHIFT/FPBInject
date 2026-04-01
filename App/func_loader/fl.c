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
#include "fl_cmd.h"
#include "fl_error.h"
#include "fl_log.h"

#ifndef FL_NO_FPB
#include "fpb_inject.h"
#endif

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
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

void fl_init_default(fl_context_t* ctx) {
    memset(ctx, 0, sizeof(fl_context_t));
}

void fl_init(fl_context_t* ctx) {
#ifndef FL_NO_FPB
    fpb_init();
#endif
    fl_log_init(ctx->output_cb, ctx->output_user);
    ctx->is_inited = true;
}

bool fl_is_inited(fl_context_t* ctx) {
    return ctx->is_inited;
}

void fl_flush_dcache(fl_context_t* ctx, const void* addr, size_t len) {
    if (ctx->flush_dcache_cb) {
        ctx->flush_dcache_cb((uintptr_t)addr, (uintptr_t)addr + len);
    }
}

/**
 * @brief  Check if [addr, addr+len) is a safe memory range
 * @note   Rejects NULL pointer and address overflow (wrapping past 0xFFFFFFFF)
 * @return true if the range is safe to access
 */
bool fl_check_addr_range(uintptr_t addr, size_t len) {
    if (addr == 0 || len == 0) {
        return false;
    }

    /* Check if addr + len - 1 overflows past 0xFFFFFFFF */
    if ((uint32_t)(addr + len - 1) < (uint32_t)addr) {
        return false;
    }

    return true;
}

/**
 * @brief Parsed command arguments (shared by all handlers)
 */

/**
 * @brief Command handler function pointer
 * @return 0 on success, -1 on argument validation error
 */

/**
 * @brief  Verify args->crc against a pre-computed CRC value
 * @param  crc   args->crc (-1 = skip verification)
 * @param  calc  Expected CRC computed by caller
 * @return true if CRC matches or not provided; false on mismatch (error response sent)
 */
bool fl_verify_crc(int crc, uint16_t calc) {
    if (crc < 0) {
        return true;
    }

    if (calc != (uint16_t)crc) {
        fl_response(false, "CRC mismatch: 0x%04X != 0x%04X", (unsigned)crc, (unsigned)calc);
        return false;
    }

    return true;
}

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
    { "ping",     fl_cmd_ping     },
    { "echo",     fl_cmd_echo     },
    { "echoback", fl_cmd_echoback },
    { "info",     fl_cmd_info     },
    { "alloc",    fl_cmd_alloc    },
    { "upload",   fl_cmd_upload   },
    { "read",     fl_cmd_read     },
    { "write",    fl_cmd_write    },
    { "patch",    fl_cmd_patch    },
    { "tpatch",   fl_cmd_tpatch   },
    { "dpatch",   fl_cmd_dpatch   },
    { "unpatch",  fl_cmd_unpatch  },
    { "enable",   fl_cmd_enable   },
    { "hello",    fl_cmd_hello    },
#if FL_USE_FILE
    /* File transfer commands */
    { "fopen",    fl_cmd_fopen    },
    { "fwrite",   fl_cmd_fwrite   },
    { "fread",    fl_cmd_fread    },
    { "fclose",   fl_cmd_fclose   },
    { "fcrc",     fl_cmd_fcrc     },
    { "fseek",    fl_cmd_fseek    },
    { "fstat",    fl_cmd_fstat    },
    { "flist",    fl_cmd_flist    },
    { "fremove",  fl_cmd_fremove  },
    { "fmkdir",   fl_cmd_fmkdir   },
    { "frename",  fl_cmd_frename  },
#endif
};
/* clang-format on */

#define CMD_TABLE_SIZE (sizeof(s_cmd_table) / sizeof(s_cmd_table[0]))

fl_error_t fl_exec_cmd(fl_context_t* ctx, int argc, const char** argv) {
    if (argc == 0) {
        return FL_ERR_ARGS;
    }

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
        return FL_ERR_PARSE;
    }

    if (!args.cmd) {
        fl_println("Available commands:");
        for (size_t i = 0; i < CMD_TABLE_SIZE; i++) {
            fl_println("  %s", s_cmd_table[i].name);
        }
        fl_response(false, "Missing --cmd");
        return FL_ERR_ARGS;
    }

    /* Lookup command in dispatch table */
    for (size_t i = 0; i < CMD_TABLE_SIZE; i++) {
        if (strcmp(args.cmd, s_cmd_table[i].name) == 0) {
            return s_cmd_table[i].handler(ctx, &args);
        }
    }

    fl_response(false, "Unknown: %s", args.cmd);
    return FL_ERR_UNKNOWN;
}
