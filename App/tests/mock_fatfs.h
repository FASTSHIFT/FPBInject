/*
 * MIT License
 * Copyright (c) 2024 _VIFEXTech
 *
 * Mock FatFS API for unit testing func_loader_file_fatfs.c
 */

#ifndef __MOCK_FATFS_H
#define __MOCK_FATFS_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================================
 * FatFS Type Definitions (minimal subset for testing)
 * ============================================================================ */

typedef unsigned int UINT;
typedef unsigned char BYTE;
typedef uint16_t WORD;
typedef uint32_t DWORD;
typedef DWORD FSIZE_t;
typedef char TCHAR;

/* File function return code */
typedef enum {
    FR_OK = 0,
    FR_DISK_ERR,
    FR_INT_ERR,
    FR_NOT_READY,
    FR_NO_FILE,
    FR_NO_PATH,
    FR_INVALID_NAME,
    FR_DENIED,
    FR_EXIST,
    FR_INVALID_OBJECT,
    FR_WRITE_PROTECTED,
    FR_INVALID_DRIVE,
    FR_NOT_ENABLED,
    FR_NO_FILESYSTEM,
    FR_MKFS_ABORTED,
    FR_TIMEOUT,
    FR_LOCKED,
    FR_NOT_ENOUGH_CORE,
    FR_TOO_MANY_OPEN_FILES,
    FR_INVALID_PARAMETER
} FRESULT;

/* File access mode flags */
#define FA_READ 0x01
#define FA_WRITE 0x02
#define FA_OPEN_EXISTING 0x00
#define FA_CREATE_NEW 0x04
#define FA_CREATE_ALWAYS 0x08
#define FA_OPEN_ALWAYS 0x10
#define FA_OPEN_APPEND 0x30

/* File attribute bits */
#define AM_RDO 0x01
#define AM_HID 0x02
#define AM_SYS 0x04
#define AM_DIR 0x10
#define AM_ARC 0x20

/* File object structure (simplified for mock) */
typedef struct {
    BYTE flag;
    FSIZE_t fptr;
    FSIZE_t obj_size;
    /* Mock internal state */
    void* mock_fp; /* FILE* pointer */
    BYTE mock_is_open;
} FIL;

/* Directory object structure (simplified for mock) */
typedef struct {
    /* Mock internal state */
    void* mock_dir;
    BYTE mock_is_open;
} FATFS_DIR;

/* File information structure */
typedef struct {
    FSIZE_t fsize;
    WORD fdate;
    WORD ftime;
    BYTE fattrib;
    TCHAR fname[256];
} FILINFO;

/* Alias for FatFS compatibility - define DIR as FATFS_DIR */
#define DIR FATFS_DIR

/* Macros for file object */
#define f_eof(fp) ((int)((fp)->fptr == (fp)->obj_size))
#define f_error(fp) (0)
#define f_tell(fp) ((fp)->fptr)
#define f_size(fp) ((fp)->obj_size)

/* ============================================================================
 * Mock FatFS API Functions
 * ============================================================================ */

FRESULT f_open(FIL* fp, const TCHAR* path, BYTE mode);
FRESULT f_close(FIL* fp);
FRESULT f_read(FIL* fp, void* buff, UINT btr, UINT* br);
FRESULT f_write(FIL* fp, const void* buff, UINT btw, UINT* bw);
FRESULT f_lseek(FIL* fp, FSIZE_t ofs);
FRESULT f_sync(FIL* fp);
FRESULT f_opendir(FATFS_DIR* dp, const TCHAR* path);
FRESULT f_closedir(FATFS_DIR* dp);
FRESULT f_readdir(FATFS_DIR* dp, FILINFO* fno);
FRESULT f_mkdir(const TCHAR* path);
FRESULT f_unlink(const TCHAR* path);
FRESULT f_rename(const TCHAR* path_old, const TCHAR* path_new);
FRESULT f_stat(const TCHAR* path, FILINFO* fno);

/* ============================================================================
 * Mock Control Functions
 * ============================================================================ */

/* Reset mock state */
void mock_fatfs_reset(void);

/* Configure mock behavior */
void mock_fatfs_set_fail_open(int fail);
void mock_fatfs_set_fail_read(int fail);
void mock_fatfs_set_fail_write(int fail);
void mock_fatfs_set_fail_stat(int fail);

/* Get mock statistics */
int mock_fatfs_get_open_count(void);
int mock_fatfs_get_close_count(void);
int mock_fatfs_get_read_count(void);
int mock_fatfs_get_write_count(void);

#ifdef __cplusplus
}
#endif

#endif /* __MOCK_FATFS_H */
