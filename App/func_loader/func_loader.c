/**
 * @file   func_loader.c
 * @brief  Function loader implementation - text-based command protocol
 *
 * Provides runtime code injection via text-based serial commands.
 * Uses argparse for command line parsing.
 *
 * Command Format:
 *   fl_loader --cmd <command> [options]\n
 *
 * Examples:
 *   fl_loader --cmd ping\n
 *   fl_loader --cmd upload --addr 0x0 --data "AABBCCDD" --checksum 0x1234\n
 *   fl_loader --cmd exec --entry 0x0 --args "arg1 arg2"\n
 *   fl_loader --cmd patch --comp 0 --orig 0x08001000 --target 0x20001000\n
 */

#include "func_loader.h"
#include "argparse/argparse.h"
#include "fpb_inject.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

static fl_platform_t g_platform;
static bool g_initialized = false;

static char g_line_buf[FL_LINE_BUFFER_SIZE];
static size_t g_line_pos = 0;

static uint8_t g_ram_code[FL_RAM_CODE_SIZE] __attribute__((aligned(4), section(".ram_code")));
static size_t g_ram_code_used = 0;

static const uint16_t g_crc16_table[256]
    = {0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7, 0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD,
       0xE1CE, 0xF1EF, 0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6, 0x9339, 0x8318, 0xB37B, 0xA35A,
       0xD3BD, 0xC39C, 0xF3FF, 0xE3DE, 0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485, 0xA56A, 0xB54B,
       0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D, 0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
       0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC, 0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861,
       0x2802, 0x3823, 0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B, 0x5AF5, 0x4AD4, 0x7AB7, 0x6A96,
       0x1A71, 0x0A50, 0x3A33, 0x2A12, 0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A, 0x6CA6, 0x7C87,
       0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41, 0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
       0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70, 0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A,
       0x9F59, 0x8F78, 0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F, 0x1080, 0x00A1, 0x30C2, 0x20E3,
       0x5004, 0x4025, 0x7046, 0x6067, 0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E, 0x02B1, 0x1290,
       0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256, 0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
       0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405, 0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E,
       0xC71D, 0xD73C, 0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634, 0xD94C, 0xC96D, 0xF90E, 0xE92F,
       0x99C8, 0x89E9, 0xB98A, 0xA9AB, 0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3, 0xCB7D, 0xDB5C,
       0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A, 0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
       0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9, 0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83,
       0x1CE0, 0x0CC1, 0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8, 0x6E17, 0x7E36, 0x4E55, 0x5E74,
       0x2E93, 0x3EB2, 0x0ED1, 0x1EF0};

uint16_t fl_crc16(const uint8_t* data, size_t len) {
    uint16_t crc = 0xFFFF;
    while (len--) {
        crc = (crc << 8) ^ g_crc16_table[(crc >> 8) ^ *data++];
    }
    return crc;
}

int fl_parse_hex(const char* str, uint32_t* value) {
    if (!str || !value) {
        return -1;
    }

    if (str[0] == '0' && (str[1] == 'x' || str[1] == 'X')) {
        str += 2;
    }

    *value = 0;
    while (*str) {
        char c = *str++;
        uint8_t digit;

        if (c >= '0' && c <= '9') {
            digit = c - '0';
        } else if (c >= 'a' && c <= 'f') {
            digit = c - 'a' + 10;
        } else if (c >= 'A' && c <= 'F') {
            digit = c - 'A' + 10;
        } else {
            return -1;
        }

        *value = (*value << 4) | digit;
    }

    return 0;
}

