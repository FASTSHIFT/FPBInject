/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 */

/**
 * @file   fl_cmd_file.c
 * @brief  File transfer command handlers
 */

#include "fl_cmd.h"
#include <limits.h>
#include <string.h>

/* ===========================
   FILE TRANSFER COMMANDS
   =========================== */

#if FL_USE_FILE

fl_error_t fl_cmd_fopen(fl_context_t* ctx, const cmd_args_t* args) {
    const char* mode = args->mode ? args->mode : "r";
    if (!ctx->file_ctx.fs) {
        fl_response(false, "File context not initialized");
        return FL_ERR_STATE;
    }

    if (!args->path || !mode) {
        fl_response(false, "Missing path or mode");
        return FL_ERR_ARGS;
    }

    /* Verify CRC if provided: covers path + mode strings */
    {
        uint16_t calc = 0xFFFF;
        calc = fl_crc16_base_str(calc, args->path);
        calc = fl_crc16_base_str(calc, mode);
        if (!fl_verify_crc(args->crc, calc)) {
            return FL_ERR_CRC;
        }
    }

    if (fl_file_open(&ctx->file_ctx, args->path, mode) != 0) {
        fl_response(false, "Failed to open: %s", args->path);
        return FL_ERR_IO;
    }

    fl_response(true, "FOPEN %s mode=%s", args->path, mode);
    return FL_OK;
}

fl_error_t fl_cmd_fwrite(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fp) {
        fl_response(false, "No file open");
        return FL_ERR_STATE;
    }

    if (!args->data) {
        fl_response(false, "Missing data");
        return FL_ERR_ARGS;
    }

    /* Decode base64 data */
    int n = fl_base64_decode(args->data, ctx->buf, FL_BUF_SIZE);
    if (n < 0) {
        fl_response(false, "Invalid base64 data");
        return FL_ERR_ENCODE;
    }

    /* Verify CRC if provided */
    if (!fl_verify_crc(args->crc, fl_crc16(ctx->buf, n))) {
        return FL_ERR_CRC;
    }

    /* Write to file */
    ssize_t written = fl_file_write(&ctx->file_ctx, ctx->buf, n);
    if (written < 0 || (int)written != n) {
        fl_response(false, "Write failed, expected %d bytes, actual %d bytes", n, (int)written);
        return FL_ERR_IO;
    }

    fl_response(true, "FWRITE %d bytes", (int)written);
    return FL_OK;
}

fl_error_t fl_cmd_fread(fl_context_t* ctx, const cmd_args_t* args) {
    int len = args->len;
    if (!ctx->file_ctx.fp) {
        fl_response(false, "No file open");
        return FL_ERR_STATE;
    }

    if (len <= 0 || len > (int)FL_BUF_SIZE) {
        len = FL_BUF_SIZE;
    }

    ssize_t nread = fl_file_read(&ctx->file_ctx, ctx->buf, len);
    if (nread < 0) {
        fl_response(false, "Read failed");
        return FL_ERR_IO;
    }

    if (nread != len) {
        fl_println("WARNING! Read expected %d bytes, actual %d bytes", len, (int)nread);
    }

    if (nread == 0) {
        fl_response(true, "FREAD 0 bytes EOF");
        return FL_OK;
    }

    /* Encode to base64 */
    if (fl_base64_encode(ctx->buf, nread, ctx->b64_buf, FL_B64_BUF_SIZE) < 0) {
        fl_response(false, "Base64 encode failed");
        return FL_ERR_ENCODE;
    }

    /* Calculate CRC */
    uint16_t crc = fl_crc16(ctx->buf, nread);

    /* Output in parts to avoid buffer overflow */
    fl_print("[FLOK] FREAD %d bytes crc=0x%04X data=", (int)nread, (unsigned)crc);
    fl_print_raw(ctx->b64_buf);
    fl_print_raw("\n[FLEND]\n");
    return FL_OK;
}

fl_error_t fl_cmd_fclose(fl_context_t* ctx, const cmd_args_t* args) {
    (void)args;
    if (!ctx->file_ctx.fp) {
        fl_response(false, "No file open");
        return FL_ERR_STATE;
    }

    if (fl_file_close(&ctx->file_ctx) != 0) {
        fl_response(false, "Close failed");
        return FL_ERR_IO;
    }

    fl_response(true, "FCLOSE");
    return FL_OK;
}

fl_error_t fl_cmd_fcrc(fl_context_t* ctx, const cmd_args_t* args) {
    off_t offset = (off_t)args->addr; /* Start offset (0 = from beginning) */
    off_t size = (off_t)args->len;
    int init_crc = args->crc; /* Previous CRC for chained calculation, -1 = initial */

    if (!ctx->file_ctx.fp) {
        fl_response(false, "No file open");
        return FL_ERR_STATE;
    }

    /* Seek to specified offset */
    if (fl_file_seek(&ctx->file_ctx, offset, FL_SEEK_SET) < 0) {
        fl_response(false, "Failed to seek to offset %ld", (long)offset);
        return FL_ERR_IO;
    }

    /* Use provided CRC as initial value for chained calculation */
    uint16_t crc = (init_crc >= 0) ? (uint16_t)init_crc : 0xFFFF;
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
            return FL_ERR_IO;
        }
        if (nread == 0) {
            break; /* EOF */
        }

        /* Update CRC incrementally (same algorithm as calc_crc16) */
        crc = fl_crc16_base(crc, ctx->buf, nread);
        total_read += nread;
        remaining -= nread;
    }

    fl_response(true, "FCRC offset=%ld size=%ld crc=0x%04X", (long)offset, (long)total_read, (unsigned)crc);
    return FL_OK;
}

