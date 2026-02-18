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

#include "func_loader_file.h"

#ifndef FL_FILE_USE_FATFS
#define FL_FILE_USE_FATFS 0
#endif

#if FL_USE_FILE && FL_FILE_USE_FATFS

#include "ff.h"
#include <string.h>

/* FatFS file handle wrapper */
typedef struct {
    FIL fil;
    uint8_t is_open;
} fatfs_file_t;

/* FatFS directory handle wrapper */
typedef struct {
    DIR dir;
    uint8_t is_open;
} fatfs_dir_t;

/* Static file/dir handles pool (avoid dynamic allocation) */
#ifndef FL_FATFS_MAX_FILES
#define FL_FATFS_MAX_FILES 1
#endif

#ifndef FL_FATFS_MAX_DIRS
#define FL_FATFS_MAX_DIRS 1
#endif

static fatfs_file_t s_files[FL_FATFS_MAX_FILES];
static fatfs_dir_t s_dirs[FL_FATFS_MAX_DIRS];

static fatfs_file_t* fatfs_alloc_file(void) {
    for (int i = 0; i < FL_FATFS_MAX_FILES; i++) {
        if (!s_files[i].is_open) {
            s_files[i].is_open = 1;
            return &s_files[i];
        }
    }
    return NULL;
}

static void fatfs_free_file(fatfs_file_t* f) {
    if (f) {
        f->is_open = 0;
    }
}

static fatfs_dir_t* fatfs_alloc_dir(void) {
    for (int i = 0; i < FL_FATFS_MAX_DIRS; i++) {
        if (!s_dirs[i].is_open) {
            s_dirs[i].is_open = 1;
            return &s_dirs[i];
        }
    }
    return NULL;
}

static void fatfs_free_dir(fatfs_dir_t* d) {
    if (d) {
        d->is_open = 0;
    }
}

/* Convert FL flags to FatFS mode */
static BYTE fl_flags_to_fatfs(int flags) {
    BYTE mode = 0;

    if ((flags & FL_O_RDWR) == FL_O_RDWR) {
        mode = FA_READ | FA_WRITE;
    } else if (flags & FL_O_WRONLY) {
        mode = FA_WRITE;
    } else {
        mode = FA_READ;
    }

    if (flags & FL_O_CREAT) {
        mode |= FA_OPEN_ALWAYS;
    }
    if (flags & FL_O_TRUNC) {
        mode |= FA_CREATE_ALWAYS;
    }
    if (flags & FL_O_APPEND) {
        mode |= FA_OPEN_APPEND;
    }

    return mode;
}

static void* fatfs_open(const char* path, int flags, int mode) {
    (void)mode;

    fatfs_file_t* f = fatfs_alloc_file();
    if (!f) {
        return NULL;
    }

    BYTE fatfs_mode = fl_flags_to_fatfs(flags);
    FRESULT res = f_open(&f->fil, path, fatfs_mode);
    if (res != FR_OK) {
        fatfs_free_file(f);
        return NULL;
    }

    return f;
}

static int fatfs_close(void* fp) {
    fatfs_file_t* f = (fatfs_file_t*)fp;
    if (!f) {
        return -1;
    }

    FRESULT res = f_close(&f->fil);
    fatfs_free_file(f);
    return (res == FR_OK) ? 0 : -1;
}

static ssize_t fatfs_read(void* fp, void* buf, size_t count) {
    fatfs_file_t* f = (fatfs_file_t*)fp;
    if (!f) {
        return -1;
    }

    UINT br;
    FRESULT res = f_read(&f->fil, buf, (UINT)count, &br);
    if (res != FR_OK) {
        return -1;
    }
    return (ssize_t)br;
}

static ssize_t fatfs_write(void* fp, const void* buf, size_t count) {
    fatfs_file_t* f = (fatfs_file_t*)fp;
    if (!f) {
        return -1;
    }

    UINT bw;
    FRESULT res = f_write(&f->fil, buf, (UINT)count, &bw);
    if (res != FR_OK) {
        return -1;
    }
    return (ssize_t)bw;
}

static off_t fatfs_lseek(void* fp, off_t offset, int whence) {
    fatfs_file_t* f = (fatfs_file_t*)fp;
    if (!f) {
        return -1;
    }

    FSIZE_t new_pos;
    switch (whence) {
    case FL_SEEK_SET:
        new_pos = (FSIZE_t)offset;
        break;
    case FL_SEEK_CUR:
        new_pos = f_tell(&f->fil) + offset;
        break;
    case FL_SEEK_END:
        new_pos = f_size(&f->fil) + offset;
        break;
    default:
        return -1;
    }

    FRESULT res = f_lseek(&f->fil, new_pos);
    if (res != FR_OK) {
        return -1;
    }
    return (off_t)f_tell(&f->fil);
}