int fl_hex_to_bytes(const char* hex_str, uint8_t* out_buf, size_t max_len) {
    if (!hex_str || !out_buf) {
        return -1;
    }

    if (hex_str[0] == '0' && (hex_str[1] == 'x' || hex_str[1] == 'X')) {
        hex_str += 2;
    }

    size_t hex_len = strlen(hex_str);
    if (hex_len % 2 != 0) {
        return -1;
    }

    size_t byte_len = hex_len / 2;
    if (byte_len > max_len) {
        return -1;
    }

    for (size_t i = 0; i < byte_len; i++) {
        uint8_t high, low;
        char c;

        c = hex_str[i * 2];
        if (c >= '0' && c <= '9')
            high = c - '0';
        else if (c >= 'a' && c <= 'f')
            high = c - 'a' + 10;
        else if (c >= 'A' && c <= 'F')
            high = c - 'A' + 10;
        else
            return -1;

        c = hex_str[i * 2 + 1];
        if (c >= '0' && c <= '9')
            low = c - '0';
        else if (c >= 'a' && c <= 'f')
            low = c - 'a' + 10;
        else if (c >= 'A' && c <= 'F')
            low = c - 'A' + 10;
        else
            return -1;

        out_buf[i] = (high << 4) | low;
    }

    return (int)byte_len;
}

int fl_bytes_to_hex(const uint8_t* data, size_t len, char* out_str, size_t max_len) {
    static const char hex_chars[] = "0123456789ABCDEF";

    if (!data || !out_str || max_len < len * 2 + 1) {
        return -1;
    }

    for (size_t i = 0; i < len; i++) {
        out_str[i * 2] = hex_chars[(data[i] >> 4) & 0x0F];
        out_str[i * 2 + 1] = hex_chars[data[i] & 0x0F];
    }
    out_str[len * 2] = '\0';

    return (int)(len * 2);
}

static void serial_puts(const char* str) {
    if (g_platform.serial_write) {
        g_platform.serial_write((const uint8_t*)str, strlen(str));
    }
}

void fl_response(bool success, const char* fmt, ...) {
    char buf[256];
    va_list args;

    serial_puts(success ? "[OK] " : "[ERR] ");

    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    serial_puts(buf);

    serial_puts("\n");
}

void fl_print(const char* fmt, ...) {
    char buf[256];
    va_list args;

    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    serial_puts(buf);
    serial_puts("\n");
}

void fl_get_ram_code_info(uint32_t* addr, size_t* size, size_t* used) {
    if (addr)
        *addr = (uint32_t)g_ram_code;
    if (size)
        *size = FL_RAM_CODE_SIZE;
    if (used)
        *used = g_ram_code_used;
}

void fl_clear_ram_code(void) {
    memset(g_ram_code, 0, FL_RAM_CODE_SIZE);
    g_ram_code_used = 0;
}

int fl_write_ram_code(uint32_t offset, const uint8_t* data, size_t len) {
    if (offset + len > FL_RAM_CODE_SIZE) {
        return -1;
    }

    memcpy(g_ram_code + offset, data, len);

    if (offset + len > g_ram_code_used) {
        g_ram_code_used = offset + len;
    }

    return 0;
}

int fl_exec_ram_code(uint32_t entry_offset, int argc, const char** argv) {
    if (entry_offset >= g_ram_code_used) {
        return -1;
    }

    uint32_t entry_addr = (uint32_t)(g_ram_code + entry_offset) | 1;

    typedef int (*ram_func_t)(int, const char**);
    ram_func_t func = (ram_func_t)entry_addr;

    __asm volatile("dsb");
    __asm volatile("isb");

    return func(argc, argv);
}

static void cmd_ping(void) {
    fl_response(true, "PONG");
}

static void cmd_info(void) {
    uint32_t addr;
    size_t size, used;

    fl_get_ram_code_info(&addr, &size, &used);

    fl_print("FPBInject v1.0");
    fl_print("RAM Code Buffer: 0x%08lX", (unsigned long)addr);
    fl_print("RAM Code Size: %u bytes", (unsigned)size);
    fl_print("RAM Code Used: %u bytes", (unsigned)used);
    fl_print("FPB Comparators: %u", (unsigned)fpb_get_state()->num_code_comp);
    fl_response(true, "Info complete");
}