fl_error_t fl_cmd_fseek(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fp) {
        fl_response(false, "No file open");
        return FL_ERR_STATE;
    }

    /* Verify CRC if provided: covers addr(4B) */
    {
        int32_t addr32 = (int32_t)args->addr;
        if (!fl_verify_crc(args->crc, fl_crc16(&addr32, sizeof(addr32)))) {
            return FL_ERR_CRC;
        }
    }

    off_t new_pos = fl_file_seek(&ctx->file_ctx, (off_t)args->addr, FL_SEEK_SET);
    if (new_pos < 0) {
        fl_response(false, "Seek failed");
        return FL_ERR_IO;
    }

    fl_response(true, "FSEEK %ld", (long)new_pos);
    return FL_OK;
}

fl_error_t fl_cmd_fstat(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fs) {
        fl_response(false, "File context not initialized");
        return FL_ERR_STATE;
    }

    if (!args->path) {
        fl_response(false, "Missing path");
        return FL_ERR_ARGS;
    }

    /* Verify CRC if provided: covers path string */
    if (!fl_verify_crc(args->crc, fl_crc16_str(args->path))) {
        return FL_ERR_CRC;
    }

    fl_file_stat_t st;
    if (fl_file_stat(&ctx->file_ctx, args->path, &st) != 0) {
        fl_response(false, "Stat failed: %s", args->path);
        return FL_ERR_IO;
    }

    const char* type_str = (st.type == FL_FILE_TYPE_DIR) ? "dir" : "file";
    fl_response(true, "FSTAT %s size=%u mtime=%u type=%s", args->path, (unsigned)st.size, (unsigned)st.mtime, type_str);
    return FL_OK;
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
    return FL_OK;
}

fl_error_t fl_cmd_flist(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fs) {
        fl_response(false, "File context not initialized");
        return FL_ERR_STATE;
    }

    if (!args->path) {
        fl_response(false, "Missing path");
        return FL_ERR_ARGS;
    }

    /* Verify CRC if provided: covers path string */
    if (!fl_verify_crc(args->crc, fl_crc16_str(args->path))) {
        return FL_ERR_CRC;
    }

    /* First pass: count dirs and files */
    flist_count_ctx_t count_ctx = {0, 0};
    int total = fl_file_list_cb(&ctx->file_ctx, args->path, flist_print_cb, &count_ctx);
    if (total < 0) {
        fl_response(false, "List failed: %s", args->path);
        return FL_ERR_IO;
    }

    fl_response(true, "FLIST dir=%d file=%d", count_ctx.dir_count, count_ctx.file_count);
    return FL_OK;
}

fl_error_t fl_cmd_fremove(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fs) {
        fl_response(false, "File context not initialized");
        return FL_ERR_STATE;
    }

    if (!args->path) {
        fl_response(false, "Missing path");
        return FL_ERR_ARGS;
    }

    /* Verify CRC if provided: covers path string */
    if (!fl_verify_crc(args->crc, fl_crc16_str(args->path))) {
        return FL_ERR_CRC;
    }

    if (fl_file_remove(&ctx->file_ctx, args->path) != 0) {
        fl_response(false, "Remove failed: %s", args->path);
        return FL_ERR_IO;
    }

    fl_response(true, "FREMOVE %s", args->path);
    return FL_OK;
}

fl_error_t fl_cmd_fmkdir(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fs) {
        fl_response(false, "File context not initialized");
        return FL_ERR_STATE;
    }

    if (!args->path) {
        fl_response(false, "Missing path");
        return FL_ERR_ARGS;
    }

    /* Verify CRC if provided: covers path string */
    if (!fl_verify_crc(args->crc, fl_crc16_str(args->path))) {
        return FL_ERR_CRC;
    }

    if (fl_file_mkdir(&ctx->file_ctx, args->path) != 0) {
        fl_response(false, "Mkdir failed: %s", args->path);
        return FL_ERR_IO;
    }

    fl_response(true, "FMKDIR %s", args->path);
    return FL_OK;
}

fl_error_t fl_cmd_frename(fl_context_t* ctx, const cmd_args_t* args) {
    if (!ctx->file_ctx.fs) {
        fl_response(false, "File context not initialized");
        return FL_ERR_STATE;
    }

    if (!args->path) {
        fl_response(false, "Missing path");
        return FL_ERR_ARGS;
    }

    if (!args->newpath) {
        fl_response(false, "Missing newpath");
        return FL_ERR_ARGS;
    }

    /* Verify CRC if provided: covers path + newpath strings */
    {
        uint16_t calc = 0xFFFF;
        calc = fl_crc16_base_str(calc, args->path);
        calc = fl_crc16_base_str(calc, args->newpath);
        if (!fl_verify_crc(args->crc, calc)) {
            return FL_ERR_CRC;
        }
    }

    if (fl_file_rename(&ctx->file_ctx, args->path, args->newpath) != 0) {
        fl_response(false, "Rename failed: %s -> %s", args->path, args->newpath);
        return FL_ERR_IO;
    }

    fl_response(true, "FRENAME %s -> %s", args->path, args->newpath);
    return FL_OK;
}

#endif /* FL_USE_FILE */
