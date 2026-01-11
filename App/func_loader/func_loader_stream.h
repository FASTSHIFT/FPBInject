/**
 * @file   func_loader_stream.h
 * @brief  Serial stream processing for func_loader
 */

#ifndef __FUNC_LOADER_STREAM_H
#define __FUNC_LOADER_STREAM_H

#ifdef __cplusplus
extern "C" {
#endif

#include "func_loader.h"

#ifndef FL_LINE_SIZE
#define FL_LINE_SIZE 512
#endif

#ifndef FL_MAX_ARGC
#define FL_MAX_ARGC 16
#endif

/* Serial callbacks */
typedef int (*fl_serial_read_cb_t)(uint8_t* buf, size_t len);
typedef int (*fl_serial_write_cb_t)(const uint8_t* buf, size_t len);
typedef int (*fl_serial_available_cb_t)(void);

typedef struct {
    fl_serial_read_cb_t read_cb;
    fl_serial_write_cb_t write_cb;
    fl_serial_available_cb_t available_cb;
} fl_serial_t;

typedef struct {
    fl_context_t* ctx;
    const fl_serial_t* serial;
    char* line_buf;
    size_t line_size;
    size_t line_pos;
} fl_stream_t;

/**
 * @brief Initialize stream processor
 */
void fl_stream_init(fl_stream_t* s, fl_context_t* ctx, const fl_serial_t* serial, char* line_buf, size_t line_size);

/**
 * @brief Process incoming serial data
 */
void fl_stream_process(fl_stream_t* s);

/**
 * @brief Parse line and execute
 */
int fl_stream_exec_line(fl_stream_t* s, char* line);

#ifdef __cplusplus
}
#endif

#endif /* __FUNC_LOADER_STREAM_H */