static void cmd_upload(uint32_t addr, const char* data_hex, uint32_t checksum, bool verify_checksum) {
    static uint8_t data_buf[FL_RAM_CODE_SIZE];

    int data_len = fl_hex_to_bytes(data_hex, data_buf, sizeof(data_buf));
    if (data_len < 0) {
        fl_response(false, "Invalid hex data format");
        return;
    }

    if (verify_checksum) {
        uint16_t calc_crc = fl_crc16(data_buf, data_len);
        if (calc_crc != (uint16_t)checksum) {
            fl_response(false, "Checksum mismatch: expected 0x%04X, got 0x%04X", (unsigned)checksum,
                        (unsigned)calc_crc);
            return;
        }
    }

    if (fl_write_ram_code(addr, data_buf, data_len) != 0) {
        fl_response(false, "Buffer overflow at offset 0x%lX", (unsigned long)addr);
        return;
    }

    fl_response(true, "Uploaded %d bytes to offset 0x%lX", data_len, (unsigned long)addr);
}

static void cmd_clear(void) {
    fl_clear_ram_code();
    fl_response(true, "RAM code buffer cleared");
}

static void cmd_exec(uint32_t entry, const char* args_str) {
    static char args_buf[256];
    static char* argv[FL_MAX_ARGC];
    int argc = 0;

    if (args_str && *args_str) {
        strncpy(args_buf, args_str, sizeof(args_buf) - 1);
        args_buf[sizeof(args_buf) - 1] = '\0';

        char* p = args_buf;
        bool in_quote = false;
        bool in_arg = false;

        while (*p && argc < FL_MAX_ARGC) {
            if (*p == '"') {
                in_quote = !in_quote;
                memmove(p, p + 1, strlen(p));
                continue;
            }

            if (!in_quote && (*p == ' ' || *p == '\t')) {
                if (in_arg) {
                    *p = '\0';
                    in_arg = false;
                }
            } else if (!in_arg) {
                argv[argc++] = p;
                in_arg = true;
            }
            p++;
        }
    }

    fl_print("Executing at entry offset 0x%lX with %d args", (unsigned long)entry, argc);

    int ret = fl_exec_ram_code(entry, argc, (const char**)argv);
    fl_response(true, "Execution returned %d (0x%08lX)", ret, (unsigned long)ret);
}

static void cmd_call(uint32_t addr, const char* args_str) {
    static char args_buf[256];
    static char* argv[FL_MAX_ARGC];
    int argc = 0;

    if (args_str && *args_str) {
        strncpy(args_buf, args_str, sizeof(args_buf) - 1);
        args_buf[sizeof(args_buf) - 1] = '\0';

        char* p = args_buf;
        bool in_quote = false;
        bool in_arg = false;

        while (*p && argc < FL_MAX_ARGC) {
            if (*p == '"') {
                in_quote = !in_quote;
                memmove(p, p + 1, strlen(p));
                continue;
            }

            if (!in_quote && (*p == ' ' || *p == '\t')) {
                if (in_arg) {
                    *p = '\0';
                    in_arg = false;
                }
            } else if (!in_arg) {
                argv[argc++] = p;
                in_arg = true;
            }
            p++;
        }
    }

    fl_print("Calling 0x%08lX with %d args", (unsigned long)addr, argc);

    typedef int (*func_t)(int, const char**);
    func_t func = (func_t)(addr | 1);

    int ret = func(argc, (const char**)argv);
    fl_response(true, "Call returned %d (0x%08lX)", ret, (unsigned long)ret);
}

static void cmd_read(uint32_t addr, uint32_t len) {
    static char hex_buf[1024];

    if (len > sizeof(hex_buf) / 2) {
        len = sizeof(hex_buf) / 2;
    }

    fl_bytes_to_hex((const uint8_t*)addr, len, hex_buf, sizeof(hex_buf));
    fl_print("Data: %s", hex_buf);
    fl_response(true, "Read %lu bytes from 0x%08lX", (unsigned long)len, (unsigned long)addr);
}

