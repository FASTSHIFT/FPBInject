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
 * @file   func_loader_file_libc.c
 * @brief  File transfer implementation using standard C library (stdio.h)
 *
 * This implementation uses FILE* based operations.
 * Suitable for platforms that only provide standard C library.
 *
 * Note: This implementation directly uses FILE* as the void* handle,
 * no file table mapping needed.
 *
 * Limitations:
 * - Directory operations (opendir/readdir/closedir/mkdir) are not supported
 *   in pure standard C library. These functions return error.
 * - stat() is not part of standard C, so fstat-like functionality is limited.
 */

#include "func_loader_file.h"

#if FL_FILE_USE_LIBC

#include <stdio.h>
#include <string.h>

/**
 * @brief Convert FL flags to fopen mode string
 */
static const char* fl_flags_to_mode(int flags) {
    int rdwr = flags & (FL_O_RDONLY | FL_O_WRONLY | FL_O_RDWR);
    int trunc = flags & FL_O_TRUNC;
    int append = flags & FL_O_APPEND;
    int create = flags & FL_O_CREAT;

    if (rdwr == FL_O_RDONLY) {
        return "rb";
    } else if (rdwr == FL_O_WRONLY) {
        if (append) {
            return "ab";
        } else if (trunc || create) {
            return "wb";
        } else {
            return "r+b"; /* Write to existing file */
        }
    } else if (rdwr == FL_O_RDWR) {
        if (trunc) {
            return "w+b";
        } else if (append) {
            return "a+b";
        } else if (create) {
            return "w+b";
        } else {
            return "r+b";
        }
    }

    return "rb"; /* Default */
}

static void* libc_open(const char* path, int flags, int mode) {
    (void)mode; /* mode not used in libc */
    const char* fmode = fl_flags_to_mode(flags);
    return fopen(path, fmode);
}

static int libc_close(void* fp) {
    if (!fp) {
        return -1;
    }
    return fclose((FILE*)fp);
}

static ssize_t libc_read(void* fp, void* buf, size_t count) {
    if (!fp) {
        return -1;
    }
    size_t nread = fread(buf, 1, count, (FILE*)fp);
    if (nread == 0 && ferror((FILE*)fp)) {
        return -1;
    }
    return (ssize_t)nread;
}

static ssize_t libc_write(void* fp, const void* buf, size_t count) {
    if (!fp) {
        return -1;
    }
    size_t nwritten = fwrite(buf, 1, count, (FILE*)fp);
    if (nwritten == 0 && ferror((FILE*)fp)) {
        return -1;
    }
    return (ssize_t)nwritten;
}

static off_t libc_lseek(void* fp, off_t offset, int whence) {
    if (!fp) {
        return -1;
    }

    /* Convert FL_SEEK_* to SEEK_* */
    int seek_whence;
    switch (whence) {
    case FL_SEEK_SET:
        seek_whence = SEEK_SET;
        break;
    case FL_SEEK_CUR:
        seek_whence = SEEK_CUR;
        break;
    case FL_SEEK_END:
        seek_whence = SEEK_END;
        break;
    default:
        seek_whence = SEEK_SET;
        break;
    }

    if (fseek((FILE*)fp, offset, seek_whence) != 0) {
        return -1;
    }
    return (off_t)ftell((FILE*)fp);
}

static int libc_fsync(void* fp) {
    if (!fp) {
        return -1;
    }
    return fflush((FILE*)fp);
}

/**
 * @brief Get file status using fseek/ftell (limited functionality)
 *
 * Note: Standard C library doesn't have stat(), so we can only get file size
 * by seeking to end. mtime and type cannot be determined.
 */
static int libc_stat(const char* path, fl_file_stat_t* st) {
    FILE* fp = fopen(path, "rb");
    if (!fp) {
        return -1;
    }

    /* Get file size by seeking to end */
    if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        return -1;
    }

    long size = ftell(fp);
    fclose(fp);

    if (size < 0) {
        return -1;
    }

    st->size = (uint32_t)size;
    st->mtime = 0;               /* Cannot determine with pure libc */
    st->type = FL_FILE_TYPE_REG; /* Assume regular file */
    return 0;
}

/*
 * Directory operations - not supported in pure standard C library.
 * These functions return error (-1 or NULL).
 */

static void* libc_opendir(const char* path) {
    (void)path;
    return NULL; /* Not supported */
}

static int libc_readdir(void* dirp, fl_dirent_t* entry) {
    (void)dirp;
    (void)entry;
    return -1; /* Not supported */
}

static int libc_closedir(void* dirp) {
    (void)dirp;
    return -1; /* Not supported */
}

static int libc_unlink(const char* path) {
    return remove(path);
}

static int libc_mkdir(const char* path, int mode) {
    (void)path;
    (void)mode;
    return -1; /* Not supported in pure libc */
}

static int libc_rename(const char* oldpath, const char* newpath) {
    return rename(oldpath, newpath);
}

/* Standard C library filesystem operations */
static const fl_fs_ops_t s_libc_fs_ops = {
    .open = libc_open,
    .close = libc_close,
    .read = libc_read,
    .write = libc_write,
    .lseek = libc_lseek,
    .fsync = libc_fsync,
    .stat = libc_stat,
    .opendir = libc_opendir,
    .readdir = libc_readdir,
    .closedir = libc_closedir,
    .unlink = libc_unlink,
    .mkdir = libc_mkdir,
    .rename = libc_rename,
};

const fl_fs_ops_t* fl_file_get_libc_ops(void) {
    return &s_libc_fs_ops;
}

#endif /* FL_FILE_USE_LIBC */
