/**
 * @file   func_loader.h
 * @brief  Function loader module - text-based command protocol
 *
 * This module provides:
 * - Text-based serial command interface (like CLI)
 * - Command line parsing using argparse
 * - Dynamic RAM code allocation and execution
 * - Platform-independent design
 *
 * Protocol Format:
 *   Command line terminated by '\n'
 *   Example: fl_loader --cmd upload --addr 0x20001000 --data "AABBCCDD" --checksum 0x1234\n
 *
 * Response Format:
 *   [OK] or [ERR] followed by message, terminated by '\n'
 *   Example: [OK] Upload 16 bytes to 0x20001000\n
 *            [ERR] Checksum mismatch\n
 */

#ifndef __FUNC_LOADER_H
#define __FUNC_LOADER_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifndef FL_MAX_CMD_LEN
#define FL_MAX_CMD_LEN 1024
#endif

#ifndef FL_MAX_ARGC
#define FL_MAX_ARGC 32
#endif

#ifndef FL_RAM_CODE_SIZE
#define FL_RAM_CODE_SIZE 4096
#endif

#ifndef FL_LINE_BUFFER_SIZE
#define FL_LINE_BUFFER_SIZE 2048
#endif

typedef enum {
    FL_CMD_NONE = 0,
    FL_CMD_PING,
    FL_CMD_INFO,
    FL_CMD_UPLOAD,
    FL_CMD_CLEAR,
    FL_CMD_EXEC,
    FL_CMD_CALL,
    FL_CMD_READ,
    FL_CMD_WRITE,
    FL_CMD_PATCH,
    FL_CMD_UNPATCH,
    FL_CMD_HELP,
} fl_cmd_type_t;

typedef enum {
    FL_ERR_NONE = 0,
    FL_ERR_CHECKSUM,
    FL_ERR_PARAM,
    FL_ERR_OVERFLOW,
    FL_ERR_EXEC,
    FL_ERR_CMD,
    FL_ERR_ADDR,
    FL_ERR_DATA,
} fl_error_t;

/**
 * @brief Platform callbacks structure
 */
typedef struct {
    int (*serial_read)(uint8_t* buf, size_t len);
    int (*serial_write)(const uint8_t* buf, size_t len);
    int (*serial_available)(void);
    void* (*malloc)(size_t size);
    void (*free)(void* ptr);
    uint32_t (*get_tick_ms)(void);
} fl_platform_t;

/**
 * @brief Initialize func_loader
 * @param platform Platform callbacks
 * @return 0 on success, -1 on failure
 */
int fl_init(const fl_platform_t* platform);

/**
 * @brief Process incoming serial data
 */
void fl_process(void);

/**
 * @brief Send response to host
 * @param success true for [OK], false for [ERR]
 * @param fmt printf-style format string
 */
void fl_response(bool success, const char* fmt, ...);

/**
 * @brief Print message to host
 * @param fmt printf-style format string
 */
void fl_print(const char* fmt, ...);

/**
 * @brief Calculate CRC-16-CCITT checksum
 */
uint16_t fl_crc16(const uint8_t* data, size_t len);

/**
 * @brief Parse hex string to bytes
 */
int fl_hex_to_bytes(const char* hex_str, uint8_t* out_buf, size_t max_len);

/**
 * @brief Convert bytes to hex string
 */
int fl_bytes_to_hex(const uint8_t* data, size_t len, char* out_str, size_t max_len);

/**
 * @brief Parse hex string to uint32
 */
int fl_parse_hex(const char* str, uint32_t* value);

/**
 * @brief Get RAM code buffer info
 */
void fl_get_ram_code_info(uint32_t* addr, size_t* size, size_t* used);

/**
 * @brief Clear RAM code buffer
 */
void fl_clear_ram_code(void);

/**
 * @brief Write data to RAM code buffer at offset
 */
int fl_write_ram_code(uint32_t offset, const uint8_t* data, size_t len);

/**
 * @brief Execute code in RAM buffer
 */
int fl_exec_ram_code(uint32_t entry_offset, int argc, const char** argv);

/**
 * @brief Main entry point for func_loader application
 */
void func_loader_run(void);

#ifdef __cplusplus
}
#endif

#endif /* __FUNC_LOADER_H */