static void cmd_write(uint32_t addr, const char* data_hex, uint32_t checksum, bool verify_checksum) {
    static uint8_t data_buf[512];

    int data_len = fl_hex_to_bytes(data_hex, data_buf, sizeof(data_buf));
    if (data_len < 0) {
        fl_response(false, "Invalid hex data format");
        return;
    }

    if (verify_checksum) {
        uint16_t calc_crc = fl_crc16(data_buf, data_len);
        if (calc_crc != (uint16_t)checksum) {
            fl_response(false, "Checksum mismatch");
            return;
        }
    }

    memcpy((void*)addr, data_buf, data_len);

    fl_response(true, "Wrote %d bytes to 0x%08lX", data_len, (unsigned long)addr);
}

static void cmd_patch(uint32_t comp, uint32_t orig, uint32_t target) {
    if (comp >= fpb_get_state()->num_code_comp) {
        fl_response(false, "Invalid comparator %lu, max is %u", (unsigned long)comp,
                    fpb_get_state()->num_code_comp - 1);
        return;
    }

    int ret = fpb_set_patch(comp, orig, target);
    if (ret != 0) {
        fl_response(false, "fpb_set_patch failed with %d", ret);
        return;
    }

    fl_response(true, "Patch %lu: 0x%08lX -> 0x%08lX", (unsigned long)comp, (unsigned long)orig, (unsigned long)target);
}

static void cmd_unpatch(uint32_t comp) {
    if (comp >= fpb_get_state()->num_code_comp) {
        fl_response(false, "Invalid comparator %lu", (unsigned long)comp);
        return;
    }

    fpb_clear_patch(comp);
    fl_response(true, "Cleared patch %lu", (unsigned long)comp);
}

