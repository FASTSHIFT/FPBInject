/*
 * MIT License
 * Copyright (c) 2024 _VIFEXTech
 *
 * Mock FatFS implementation using host filesystem
 */

/* Include system headers BEFORE mock_fatfs.h to avoid DIR conflict */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <dirent.h>
#include <unistd.h>
#include <time.h>

/* Save system DIR type */
typedef DIR SYS_DIR;

/* Now include mock header which redefines DIR */
#include "mock_fatfs.h"

/* ============================================================================
 * Mock State
 * ============================================================================ */

static struct {
    int fail_open;
    int fail_read;
    int fail_write;
    int fail_stat;
    int open_count;
    int close_count;
    int read_count;
    int write_count;
} mock_state;

void mock_fatfs_reset(void) {
    memset(&mock_state, 0, sizeof(mock_state));
}

void mock_fatfs_set_fail_open(int fail) {
    mock_state.fail_open = fail;
}

void mock_fatfs_set_fail_read(int fail) {
    mock_state.fail_read = fail;
}

void mock_fatfs_set_fail_write(int fail) {
    mock_state.fail_write = fail;
}

void mock_fatfs_set_fail_stat(int fail) {
    mock_state.fail_stat = fail;
}

int mock_fatfs_get_open_count(void) {
    return mock_state.open_count;
}

int mock_fatfs_get_close_count(void) {
    return mock_state.close_count;
}

int mock_fatfs_get_read_count(void) {
    return mock_state.read_count;
}

int mock_fatfs_get_write_count(void) {
    return mock_state.write_count;
}

/* ============================================================================
 * Mock FatFS Implementation
 * ============================================================================ */

FRESULT f_open(FIL* fp, const TCHAR* path, BYTE mode) {
    if (!fp || !path) {
        return FR_INVALID_PARAMETER;
    }

    if (mock_state.fail_open) {
        return FR_DISK_ERR;
    }

    mock_state.open_count++;

    /* Convert FatFS mode to fopen mode */
    const char* fmode;
    if ((mode & FA_OPEN_APPEND) == FA_OPEN_APPEND) {
        fmode = (mode & FA_READ) ? "a+" : "a";
    } else if (mode & FA_CREATE_ALWAYS) {
        fmode = (mode & FA_READ) ? "w+" : "w";
    } else if (mode & FA_OPEN_ALWAYS) {
        fmode = (mode & FA_READ) ? "r+" : "w";
    } else if (mode & FA_WRITE) {
        fmode = "r+";
    } else {
        fmode = "r";
    }

    FILE* file = fopen(path, fmode);
    if (!file) {
        /* Try create if FA_OPEN_ALWAYS or FA_CREATE_NEW */
        if ((mode & FA_OPEN_ALWAYS) || (mode & FA_CREATE_NEW)) {
            file = fopen(path, "w+");
        }
        if (!file) {
            return FR_NO_FILE;
        }
    }

    fp->mock_is_open = 1;
    fp->fptr = 0;
    fp->flag = mode;

    /* Get file size */
    fseek(file, 0, SEEK_END);
    fp->obj_size = ftell(file);
    fseek(file, 0, SEEK_SET);

    /* Store FILE* pointer */
    fp->mock_fp = file;

    return FR_OK;
}

FRESULT f_close(FIL* fp) {
    if (!fp || !fp->mock_is_open) {
        return FR_INVALID_OBJECT;
    }

    mock_state.close_count++;

    FILE* file = (FILE*)fp->mock_fp;
    fclose(file);

    fp->mock_is_open = 0;
    fp->mock_fp = NULL;

    return FR_OK;
}

FRESULT f_read(FIL* fp, void* buff, UINT btr, UINT* br) {
    if (!fp || !fp->mock_is_open || !buff || !br) {
        return FR_INVALID_PARAMETER;
    }

    if (mock_state.fail_read) {
        *br = 0;
        return FR_DISK_ERR;
    }

    mock_state.read_count++;

    FILE* file = (FILE*)fp->mock_fp;
    *br = (UINT)fread(buff, 1, btr, file);
    fp->fptr += *br;

    return FR_OK;
}

FRESULT f_write(FIL* fp, const void* buff, UINT btw, UINT* bw) {
    if (!fp || !fp->mock_is_open || !buff || !bw) {
        return FR_INVALID_PARAMETER;
    }

    if (mock_state.fail_write) {
        *bw = 0;
        return FR_DISK_ERR;
    }

    mock_state.write_count++;

    FILE* file = (FILE*)fp->mock_fp;
    *bw = (UINT)fwrite(buff, 1, btw, file);
    fp->fptr += *bw;

    if (fp->fptr > fp->obj_size) {
        fp->obj_size = fp->fptr;
    }

    return FR_OK;
}

