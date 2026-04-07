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
 * @file   fl_cmd.h
 * @brief  Internal header shared by fl_cmd_*.c command modules
 */

#ifndef FL_CMD_H
#define FL_CMD_H

#ifdef __cplusplus
extern "C" {
#endif

#include "fl.h"
#include "fl_codec.h"
#include "fl_error.h"
#include "fl_log.h"

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
 * @return FL_OK or negative fl_error_t
 */
typedef fl_error_t (*cmd_handler_t)(fl_context_t* ctx, const cmd_args_t* args);

/**
 * @brief  Verify args->crc against a pre-computed CRC value
 * @param  crc   args->crc (-1 = skip verification)
 * @param  calc  Expected CRC computed by caller
 * @return true if CRC matches or not provided; false on mismatch (error response sent)
 */
bool fl_verify_crc(int crc, uint16_t calc);

/**
 * @brief  Flush data cache for a memory region
 */
void fl_flush_dcache(fl_context_t* ctx, const void* addr, size_t len);

/**
 * @brief  Invalidate instruction cache for a memory region
 */
void fl_invalidate_icache(fl_context_t* ctx, const void* addr, size_t len);

/**
 * @brief  Check if [addr, addr+len) is a safe memory range
 * @return true if the range is safe to access
 */
bool fl_check_addr_range(uintptr_t addr, size_t len);

/* ===========================
   Command handler declarations
   =========================== */

/* Core commands (fl_cmd_core.c) */
fl_error_t fl_cmd_ping(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_echo(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_echoback(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_info(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_hello(fl_context_t* ctx, const cmd_args_t* args);

/* Memory commands (fl_cmd_mem.c) */
fl_error_t fl_cmd_alloc(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_upload(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_read(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_write(fl_context_t* ctx, const cmd_args_t* args);

/* Patch commands (fl_cmd_patch.c) */
void fl_cmd_print_fpb_info(fl_context_t* ctx);
fl_error_t fl_cmd_patch(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_tpatch(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_dpatch(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_unpatch(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_enable(fl_context_t* ctx, const cmd_args_t* args);

/* File commands (fl_cmd_file.c) */
#if FL_USE_FILE
fl_error_t fl_cmd_fopen(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_fwrite(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_fread(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_fclose(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_fcrc(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_fseek(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_fstat(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_flist(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_fremove(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_fmkdir(fl_context_t* ctx, const cmd_args_t* args);
fl_error_t fl_cmd_frename(fl_context_t* ctx, const cmd_args_t* args);
#endif

#ifdef __cplusplus
}
#endif

#endif /* FL_CMD_H */