static void process_command(char* line) {
    static char* argv[FL_MAX_ARGC];
    int argc = 0;

    char* p = line;
    bool in_quote = false;
    bool in_arg = false;

    while (*p && argc < FL_MAX_ARGC) {
        if (*p == '"') {
            in_quote = !in_quote;
            if (!in_arg) {
                argv[argc++] = p + 1;
                in_arg = true;
            }
            memmove(p, p + 1, strlen(p));
            continue;
        }

        if (!in_quote && (*p == ' ' || *p == '\t')) {
            if (in_arg) {
                *p = '\0';
                in_arg = false;
            }
        } else if (!in_arg) {
            argv[argc++] = p;
            in_arg = true;
        }
        p++;
    }

    if (argc == 0) {
        return;
    }

    const char* cmd = NULL;
    const char* data = NULL;
    const char* args = NULL;
    int addr = 0;
    int checksum = -1;
    int len = 64;
    int comp = 0;
    int orig = 0;
    int target = 0;
    int entry = 0;

    struct argparse_option options[] = {
        OPT_GROUP("Commands"),
        OPT_STRING('c', "cmd", &cmd, "Command: ping/info/upload/clear/exec/call/read/write/patch/unpatch", NULL, 0, 0),
        OPT_GROUP("Upload/Write options"),
        OPT_INTEGER('a', "addr", &addr, "Address or offset (hex with 0x)", NULL, 0, 0),
        OPT_STRING('d', "data", &data, "Hex data string", NULL, 0, 0),
        OPT_INTEGER('s', "checksum", &checksum, "CRC-16 checksum (hex with 0x)", NULL, 0, 0),
        OPT_GROUP("Exec/Call options"),
        OPT_INTEGER('e', "entry", &entry, "Entry point offset", NULL, 0, 0),
        OPT_STRING(0, "args", &args, "Arguments string", NULL, 0, 0),
        OPT_GROUP("Read options"),
        OPT_INTEGER('l', "len", &len, "Read length", NULL, 0, 0),
        OPT_GROUP("Patch options"),
        OPT_INTEGER(0, "comp", &comp, "Comparator ID", NULL, 0, 0),
        OPT_INTEGER(0, "orig", &orig, "Original address", NULL, 0, 0),
        OPT_INTEGER(0, "target", &target, "Target/patch address", NULL, 0, 0),
        OPT_END(),
    };

    struct argparse argparse;
    static const char* const usages[] = {
        "fl_loader --cmd <command> [options]",
        NULL,
    };

    argparse_init(&argparse, options, usages, ARGPARSE_IGNORE_UNKNOWN_ARGS);
    argparse_describe(&argparse, "FPBInject Function Loader", NULL);
    argparse_parse(&argparse, argc, (const char**)argv);

    if (!cmd) {
        fl_response(false, "Missing --cmd parameter");
        return;
    }

    if (strcmp(cmd, "ping") == 0) {
        cmd_ping();
    } else if (strcmp(cmd, "info") == 0) {
        cmd_info();
    } else if (strcmp(cmd, "upload") == 0) {
        if (!data) {
            fl_response(false, "Missing --data parameter");
            return;
        }
        cmd_upload(addr, data, checksum, checksum >= 0);
    } else if (strcmp(cmd, "clear") == 0) {
        cmd_clear();
    } else if (strcmp(cmd, "exec") == 0) {
        cmd_exec(entry, args);
    } else if (strcmp(cmd, "call") == 0) {
        if (addr == 0) {
            fl_response(false, "Missing --addr parameter");
            return;
        }
        cmd_call(addr, args);
    } else if (strcmp(cmd, "read") == 0) {
        if (addr == 0) {
            fl_response(false, "Missing --addr parameter");
            return;
        }
        cmd_read(addr, len);
    } else if (strcmp(cmd, "write") == 0) {
        if (addr == 0 || !data) {
            fl_response(false, "Missing --addr or --data parameter");
            return;
        }
        cmd_write(addr, data, checksum, checksum >= 0);
    } else if (strcmp(cmd, "patch") == 0) {
        if (orig == 0 || target == 0) {
            fl_response(false, "Missing --orig or --target parameter");
            return;
        }
        cmd_patch(comp, orig, target);
    } else if (strcmp(cmd, "unpatch") == 0) {
        cmd_unpatch(comp);
    } else if (strcmp(cmd, "help") == 0) {
        fl_print("Commands:");
        fl_print("  ping                              - Test connection");
        fl_print("  info                              - Get device info");
        fl_print("  upload -a <offset> -d <hex> [-s <crc>]");
        fl_print("                                    - Upload data to RAM buffer");
        fl_print("  clear                             - Clear RAM buffer");
        fl_print("  exec [-e <entry>] [--args \"...\"] - Execute RAM code");
        fl_print("  call -a <addr> [--args \"...\"]    - Call function");
        fl_print("  read -a <addr> [-l <len>]         - Read memory");
        fl_print("  write -a <addr> -d <hex> [-s <crc>]");
        fl_print("                                    - Write memory");
        fl_print("  patch --comp <n> --orig <addr> --target <addr>");
        fl_print("                                    - Set FPB patch");
        fl_print("  unpatch --comp <n>                - Clear FPB patch");
        fl_response(true, "Help complete");
    } else {
        fl_response(false, "Unknown command: %s", cmd);
    }
}

int fl_init(const fl_platform_t* platform) {
    if (!platform) {
        return -1;
    }

    if (!platform->serial_read || !platform->serial_write || !platform->serial_available) {
        return -1;
    }

    memcpy(&g_platform, platform, sizeof(fl_platform_t));
    g_initialized = true;

    g_line_pos = 0;
    g_ram_code_used = 0;

    fpb_init();

    return 0;
}

void fl_process(void) {
    if (!g_initialized) {
        return;
    }

    while (g_platform.serial_available() > 0) {
        uint8_t byte;
        if (g_platform.serial_read(&byte, 1) != 1) {
            break;
        }

        if (byte == '\n' || byte == '\r') {
            if (g_line_pos > 0) {
                g_line_buf[g_line_pos] = '\0';
                process_command(g_line_buf);
                g_line_pos = 0;
            }
            continue;
        }

        if (byte == '\b' || byte == 0x7F) {
            if (g_line_pos > 0) {
                g_line_pos--;
            }
            continue;
        }

        if (g_line_pos < FL_LINE_BUFFER_SIZE - 1) {
            g_line_buf[g_line_pos++] = byte;
        }
    }
}
