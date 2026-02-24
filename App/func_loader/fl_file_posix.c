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

#include "fl_file.h"
#include "fl_log.h"

#if FL_FILE_USE_POSIX

#include <fcntl.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/stat.h>

#define FD2PTR(fd) ((void*)(uintptr_t)((fd) + 1)) /* +1 to avoid NULL for fd=0 */
#define PTR2FD(ptr) ((int)((uintptr_t)(ptr)-1))

/**
 * @brief Convert FL flags to POSIX flags
 */
static int fl_flags_to_posix(int fl_flags) {
    int flags = 0;

    /* Access mode */
    if ((fl_flags & FL_O_RDWR) == FL_O_RDWR) {
        flags |= O_RDWR;
    } else if (fl_flags & FL_O_WRONLY) {
        flags |= O_WRONLY;
    } else {
        flags |= O_RDONLY;
    }

    /* Creation flags */
    if (fl_flags & FL_O_CREAT) {
        flags |= O_CREAT;
    }
    if (fl_flags & FL_O_TRUNC) {
        flags |= O_TRUNC;
    }
    if (fl_flags & FL_O_APPEND) {
        flags |= O_APPEND;
    }

    return flags;
}

static void* posix_open(const char* path, int flags, int mode) {
    int fd = open(path, fl_flags_to_posix(flags), mode);
    if (fd < 0) {
        fl_println("Failed to open file %s: flags: 0x%x, mode: 0x%x, errno: %d", path, flags, mode, errno);
        return NULL;
    }
    return FD2PTR(fd);
}

static int posix_close(void* fp) {
    int fd = PTR2FD(fp);
    int ret = close(fd);
    if (ret < 0) {
        fl_println("Failed to close fd %d: errno: %d", fd, errno);
    }
    return ret;
}

static ssize_t posix_read(void* fp, void* buf, size_t count) {
    int fd = PTR2FD(fp);
    ssize_t ret = read(fd, buf, count);
    if (ret < 0) {
        fl_println("Failed to read from fd %d: errno: %d", fd, errno);
    }
    return ret;
}

static ssize_t posix_write(void* fp, const void* buf, size_t count) {
    int fd = PTR2FD(fp);
    ssize_t ret = write(fd, buf, count);
    if (ret < 0) {
        fl_println("Failed to write to fd %d: errno: %d", fd, errno);
    }
    return ret;
}

static off_t posix_lseek(void* fp, off_t offset, int whence) {
    int fd = PTR2FD(fp);
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
    off_t ret = lseek(fd, offset, seek_whence);
    if (ret < 0) {
        fl_println("Failed to lseek fd %d: errno: %d", fd, errno);
    }
    return ret;
}

static int posix_fsync(void* fp) {
    int fd = PTR2FD(fp);
    int ret = fsync(fd);
    if (ret < 0) {
        fl_println("Failed to fsync fd %d: errno: %d", fd, errno);
    }
    return ret;
}

static int posix_stat(const char* path, fl_file_stat_t* st) {
    struct stat sb;
    if (stat(path, &sb) != 0) {
        fl_println("Failed to stat file %s: errno: %d", path, errno);
        return -1;
    }
    st->size = (uint32_t)sb.st_size;
    st->mtime = (uint32_t)sb.st_mtime;
    st->type = S_ISDIR(sb.st_mode) ? FL_FILE_TYPE_DIR : FL_FILE_TYPE_REG;
    return 0;
}

static void* posix_opendir(const char* path) {
    void* dir = opendir(path);
    if (!dir) {
        fl_println("Failed to open dir %s: errno: %d", path, errno);
    }
    return dir;
}

static int posix_readdir(void* dirp, fl_dirent_t* entry) {
    struct dirent* de = readdir((DIR*)dirp);
    if (!de) {
        return -1;
    }

    strncpy(entry->name, de->d_name, sizeof(entry->name) - 1);
    entry->name[sizeof(entry->name) - 1] = '\0';

    /* Determine type */
    if (de->d_type == DT_DIR) {
        entry->type = FL_FILE_TYPE_DIR;
    } else {
        entry->type = FL_FILE_TYPE_REG;
    }

    entry->size = 0; /* Size not available from dirent */
    return 0;
}

static int posix_closedir(void* dirp) {
    int ret = closedir((DIR*)dirp);
    if (ret < 0) {
        fl_println("Failed to closedir: errno: %d", errno);
    }
    return ret;
}

static int posix_unlink(const char* path) {
    int ret = unlink(path);
    if (ret < 0) {
        fl_println("Failed to unlink %s: errno: %d", path, errno);
    }
    return ret;
}

static int posix_rmdir(const char* path) {
    int ret = rmdir(path);
    if (ret < 0) {
        fl_println("Failed to rmdir %s: errno: %d", path, errno);
    }
    return ret;
}

static int posix_mkdir(const char* path, int mode) {
    int ret = mkdir(path, mode);
    if (ret < 0) {
        fl_println("Failed to mkdir %s: errno: %d", path, errno);
    }
    return ret;
}

static int posix_rename(const char* oldpath, const char* newpath) {
    int ret = rename(oldpath, newpath);
    if (ret < 0) {
        fl_println("Failed to rename %s to %s: errno: %d", oldpath, newpath, errno);
    }
    return ret;
}

/* Default POSIX filesystem operations */
static const fl_fs_ops_t s_posix_fs_ops = {
    .open = posix_open,
    .close = posix_close,
    .read = posix_read,
    .write = posix_write,
    .lseek = posix_lseek,
    .fsync = posix_fsync,
    .stat = posix_stat,
    .opendir = posix_opendir,
    .readdir = posix_readdir,
    .closedir = posix_closedir,
    .unlink = posix_unlink,
    .rmdir = posix_rmdir,
    .mkdir = posix_mkdir,
    .rename = posix_rename,
};

const fl_fs_ops_t* fl_file_get_posix_ops(void) {
    return &s_posix_fs_ops;
}

#endif /* FL_FILE_USE_POSIX */
