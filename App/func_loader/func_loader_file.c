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
 * @file   func_loader_file.c
 * @brief  File transfer module implementation
 */

#include "func_loader_file.h"
#include "func_loader_log.h"

#ifdef FL_USE_FILE

#include <stdio.h>
#include <string.h>

int fl_file_open(fl_file_ctx_t* file_ctx, const char* path, const char* mode) {
    if (!file_ctx || !file_ctx->fs || !path || !mode) {
        return -1;
    }

    /* Close any previously open file */
    if (file_ctx->fp) {
        fl_println("Warning: Closing previously open file: %s", file_ctx->path);
        fl_file_close(file_ctx);
    }

    /* Parse mode string to flags */
    int flags = 0;
    if (strchr(mode, 'r') && strchr(mode, 'w')) {
        flags = FL_O_RDWR;
    } else if (strchr(mode, 'r')) {
        flags = FL_O_RDONLY;
    } else if (strchr(mode, 'w')) {
        flags = FL_O_WRONLY | FL_O_CREAT | FL_O_TRUNC;
    } else if (strchr(mode, 'a')) {
        flags = FL_O_WRONLY | FL_O_CREAT | FL_O_APPEND;
    } else {
        fl_println("Invalid mode string: %s", mode);
        return -1;
    }

    void* fp = file_ctx->fs->open(path, flags, 0644);
    if (!fp) {
        return -1;
    }

    file_ctx->fp = fp;
    strncpy(file_ctx->path, path, FL_FILE_PATH_MAX - 1);
    file_ctx->path[FL_FILE_PATH_MAX - 1] = '\0';
    file_ctx->offset = 0;

    /* Get file size for read mode */
    if (strchr(mode, 'r')) {
        fl_file_stat_t st;
        if (file_ctx->fs->stat(path, &st) == 0) {
            file_ctx->total_size = st.size;
        }
    } else {
        file_ctx->total_size = 0;
    }

    return 0;
}

ssize_t fl_file_write(fl_file_ctx_t* file_ctx, const void* data, size_t len) {
    if (!file_ctx || !file_ctx->fs || !file_ctx->fp || !data) {
        return -1;
    }

    ssize_t written = file_ctx->fs->write(file_ctx->fp, data, len);
    if (written > 0) {
        file_ctx->offset += written;
        if (file_ctx->offset > file_ctx->total_size) {
            file_ctx->total_size = file_ctx->offset;
        }
    }

    return written;
}

ssize_t fl_file_read(fl_file_ctx_t* file_ctx, void* buf, size_t len) {
    if (!file_ctx || !file_ctx->fs || !file_ctx->fp || !buf) {
        return -1;
    }

    ssize_t nread = file_ctx->fs->read(file_ctx->fp, buf, len);
    if (nread > 0) {
        file_ctx->offset += nread;
    }

    return nread;
}

int fl_file_close(fl_file_ctx_t* file_ctx) {
    if (!file_ctx || !file_ctx->fs || !file_ctx->fp) {
        return -1;
    }

    /* Sync before close */
    if (file_ctx->fs->fsync) {
        file_ctx->fs->fsync(file_ctx->fp);
    }

    int ret = file_ctx->fs->close(file_ctx->fp);
    file_ctx->fp = NULL;
    file_ctx->path[0] = '\0';
    file_ctx->offset = 0;
    file_ctx->total_size = 0;

    return ret;
}

int fl_file_stat(fl_file_ctx_t* file_ctx, const char* path, fl_file_stat_t* st) {
    if (!file_ctx || !file_ctx->fs || !path || !st) {
        return -1;
    }

    return file_ctx->fs->stat(path, st);
}

int fl_file_list(fl_file_ctx_t* file_ctx, const char* path, fl_dirent_t* entries, int max_entries) {
    if (!file_ctx || !file_ctx->fs || !path || !entries || max_entries <= 0) {
        return -1;
    }

    void* dirp = file_ctx->fs->opendir(path);
    if (!dirp) {
        return -1;
    }

    int count = 0;
    fl_dirent_t entry;

    while (count < max_entries && file_ctx->fs->readdir(dirp, &entry) == 0) {
        /* Skip . and .. */
        if (strcmp(entry.name, ".") == 0 || strcmp(entry.name, "..") == 0) {
            continue;
        }

        /* Get file size for regular files */
        if (entry.type == FL_FILE_TYPE_REG) {
            char fullpath[FL_FILE_PATH_MAX];
            snprintf(fullpath, sizeof(fullpath), "%s/%s", path, entry.name);
            fl_file_stat_t st;
            if (file_ctx->fs->stat(fullpath, &st) == 0) {
                entry.size = st.size;
            }
        }

        entries[count++] = entry;
    }

    file_ctx->fs->closedir(dirp);
    return count;
}

int fl_file_remove(fl_file_ctx_t* file_ctx, const char* path) {
    if (!file_ctx || !file_ctx->fs || !path) {
        return -1;
    }

    return file_ctx->fs->unlink(path);
}

int fl_file_mkdir(fl_file_ctx_t* file_ctx, const char* path) {
    if (!file_ctx || !file_ctx->fs || !path) {
        return -1;
    }

    return file_ctx->fs->mkdir(path, 0755);
}

#endif /* FL_USE_FILE */