static int fatfs_fsync(void* fp) {
    fatfs_file_t* f = (fatfs_file_t*)fp;
    if (!f) {
        return -1;
    }

    FRESULT res = f_sync(&f->fil);
    return (res == FR_OK) ? 0 : -1;
}

static int fatfs_stat(const char* path, fl_file_stat_t* st) {
    FILINFO fno;
    FRESULT res = f_stat(path, &fno);
    if (res != FR_OK) {
        return -1;
    }

    st->size = (uint32_t)fno.fsize;
    st->type = (fno.fattrib & AM_DIR) ? FL_FILE_TYPE_DIR : FL_FILE_TYPE_REG;

    /* Convert FatFS date/time to Unix timestamp (approximate) */
    /* FatFS: fdate = ((year-1980)<<9) | (month<<5) | day */
    /* FatFS: ftime = (hour<<11) | (min<<5) | (sec/2) */
    uint16_t year = ((fno.fdate >> 9) & 0x7F) + 1980;
    uint16_t month = (fno.fdate >> 5) & 0x0F;
    uint16_t day = fno.fdate & 0x1F;
    uint16_t hour = (fno.ftime >> 11) & 0x1F;
    uint16_t min = (fno.ftime >> 5) & 0x3F;
    uint16_t sec = (fno.ftime & 0x1F) * 2;

    /* Simple Unix timestamp calculation (not accounting for leap years properly) */
    uint32_t days = (year - 1970) * 365 + (year - 1969) / 4;
    static const uint16_t month_days[] = {0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334};
    if (month > 0 && month <= 12) {
        days += month_days[month - 1];
    }
    days += day - 1;
    st->mtime = days * 86400 + hour * 3600 + min * 60 + sec;

    return 0;
}

static void* fatfs_opendir(const char* path) {
    fatfs_dir_t* d = fatfs_alloc_dir();
    if (!d) {
        return NULL;
    }

    FRESULT res = f_opendir(&d->dir, path);
    if (res != FR_OK) {
        fatfs_free_dir(d);
        return NULL;
    }

    return d;
}

static int fatfs_readdir(void* dirp, fl_dirent_t* entry) {
    fatfs_dir_t* d = (fatfs_dir_t*)dirp;
    if (!d || !entry) {
        return -1;
    }

    FILINFO fno;
    FRESULT res = f_readdir(&d->dir, &fno);
    if (res != FR_OK || fno.fname[0] == 0) {
        return -1; /* End of directory or error */
    }

    strncpy(entry->name, fno.fname, sizeof(entry->name) - 1);
    entry->name[sizeof(entry->name) - 1] = '\0';
    entry->type = (fno.fattrib & AM_DIR) ? FL_FILE_TYPE_DIR : FL_FILE_TYPE_REG;
    entry->size = (uint32_t)fno.fsize;

    return 0;
}

static int fatfs_closedir(void* dirp) {
    fatfs_dir_t* d = (fatfs_dir_t*)dirp;
    if (!d) {
        return -1;
    }

    FRESULT res = f_closedir(&d->dir);
    fatfs_free_dir(d);
    return (res == FR_OK) ? 0 : -1;
}

static int fatfs_unlink(const char* path) {
    FRESULT res = f_unlink(path);
    return (res == FR_OK) ? 0 : -1;
}

static int fatfs_rmdir(const char* path) {
    FRESULT res = f_unlink(path); /* FatFS uses f_unlink for both */
    return (res == FR_OK) ? 0 : -1;
}

static int fatfs_mkdir(const char* path, int mode) {
    (void)mode;
    FRESULT res = f_mkdir(path);
    return (res == FR_OK) ? 0 : -1;
}

static int fatfs_rename(const char* oldpath, const char* newpath) {
    FRESULT res = f_rename(oldpath, newpath);
    return (res == FR_OK) ? 0 : -1;
}