FRESULT f_lseek(FIL* fp, FSIZE_t ofs) {
    if (!fp || !fp->mock_is_open) {
        return FR_INVALID_OBJECT;
    }

    FILE* file = (FILE*)fp->mock_fp;
    if (fseek(file, (long)ofs, SEEK_SET) != 0) {
        return FR_DISK_ERR;
    }

    fp->fptr = ofs;
    return FR_OK;
}

FRESULT f_sync(FIL* fp) {
    if (!fp || !fp->mock_is_open) {
        return FR_INVALID_OBJECT;
    }

    FILE* file = (FILE*)fp->mock_fp;
    fflush(file);

    return FR_OK;
}

FRESULT f_stat(const TCHAR* path, FILINFO* fno) {
    if (!path || !fno) {
        return FR_INVALID_PARAMETER;
    }

    if (mock_state.fail_stat) {
        return FR_DISK_ERR;
    }

    struct stat st;
    if (stat(path, &st) != 0) {
        return FR_NO_FILE;
    }

    fno->fsize = st.st_size;
    fno->fattrib = S_ISDIR(st.st_mode) ? AM_DIR : 0;

    /* Convert time to FatFS format */
    struct tm* tm = localtime(&st.st_mtime);
    if (tm) {
        fno->fdate = ((tm->tm_year - 80) << 9) | ((tm->tm_mon + 1) << 5) | tm->tm_mday;
        fno->ftime = (tm->tm_hour << 11) | (tm->tm_min << 5) | (tm->tm_sec / 2);
    } else {
        fno->fdate = 0;
        fno->ftime = 0;
    }

    /* Extract filename */
    const char* name = strrchr(path, '/');
    if (name) {
        name++;
    } else {
        name = path;
    }
    strncpy(fno->fname, name, sizeof(fno->fname) - 1);
    fno->fname[sizeof(fno->fname) - 1] = '\0';

    return FR_OK;
}

FRESULT f_opendir(FATFS_DIR* dp, const TCHAR* path) {
    if (!dp || !path) {
        return FR_INVALID_PARAMETER;
    }

    SYS_DIR* dir = opendir(path);
    if (!dir) {
        return FR_NO_PATH;
    }

    dp->mock_dir = dir;
    dp->mock_is_open = 1;

    return FR_OK;
}

FRESULT f_closedir(FATFS_DIR* dp) {
    if (!dp || !dp->mock_is_open) {
        return FR_INVALID_OBJECT;
    }

    closedir((SYS_DIR*)dp->mock_dir);
    dp->mock_is_open = 0;
    dp->mock_dir = NULL;

    return FR_OK;
}

FRESULT f_readdir(FATFS_DIR* dp, FILINFO* fno) {
    if (!dp || !dp->mock_is_open) {
        return FR_INVALID_OBJECT;
    }

    /* NULL fno means rewind */
    if (!fno) {
        rewinddir((SYS_DIR*)dp->mock_dir);
        return FR_OK;
    }

    struct dirent* entry = readdir((SYS_DIR*)dp->mock_dir);
    if (!entry) {
        fno->fname[0] = '\0';
        return FR_OK;
    }

    strncpy(fno->fname, entry->d_name, sizeof(fno->fname) - 1);
    fno->fname[sizeof(fno->fname) - 1] = '\0';
    fno->fattrib = (entry->d_type == DT_DIR) ? AM_DIR : 0;
    fno->fsize = 0; /* Would need stat to get actual size */

    return FR_OK;
}

FRESULT f_mkdir(const TCHAR* path) {
    if (!path) {
        return FR_INVALID_PARAMETER;
    }

    if (mkdir(path, 0755) != 0) {
        return FR_DENIED;
    }

    return FR_OK;
}

FRESULT f_unlink(const TCHAR* path) {
    if (!path) {
        return FR_INVALID_PARAMETER;
    }

    struct stat st;
    if (stat(path, &st) != 0) {
        return FR_NO_FILE;
    }

    if (S_ISDIR(st.st_mode)) {
        if (rmdir(path) != 0) {
            return FR_DENIED;
        }
    } else {
        if (unlink(path) != 0) {
            return FR_DENIED;
        }
    }

    return FR_OK;
}

FRESULT f_rename(const TCHAR* path_old, const TCHAR* path_new) {
    if (!path_old || !path_new) {
        return FR_INVALID_PARAMETER;
    }

    if (rename(path_old, path_new) != 0) {
        return FR_DENIED;
    }

    return FR_OK;
}
