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
 * @file   func_loader_file.h
 * @brief  File transfer module with filesystem abstraction
 */

#ifndef __FUNC_LOADER_FILE_H
#define __FUNC_LOADER_FILE_H

#ifndef FL_USE_FILE
#define FL_USE_FILE 0
#endif

#ifndef FL_FILE_USE_POSIX
#define FL_FILE_USE_POSIX 0
#endif

#ifndef FL_FILE_USE_LIBC
#define FL_FILE_USE_LIBC 0
#endif

#ifndef FL_FILE_USE_FATFS
#define FL_FILE_USE_FATFS 0
#endif

#if FL_USE_FILE

#ifdef __cplusplus
extern "C" {
#endif

#include <stddef.h>
#include <stdint.h>
#include <sys/types.h>

/* Maximum path length */
#ifndef FL_FILE_PATH_MAX
#define FL_FILE_PATH_MAX 128
#endif

/* File transfer buffer sizes */
#ifndef FL_FILE_BUF_SIZE
#define FL_FILE_BUF_SIZE 1024
#endif
#ifndef FL_FILE_B64_BUF_SIZE
#define FL_FILE_B64_BUF_SIZE 2048
#endif

/* File open modes (for fl_file_open mode string) */
#define FL_FILE_MODE_READ 0x01
#define FL_FILE_MODE_WRITE 0x02
#define FL_FILE_MODE_APPEND 0x04
#define FL_FILE_MODE_CREATE 0x08
#define FL_FILE_MODE_TRUNC 0x10

/* File open flags (for fs_ops->open) */
#define FL_O_RDONLY 0x0000
#define FL_O_WRONLY 0x0001
#define FL_O_RDWR 0x0002
#define FL_O_CREAT 0x0100
#define FL_O_TRUNC 0x0200
#define FL_O_APPEND 0x0400

/* Seek whence values */
#define FL_SEEK_SET 0
#define FL_SEEK_CUR 1
#define FL_SEEK_END 2

/* File types */
#define FL_FILE_TYPE_REG 0x01 /* Regular file */
#define FL_FILE_TYPE_DIR 0x02 /* Directory */

/**
 * @brief File stat structure
 */
typedef struct fl_file_stat_s {
    uint32_t size;  /* File size in bytes */
    uint32_t mtime; /* Modification time (Unix timestamp) */
    uint8_t type;   /* File type (FL_FILE_TYPE_*) */
} fl_file_stat_t;

/**
 * @brief Directory entry structure
 */
typedef struct fl_dirent_s {
    char name[64]; /* Entry name */
    uint8_t type;  /* Entry type (FL_FILE_TYPE_*) */
    uint32_t size; /* File size (0 for directories) */
} fl_dirent_t;

/**
 * @brief File system operations interface (function pointer abstraction)
 *
 * This allows supporting different filesystem backends:
 * - POSIX (NuttX VFS, Linux)
 * - LittleFS
 * - FATFS
 * - Custom implementations
 *
 * Note: File handle (void*) can be:
 * - Cast from int fd for POSIX-like systems: (void*)(intptr_t)fd
 * - Direct FILE* pointer for libc
 * - Custom handle for other filesystems
 */
typedef struct fl_fs_ops_s {
    /* File operations */
    void* (*open)(const char* path, int flags, int mode);
    int (*close)(void* fp);
    ssize_t (*read)(void* fp, void* buf, size_t count);
    ssize_t (*write)(void* fp, const void* buf, size_t count);
    off_t (*lseek)(void* fp, off_t offset, int whence);
    int (*fsync)(void* fp);

    /* File info */
    int (*stat)(const char* path, fl_file_stat_t* st);

    /* Directory operations */
    void* (*opendir)(const char* path);
    int (*readdir)(void* dirp, fl_dirent_t* entry);
    int (*closedir)(void* dirp);

    /* File management */
    int (*unlink)(const char* path);
    int (*rmdir)(const char* path);
    int (*mkdir)(const char* path, int mode);
    int (*rename)(const char* oldpath, const char* newpath);
} fl_fs_ops_t;

/**
 * @brief File transfer context
 */
typedef struct fl_file_ctx_s {
    const fl_fs_ops_t* fs;       /* Filesystem operations */
    void* fp;                    /* Current open file handle */
    char path[FL_FILE_PATH_MAX]; /* Current file path */
    size_t offset;               /* Current read/write offset */
    size_t total_size;           /* Total file size (for progress) */

    /* Transfer buffers */
    uint8_t buf[FL_FILE_BUF_SIZE];      /* Data buffer for read/write */
    char b64_buf[FL_FILE_B64_BUF_SIZE]; /* Base64 encoding buffer */
} fl_file_ctx_t;

#if FL_FILE_USE_POSIX

/**
 * @brief Get default POSIX filesystem operations
 * @return Pointer to default POSIX fs_ops
 */
const fl_fs_ops_t* fl_file_get_posix_ops(void);

#endif /* FL_FILE_USE_POSIX */

#if FL_FILE_USE_LIBC

/**
 * @brief Get standard C library (stdio.h) filesystem operations
 * @return Pointer to libc fs_ops
 */
const fl_fs_ops_t* fl_file_get_libc_ops(void);

#endif /* FL_FILE_USE_LIBC */

#if FL_FILE_USE_FATFS

/**
 * @brief Get FatFS filesystem operations
 * @return Pointer to FatFS fs_ops
 */
const fl_fs_ops_t* fl_file_get_fatfs_ops(void);

#endif /* FL_FILE_USE_FATFS */

/**
 * @brief Open a file
 * @param file_ctx File context
 * @param path File path
 * @param mode Mode string ("r", "w", "a", "rw")
 * @return 0 on success, -1 on error
 */
int fl_file_open(fl_file_ctx_t* file_ctx, const char* path, const char* mode);

/**
 * @brief Write data to open file
 * @param file_ctx File context
 * @param data Data buffer
 * @param len Data length
 * @return Bytes written, or -1 on error
 */
ssize_t fl_file_write(fl_file_ctx_t* file_ctx, const void* data, size_t len);

/**
 * @brief Read data from open file
 * @param file_ctx File context
 * @param buf Buffer to read into
 * @param len Maximum bytes to read
 * @return Bytes read, or -1 on error
 */
ssize_t fl_file_read(fl_file_ctx_t* file_ctx, void* buf, size_t len);

/**
 * @brief Close open file
 * @param file_ctx File context
 * @return 0 on success, -1 on error
 */
int fl_file_close(fl_file_ctx_t* file_ctx);

/**
 * @brief Seek to position in open file
 * @param file_ctx File context
 * @param offset Offset in bytes
 * @param whence FL_SEEK_SET (0), FL_SEEK_CUR (1), or FL_SEEK_END (2)
 * @return New position on success, -1 on error
 */
off_t fl_file_seek(fl_file_ctx_t* file_ctx, off_t offset, int whence);

/**
 * @brief Get file status
 * @param file_ctx File context
 * @param path File path
 * @param st Stat structure to fill
 * @return 0 on success, -1 on error
 */
int fl_file_stat(fl_file_ctx_t* file_ctx, const char* path, fl_file_stat_t* st);

/**
 * @brief Directory entry callback function type
 * @param entry Directory entry
 * @param user_data User data passed to fl_file_list_cb
 * @return 0 to continue, non-zero to stop iteration
 */
typedef int (*fl_file_list_cb_t)(const fl_dirent_t* entry, void* user_data);

/**
 * @brief List directory contents with callback
 * @param file_ctx File context
 * @param path Directory path
 * @param callback Callback function for each entry
 * @param user_data User data passed to callback
 * @return Number of entries processed, or -1 on error
 */
int fl_file_list_cb(fl_file_ctx_t* file_ctx, const char* path, fl_file_list_cb_t callback, void* user_data);

/**
 * @brief List directory contents
 * @param file_ctx File context
 * @param path Directory path
 * @param entries Array to fill with entries
 * @param max_entries Maximum entries to return
 * @return Number of entries, or -1 on error
 * @note This is a convenience wrapper around fl_file_list_cb
 */
int fl_file_list(fl_file_ctx_t* file_ctx, const char* path, fl_dirent_t* entries, int max_entries);

/**
 * @brief Remove a file
 * @param file_ctx File context
 * @param path File path
 * @return 0 on success, -1 on error
 */
int fl_file_remove(fl_file_ctx_t* file_ctx, const char* path);

/**
 * Create a directory
 * @param file_ctx File context
 * @param path Directory path
 * @return 0 on success, -1 on error
 */
int fl_file_mkdir(fl_file_ctx_t* file_ctx, const char* path);

/**
 * Rename a file or directory
 * @param file_ctx File context
 * @param oldpath Current path
 * @param newpath New path
 * @return 0 on success, -1 on error
 */
int fl_file_rename(fl_file_ctx_t* file_ctx, const char* oldpath, const char* newpath);

#ifdef __cplusplus
}
#endif

#endif /* FL_USE_FILE */

#endif /* __FUNC_LOADER_FILE_H */