/* FatFS filesystem operations */
static const fl_fs_ops_t s_fatfs_ops = {
    .open = fatfs_open,
    .close = fatfs_close,
    .read = fatfs_read,
    .write = fatfs_write,
    .lseek = fatfs_lseek,
    .fsync = fatfs_fsync,
    .stat = fatfs_stat,
    .opendir = fatfs_opendir,
    .readdir = fatfs_readdir,
    .closedir = fatfs_closedir,
    .unlink = fatfs_unlink,
    .rmdir = fatfs_rmdir,
    .mkdir = fatfs_mkdir,
    .rename = fatfs_rename,
};

const fl_fs_ops_t* fl_file_get_fatfs_ops(void) {
    return &s_fatfs_ops;
}

/*
 * Implementation of fl_file_* wrapper functions
 * These call through the fs_ops interface
 */

int fl_file_open(fl_file_ctx_t* file_ctx, const char* path, const char* mode) {
    if (!file_ctx || !file_ctx->fs || !path || !mode) {
        return -1;
    }

    int flags = 0;

    /* Parse mode string */
    while (*mode) {
        switch (*mode) {
        case 'r':
            flags |= FL_O_RDONLY;
            break;
        case 'w':
            flags |= FL_O_WRONLY | FL_O_CREAT | FL_O_TRUNC;
            break;
        case 'a':
            flags |= FL_O_WRONLY | FL_O_CREAT | FL_O_APPEND;
            break;
        case '+':
            flags = (flags & ~(FL_O_RDONLY | FL_O_WRONLY)) | FL_O_RDWR;
            break;
        default:
            break;
        }
        mode++;
    }

    file_ctx->fp = file_ctx->fs->open(path, flags, 0644);
    if (!file_ctx->fp) {
        return -1;
    }

    strncpy(file_ctx->path, path, FL_FILE_PATH_MAX - 1);
    file_ctx->path[FL_FILE_PATH_MAX - 1] = '\0';
    file_ctx->offset = 0;

    return 0;
}

ssize_t fl_file_write(fl_file_ctx_t* file_ctx, const void* data, size_t len) {
    if (!file_ctx || !file_ctx->fs || !file_ctx->fp) {
        return -1;
    }
    ssize_t ret = file_ctx->fs->write(file_ctx->fp, data, len);
    if (ret > 0) {
        file_ctx->offset += ret;
    }
    return ret;
}

ssize_t fl_file_read(fl_file_ctx_t* file_ctx, void* buf, size_t len) {
    if (!file_ctx || !file_ctx->fs || !file_ctx->fp) {
        return -1;
    }
    ssize_t ret = file_ctx->fs->read(file_ctx->fp, buf, len);
    if (ret > 0) {
        file_ctx->offset += ret;
    }
    return ret;
}

int fl_file_close(fl_file_ctx_t* file_ctx) {
    if (!file_ctx || !file_ctx->fs || !file_ctx->fp) {
        return -1;
    }
    int ret = file_ctx->fs->close(file_ctx->fp);
    file_ctx->fp = NULL;
    file_ctx->offset = 0;
    return ret;
}

off_t fl_file_seek(fl_file_ctx_t* file_ctx, off_t offset, int whence) {
    if (!file_ctx || !file_ctx->fs || !file_ctx->fp) {
        return -1;
    }
    off_t ret = file_ctx->fs->lseek(file_ctx->fp, offset, whence);
    if (ret >= 0) {
        file_ctx->offset = ret;
    }
    return ret;
}

int fl_file_stat(fl_file_ctx_t* file_ctx, const char* path, fl_file_stat_t* st) {
    if (!file_ctx || !file_ctx->fs || !path || !st) {
        return -1;
    }
    return file_ctx->fs->stat(path, st);
}

int fl_file_list_cb(fl_file_ctx_t* file_ctx, const char* path, fl_file_list_cb_t callback, void* user_data) {
    if (!file_ctx || !file_ctx->fs || !path || !callback) {
        return -1;
    }

    void* dirp = file_ctx->fs->opendir(path);
    if (!dirp) {
        return -1;
    }

    int count = 0;
    fl_dirent_t entry;
    while (file_ctx->fs->readdir(dirp, &entry) == 0) {
        if (callback(&entry, user_data) != 0) {
            break;
        }
        count++;
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

int fl_file_rename(fl_file_ctx_t* file_ctx, const char* oldpath, const char* newpath) {
    if (!file_ctx || !file_ctx->fs || !oldpath || !newpath) {
        return -1;
    }
    return file_ctx->fs->rename(oldpath, newpath);
}

#endif /* FL_USE_FILE && FL_FILE_USE_FATFS */
