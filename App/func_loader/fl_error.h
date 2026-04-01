/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 */

/**
 * @file   fl_error.h
 * @brief  Error codes for func_loader
 */

#ifndef FL_ERROR_H
#define FL_ERROR_H

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Error codes for fl_exec_cmd and command handlers
 */
typedef enum {
    FL_OK = 0,             /* Command executed successfully */
    FL_ERR_ARGS = -1,      /* Missing or invalid required arguments */
    FL_ERR_CRC = -2,       /* CRC verification failed */
    FL_ERR_PARSE = -3,     /* Argument parsing failed */
    FL_ERR_IO = -4,        /* I/O operation failed (file read/write/seek/close) */
    FL_ERR_ALLOC = -5,     /* Memory allocation failed */
    FL_ERR_STATE = -6,     /* Invalid state (no file open, no alloc, not initialized) */
    FL_ERR_RANGE = -7,     /* Address/comp/length out of valid range */
    FL_ERR_ENCODE = -8,    /* Base64 encode/decode failed */
    FL_ERR_HW = -9,        /* Hardware operation failed (FPB/debugmon) */
    FL_ERR_DISABLED = -10, /* Feature disabled at compile time */
    FL_ERR_UNKNOWN = -11,  /* Unknown command */
} fl_error_t;

#ifdef __cplusplus
}
#endif

#endif /* FL_ERROR_H */
