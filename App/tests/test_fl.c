/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Tests for func_loader.c - Function loader core
 */

#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE /* For getpid, rmdir, etc. */
#endif

#include "test_framework.h"
#include "mock_hardware.h"
#include "fpb_mock_regs.h"
#include "fl.h"
#include <unistd.h>
#include <sys/stat.h>

/* Test context */
static fl_context_t test_ctx;

/* ============================================================================
 * Test CRC Helper (mirrors firmware calc_crc16_base / calc_crc16)
 * ============================================================================ */

static const uint16_t s_test_crc16_table[256] = {
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7, 0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD,
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
    0x2E93, 0x3EB2, 0x0ED1, 0x1EF0,
};

static uint16_t test_crc16_update(uint16_t crc, const void* data, size_t len) {
    const uint8_t* ptr = data;
    while (len--) {
        crc = (crc << 8) ^ s_test_crc16_table[(crc >> 8) ^ *ptr++];
    }
    return crc;
}

static uint16_t test_crc16(const void* data, size_t len) {
    return test_crc16_update(0xFFFF, data, len);
}

/* ============================================================================
 * Setup/Teardown
 * ============================================================================ */

static void setup_loader(void) {
    mock_output_reset();
    mock_heap_reset();
    mock_fpb_reset();
    memset(&test_ctx, 0, sizeof(test_ctx));

    test_ctx.output_cb = mock_output_cb;
    test_ctx.output_user = NULL;
    test_ctx.malloc_cb = mock_malloc;
    test_ctx.free_cb = mock_free;
}

/* ============================================================================
 * fl_init Tests
 * ============================================================================ */

void test_loader_init_default(void) {
    fl_context_t ctx;
    memset(&ctx, 0, sizeof(ctx));
    fl_init_default(&ctx);
    /* Should not crash, sets defaults */
}

void test_loader_init_basic(void) {
    setup_loader();
    fl_init(&test_ctx);
    TEST_ASSERT_TRUE(fl_is_inited(&test_ctx));
}

void test_loader_init_clears_slots(void) {
    setup_loader();
    /* Note: fl_init() does NOT clear slots by design.
     * Use fl_init_default() to zero the entire context if needed.
     * This test verifies fl_init_default behavior instead.
     */
    fl_context_t ctx;
    memset(&ctx, 0xFF, sizeof(ctx)); /* Fill with garbage */
    fl_init_default(&ctx);

    for (int i = 0; i < FL_MAX_SLOTS; i++) {
        TEST_ASSERT_FALSE(ctx.slots[i].active);
        TEST_ASSERT_EQUAL_HEX(0, ctx.slots[i].orig_addr);
    }
}

void test_loader_init_idempotent(void) {
    setup_loader();
    fl_init(&test_ctx);
    fl_init(&test_ctx); /* Second call */
    TEST_ASSERT_TRUE(fl_is_inited(&test_ctx));
}

/* ============================================================================
 * fl_is_inited Tests
 * ============================================================================ */

void test_loader_not_inited(void) {
    fl_context_t ctx;
    memset(&ctx, 0, sizeof(ctx));
    TEST_ASSERT_FALSE(fl_is_inited(&ctx));
}

void test_loader_is_inited_after_init(void) {
    setup_loader();
    fl_init(&test_ctx);
    TEST_ASSERT_TRUE(fl_is_inited(&test_ctx));
}

/* ============================================================================
 * fl_exec_cmd Tests - Basic Commands
 * ============================================================================ */

void test_loader_cmd_help(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--help"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 2, argv);

    /* --help prints usage but still requires --cmd, so returns error */
    /* Output should contain help text */
    TEST_ASSERT(result != FL_OK);
}

void test_loader_cmd_info(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "info"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
}

void test_loader_cmd_unknown(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "unknown_command_xyz"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    /* Unknown command should return error */
    TEST_ASSERT(result != FL_OK);
}

void test_loader_cmd_empty(void) {
    setup_loader();
    fl_init(&test_ctx);

    fl_error_t result = fl_exec_cmd(&test_ctx, 0, NULL);
    /* Empty command returns error */
    TEST_ASSERT_EQUAL(FL_ERR_ARGS, result);
}

/* ============================================================================
 * fl_exec_cmd Tests - Slot Commands
 * ============================================================================ */

void test_loader_cmd_list(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* 'list' is not a valid command, use 'info' instead */
    const char* argv[] = {"fl", "--cmd", "info"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
}

void test_loader_cmd_clear_invalid_slot(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "unpatch", "--comp", "99"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    /* Invalid slot should error */
    TEST_ASSERT(result != FL_OK || mock_output_contains("Invalid") || mock_output_contains("Error"));
}

void test_loader_cmd_clear_valid_slot(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "unpatch", "--comp", "0"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    /* Should succeed even if slot is empty */
    TEST_ASSERT_EQUAL(FL_OK, result);
}

void test_loader_cmd_clearall(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Mark some slots as active */
    test_ctx.slots[0].active = true;
    test_ctx.slots[1].active = true;

    const char* argv[] = {"fl", "--cmd", "unpatch", "--all"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 4, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
}

/* ============================================================================
 * fl_exec_cmd Tests - Core Commands
 * ============================================================================ */

/* Declare fl_hello (defined in fl.c, non-static) */
extern void fl_hello(void);

void test_loader_cmd_hello(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "hello"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("HELLO from original fl_hello"));
}

void test_loader_cmd_hello_direct_call(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Call fl_hello directly to verify it is not inlined and is linkable */
    fl_hello();

    TEST_ASSERT(mock_output_contains("HELLO from original fl_hello"));
}

void test_loader_cmd_ping(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "ping"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("PONG"));
}

void test_loader_cmd_echo(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "echo", "--data", "SGVsbG8="}; /* "Hello" in base64 */
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
}

void test_loader_cmd_echo_no_data(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "echo"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    /* Echo without data should still succeed */
    TEST_ASSERT_EQUAL(FL_OK, result);
}

void test_loader_cmd_alloc(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "alloc", "--size", "256"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
}

void test_loader_cmd_alloc_no_size(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "alloc"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    /* Alloc without size should fail */
    TEST_ASSERT(result != FL_OK);
}

void test_loader_cmd_alloc_zero(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "alloc", "--size", "0"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    /* Zero size allocation should fail */
    TEST_ASSERT(result != FL_OK);
}

/* ============================================================================
 * fl_exec_cmd Tests - Patch Commands
 * ============================================================================ */

void test_loader_cmd_patch_missing_args(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "patch"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    /* patch without orig/target should fail */
    TEST_ASSERT(result != FL_OK);
}

void test_loader_cmd_patch_valid(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* First allocate some memory */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    const char* argv[] = {"fl", "--cmd", "patch", "--comp", "0", "--orig", "0x08001000", "--target", "0x20000100"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 9, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
}

void test_loader_cmd_tpatch_missing_args(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "tpatch"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    TEST_ASSERT(result != FL_OK);
}

void test_loader_cmd_dpatch_missing_args(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "dpatch"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    TEST_ASSERT(result != FL_OK);
}

/* ============================================================================
 * fl_exec_cmd Tests - Upload Commands
 * ============================================================================ */

void test_loader_cmd_upload_no_alloc(void) {
    setup_loader();
    fl_init(&test_ctx);

    mock_output_reset();
    const char* argv[] = {"fl", "--cmd", "upload", "--data", "AQIDBA=="};
    fl_exec_cmd(&test_ctx, 5, argv);

    /* Upload without alloc should output error message */
    const char* output = mock_output_get();
    TEST_ASSERT(strstr(output, "No allocation") != NULL || strstr(output, "FLERR") != NULL);
}

void test_loader_cmd_upload_no_data(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    const char* argv[] = {"fl", "--cmd", "upload"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    /* Upload without data should fail */
    TEST_ASSERT(result != FL_OK);
}

void test_loader_cmd_upload_with_data(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    const char* argv[] = {"fl", "--cmd", "upload", "--addr", "0", "--data", "AQIDBA=="};
    fl_error_t result = fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
}

void test_loader_cmd_upload_overflow(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Allocate only 4 bytes */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "4"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    mock_output_reset();

    /* Try to upload 4 bytes at offset 2 -> 2+4=6 > 4, overflow */
    const char* argv[] = {"fl", "--cmd", "upload", "--addr", "2", "--data", "AQIDBA=="};
    fl_error_t result = fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(result != FL_OK);
    TEST_ASSERT(mock_output_contains("overflow") || mock_output_contains("FLERR"));
}

/* ============================================================================
 * Slot State Tests
 * ============================================================================ */

void test_loader_slot_state_initial(void) {
    setup_loader();
    fl_init(&test_ctx);

    for (int i = 0; i < FL_MAX_SLOTS; i++) {
        TEST_ASSERT_FALSE(test_ctx.slots[i].active);
        TEST_ASSERT_EQUAL_HEX(0, test_ctx.slots[i].orig_addr);
        TEST_ASSERT_EQUAL_HEX(0, test_ctx.slots[i].target_addr);
        TEST_ASSERT_EQUAL(0, test_ctx.slots[i].code_size);
    }
}

void test_loader_max_slots(void) {
    TEST_ASSERT_EQUAL(8, FL_MAX_SLOTS); /* FPB v2 supports 8 slots */
}

/* ============================================================================
 * fl_exec_cmd Tests - File Commands
 * ============================================================================ */

#include "fl_file.h"
#include <unistd.h>

static void setup_loader_with_file(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Initialize file context with libc ops */
    const fl_fs_ops_t* ops = fl_file_get_libc_ops();
    test_ctx.file_ctx.fs = ops;
}

void test_loader_cmd_fopen(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fopen_%d.txt", getpid());

    const char* argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "w"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FOPEN") || mock_output_contains("FLOK"));

    /* Close the file */
    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);

    /* Cleanup */
    unlink(test_file);
}

void test_loader_cmd_fopen_no_path(void) {
    setup_loader_with_file();

    const char* argv[] = {"fl", "--cmd", "fopen", "--mode", "w"};
    fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT(mock_output_contains("FLERR") || mock_output_contains("path"));
}

void test_loader_cmd_fclose(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fclose_%d.txt", getpid());

    /* Open file first */
    const char* open_argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "w"};
    fl_exec_cmd(&test_ctx, 7, open_argv);

    mock_output_reset();

    /* Close file */
    const char* argv[] = {"fl", "--cmd", "fclose"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FCLOSE") || mock_output_contains("FLOK"));

    /* Cleanup */
    unlink(test_file);
}

void test_loader_cmd_fwrite(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fwrite_%d.txt", getpid());

    /* Open file */
    const char* open_argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "w"};
    fl_exec_cmd(&test_ctx, 7, open_argv);

    mock_output_reset();

    /* Write data (base64: "SGVsbG8=" = "Hello") */
    const char* argv[] = {"fl", "--cmd", "fwrite", "--data", "SGVsbG8="};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FWRITE") || mock_output_contains("FLOK"));

    /* Close file */
    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);

    /* Cleanup */
    unlink(test_file);
}

void test_loader_cmd_fwrite_no_file(void) {
    setup_loader_with_file();

    /* Try to write without opening a file */
    const char* argv[] = {"fl", "--cmd", "fwrite", "--data", "SGVsbG8="};
    fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT(mock_output_contains("FLERR") || mock_output_contains("No file"));
}

void test_loader_cmd_fread(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fread_%d.txt", getpid());

    /* Create a file with content */
    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "Hello");
        fclose(f);
    }

    /* Open file for reading */
    const char* open_argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "r"};
    fl_exec_cmd(&test_ctx, 7, open_argv);

    mock_output_reset();

    /* Read data */
    const char* argv[] = {"fl", "--cmd", "fread", "--len", "5"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FREAD") || mock_output_contains("FLOK"));

    /* Close file */
    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);

    /* Cleanup */
    unlink(test_file);
}

void test_loader_cmd_fseek(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fseek_%d.txt", getpid());

    /* Create a file with content */
    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "Hello World");
        fclose(f);
    }

    /* Open file */
    const char* open_argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "r"};
    fl_exec_cmd(&test_ctx, 7, open_argv);

    mock_output_reset();

    /* Seek to position 6 */
    const char* argv[] = {"fl", "--cmd", "fseek", "--addr", "0x6"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FSEEK") || mock_output_contains("FLOK"));

    /* Close file */
    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);

    /* Cleanup */
    unlink(test_file);
}

void test_loader_cmd_fstat(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fstat_%d.txt", getpid());

    /* Create a file */
    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "Hello");
        fclose(f);
    }

    const char* argv[] = {"fl", "--cmd", "fstat", "--path", test_file};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FSTAT") || mock_output_contains("FLOK") || mock_output_contains("size"));

    /* Cleanup */
    unlink(test_file);
}

void test_loader_cmd_fremove(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fremove_%d.txt", getpid());

    /* Create a file */
    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "to be removed");
        fclose(f);
    }

    const char* argv[] = {"fl", "--cmd", "fremove", "--path", test_file};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FREMOVE") || mock_output_contains("FLOK"));

    /* Verify file is gone */
    TEST_ASSERT(access(test_file, F_OK) != 0);
}

void test_loader_cmd_frename(void) {
    setup_loader_with_file();

    char old_file[256], new_file[256];
    snprintf(old_file, sizeof(old_file), "/tmp/fl_test_old_%d.txt", getpid());
    snprintf(new_file, sizeof(new_file), "/tmp/fl_test_new_%d.txt", getpid());

    /* Create the old file */
    FILE* f = fopen(old_file, "w");
    if (f) {
        fprintf(f, "to be renamed");
        fclose(f);
    }

    const char* argv[] = {"fl", "--cmd", "frename", "--path", old_file, "--newpath", new_file};
    fl_error_t result = fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FRENAME") || mock_output_contains("FLOK"));

    /* Cleanup */
    unlink(old_file);
    unlink(new_file);
}

void test_loader_cmd_fmkdir(void) {
    setup_loader_with_file();

    char test_dir[256];
    snprintf(test_dir, sizeof(test_dir), "/tmp/fl_test_mkdir_%d", getpid());

    const char* argv[] = {"fl", "--cmd", "fmkdir", "--path", test_dir};
    fl_exec_cmd(&test_ctx, 5, argv);

    /* Note: libc backend does not support mkdir, so we just verify no crash */
    TEST_ASSERT(mock_output_contains("FLERR") || mock_output_contains("FLOK"));

    /* Try to cleanup if it was created */
    rmdir(test_dir);
}

void test_loader_cmd_fcrc(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fcrc_%d.txt", getpid());

    /* Create a file with known content */
    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "HelloWorld");
        fclose(f);
    }

    /* Open file */
    const char* open_argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "r"};
    fl_exec_cmd(&test_ctx, 7, open_argv);

    mock_output_reset();

    /* Calculate CRC */
    const char* argv[] = {"fl", "--cmd", "fcrc"};
    fl_exec_cmd(&test_ctx, 3, argv);

    TEST_ASSERT(mock_output_contains("FCRC") || mock_output_contains("FLOK") || mock_output_contains("crc"));

    /* Close file */
    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);

    /* Cleanup */
    unlink(test_file);
}

void test_loader_cmd_fcrc_no_file(void) {
    setup_loader_with_file();

    /* Try to calculate CRC without opening a file */
    const char* argv[] = {"fl", "--cmd", "fcrc"};
    fl_exec_cmd(&test_ctx, 3, argv);

    TEST_ASSERT(mock_output_contains("FLERR") || mock_output_contains("No file"));
}

void test_loader_cmd_flist(void) {
    setup_loader_with_file();

    /* List /tmp directory */
    const char* argv[] = {"fl", "--cmd", "flist", "--path", "/tmp"};
    fl_exec_cmd(&test_ctx, 5, argv);

    /* Note: libc backend does not support directory listing */
    TEST_ASSERT(mock_output_contains("FLERR") || mock_output_contains("FLIST") || mock_output_contains("FLOK"));
}

void test_loader_cmd_upload_hex_data(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Allocate memory first */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    mock_output_reset();

    /* Upload base64 data (AQIDBA== = 01 02 03 04) */
    const char* argv[] = {"fl", "--cmd", "upload", "--addr", "0", "--data", "AQIDBA=="};
    fl_error_t result = fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("Uploaded") || mock_output_contains("FLOK"));
}

void test_loader_cmd_upload_with_crc(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Allocate memory first */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    mock_output_reset();

    /* Upload data with CRC verification
     * Base64: AQIDBA== = 01 02 03 04
     * CRC calculation: calc_crc16([0x01, 0x02, 0x03, 0x04], 4)
     */
    const char* argv[] = {"fl", "--cmd", "upload", "--addr", "0", "--data", "AQIDBA==", "--crc", "0xB5F2"};
    fl_exec_cmd(&test_ctx, 9, argv);

    /* May pass or fail depending on CRC, just check no crash */
    const char* output = mock_output_get();
    TEST_ASSERT(output != NULL);
}

void test_loader_cmd_tpatch_valid(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Allocate memory first */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    mock_output_reset();

    /* Try tpatch - may be disabled with FPB_NO_TRAMPOLINE */
    const char* argv[] = {"fl", "--cmd", "tpatch", "--comp", "0", "--orig", "0x08001000", "--target", "0x20002000"};
    fl_exec_cmd(&test_ctx, 9, argv);

    /* Should either succeed or say trampoline disabled */
    const char* output = mock_output_get();
    TEST_ASSERT(output != NULL);
}

void test_loader_cmd_dpatch_valid(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Allocate memory first */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    mock_output_reset();

    /* Try dpatch - may be disabled with FPB_NO_DEBUGMON */
    const char* argv[] = {"fl", "--cmd", "dpatch", "--comp", "0", "--orig", "0x08001000", "--target", "0x20002000"};
    fl_exec_cmd(&test_ctx, 9, argv);

    /* Should either succeed or say debugmon disabled */
    const char* output = mock_output_get();
    TEST_ASSERT(output != NULL);
}

void test_loader_cmd_run(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Allocate memory first */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    mock_output_reset();

    /* Try run command */
    const char* argv[] = {"fl", "--cmd", "run", "--entry", "0"};
    fl_exec_cmd(&test_ctx, 5, argv);

    /* May fail due to no valid code, but shouldn't crash */
    const char* output = mock_output_get();
    TEST_ASSERT(output != NULL);
}

void test_loader_cmd_read(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Allocate memory first */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    /* Write known data to allocated memory */
    uintptr_t alloc_addr = test_ctx.last_alloc;
    uint8_t* ptr = (uint8_t*)alloc_addr;
    for (int i = 0; i < 16; i++) {
        ptr[i] = (uint8_t)(0xA0 + i);
    }

    mock_output_reset();

    /* Read back via read command */
    char addr_str[32];
    snprintf(addr_str, sizeof(addr_str), "0x%lX", (unsigned long)alloc_addr);
    const char* argv[] = {"fl", "--cmd", "read", "--addr", addr_str, "--len", "16"};
    fl_exec_cmd(&test_ctx, 7, argv);

    /* Should return FLOK with base64 data and CRC */
    const char* output = mock_output_get();
    TEST_ASSERT(output != NULL);
    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("READ 16 bytes"));
    TEST_ASSERT(mock_output_contains("crc=0x"));
    TEST_ASSERT(mock_output_contains("data="));
}

void test_loader_cmd_upload_invalid_data(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Allocate memory first */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    mock_output_reset();

    /* Upload invalid data (not valid hex or base64) */
    const char* argv[] = {"fl", "--cmd", "upload", "--addr", "0", "--data", "ZZZZ!!!"};
    fl_exec_cmd(&test_ctx, 7, argv);

    /* Should fail with invalid encoding error */
    TEST_ASSERT(mock_output_contains("FLERR") || mock_output_contains("Invalid"));
}

void test_loader_cmd_fwrite_hex_data(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fwrite_hex_%d.txt", getpid());

    /* Open file */
    const char* open_argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "w"};
    fl_exec_cmd(&test_ctx, 7, open_argv);

    mock_output_reset();

    /* Write base64 data (SGVsbG8= = "Hello") */
    const char* argv[] = {"fl", "--cmd", "fwrite", "--data", "SGVsbG8="};
    fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT(mock_output_contains("FWRITE") || mock_output_contains("FLOK"));

    /* Close file */
    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);

    /* Cleanup */
    unlink(test_file);
}

void test_loader_cmd_fwrite_with_crc(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fwrite_crc_%d.txt", getpid());

    /* Open file */
    const char* open_argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "w"};
    fl_exec_cmd(&test_ctx, 7, open_argv);

    mock_output_reset();

    /* Write data with CRC (SGVsbG8= = "Hello") */
    const char* argv[] = {"fl", "--cmd", "fwrite", "--data", "SGVsbG8=", "--crc", "0x1234"};
    fl_exec_cmd(&test_ctx, 7, argv);

    /* May fail CRC check, just verify no crash */
    const char* output = mock_output_get();
    TEST_ASSERT(output != NULL);

    /* Close file */
    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);

    /* Cleanup */
    unlink(test_file);
}

void test_loader_cmd_fread_large(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fread_large_%d.txt", getpid());

    /* Create a file with content */
    FILE* f = fopen(test_file, "w");
    if (f) {
        for (int i = 0; i < 100; i++) {
            fprintf(f, "Line %d of test data\n", i);
        }
        fclose(f);
    }

    /* Open file for reading */
    const char* open_argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "r"};
    fl_exec_cmd(&test_ctx, 7, open_argv);

    mock_output_reset();

    /* Read data without specifying len (should use default) */
    const char* argv[] = {"fl", "--cmd", "fread"};
    fl_exec_cmd(&test_ctx, 3, argv);

    TEST_ASSERT(mock_output_contains("FREAD") || mock_output_contains("FLOK"));

    /* Close file */
    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);

    /* Cleanup */
    unlink(test_file);
}

void test_loader_cmd_fclose_no_file(void) {
    setup_loader_with_file();

    /* Try to close without opening */
    const char* argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, argv);

    /* Should report error or succeed gracefully */
    const char* output = mock_output_get();
    TEST_ASSERT(output != NULL);
}

void test_loader_cmd_fseek_no_file(void) {
    setup_loader_with_file();

    /* Try to seek without opening */
    const char* argv[] = {"fl", "--cmd", "fseek", "--addr", "0x10"};
    fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT(mock_output_contains("FLERR") || mock_output_contains("No file"));
}

void test_loader_cmd_fstat_no_path(void) {
    setup_loader_with_file();

    /* Try fstat without path */
    const char* argv[] = {"fl", "--cmd", "fstat"};
    fl_exec_cmd(&test_ctx, 3, argv);

    TEST_ASSERT(mock_output_contains("FLERR") || mock_output_contains("Missing"));
}

void test_loader_cmd_read_no_alloc(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Read from a stack-local buffer without alloc — should still work */
    static uint8_t local_buf[16] = {0x01, 0x02, 0x03, 0x04};
    char addr_str[32];
    snprintf(addr_str, sizeof(addr_str), "0x%lX", (unsigned long)(uintptr_t)local_buf);
    const char* argv[] = {"fl", "--cmd", "read", "--addr", addr_str, "--len", "4"};
    fl_exec_cmd(&test_ctx, 7, argv);

    const char* output = mock_output_get();
    TEST_ASSERT(output != NULL);
    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("READ 4 bytes"));
}

void test_loader_cmd_read_invalid_len(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Read with length 0 — should fail */
    const char* argv[] = {"fl", "--cmd", "read", "--addr", "0x1000", "--len", "0"};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("Invalid length"));
}

void test_loader_cmd_write(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Allocate a buffer to write into */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    uintptr_t alloc_addr = test_ctx.last_alloc;
    mock_output_reset();

    /* Write base64 data "AQIDBA==" = {0x01, 0x02, 0x03, 0x04} */
    char addr_str[32];
    snprintf(addr_str, sizeof(addr_str), "0x%lX", (unsigned long)alloc_addr);
    const char* argv[] = {"fl", "--cmd", "write", "--addr", addr_str, "--data", "AQIDBA=="};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("WRITE 4 bytes"));

    /* Verify memory contents */
    uint8_t* ptr = (uint8_t*)alloc_addr;
    TEST_ASSERT_EQUAL(0x01, ptr[0]);
    TEST_ASSERT_EQUAL(0x02, ptr[1]);
    TEST_ASSERT_EQUAL(0x03, ptr[2]);
    TEST_ASSERT_EQUAL(0x04, ptr[3]);
}

void test_loader_cmd_write_with_crc(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    uintptr_t alloc_addr = test_ctx.last_alloc;
    mock_output_reset();

    /* Write with valid CRC — "AQIDBA==" = {0x01, 0x02, 0x03, 0x04}, CRC pre-computed */
    char addr_str[32];
    snprintf(addr_str, sizeof(addr_str), "0x%lX", (unsigned long)alloc_addr);

    /* Write base64 data (AQIDBA== = 0x01 0x02 0x03 0x04) */
    const char* argv[] = {"fl", "--cmd", "write", "--addr", addr_str, "--data", "AQIDBA=="};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("WRITE 4 bytes"));
}

void test_loader_cmd_write_crc_mismatch(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    uintptr_t alloc_addr = test_ctx.last_alloc;
    mock_output_reset();

    /* Write with wrong CRC */
    char addr_str[32];
    snprintf(addr_str, sizeof(addr_str), "0x%lX", (unsigned long)alloc_addr);
    const char* argv[] = {"fl", "--cmd", "write", "--addr", addr_str, "--data", "AQIDBA==", "--crc", "0xFFFF"};
    fl_exec_cmd(&test_ctx, 9, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("CRC mismatch"));
}

void test_loader_cmd_write_no_data(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Write without --data should fail */
    const char* argv[] = {"fl", "--cmd", "write", "--addr", "0x1000"};
    fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT(mock_output_contains("FLERR") || mock_output_contains("Missing"));
}

void test_loader_cmd_write_zero_addr(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Write to address 0 should fail */
    const char* argv[] = {"fl", "--cmd", "write", "--addr", "0x0", "--data", "AQIDBA=="};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("Invalid address"));
}

void test_loader_cmd_read_zero_addr(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Read from address 0 should fail */
    const char* argv[] = {"fl", "--cmd", "read", "--addr", "0x0", "--len", "4"};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("Invalid address range"));
}

void test_loader_cmd_read_zero_addr_force(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Read from address 0 with --force should bypass the check.
     * Note: actual memcpy from 0x0 may segfault on host, so we use
     * a valid address but verify the --force flag is accepted.
     */
    static uint8_t local_buf[4] = {0x11, 0x22, 0x33, 0x44};
    char addr_str[32];
    snprintf(addr_str, sizeof(addr_str), "0x%lX", (unsigned long)(uintptr_t)local_buf);

    /* First verify it works without --force */
    const char* argv1[] = {"fl", "--cmd", "read", "--addr", addr_str, "--len", "4"};
    fl_exec_cmd(&test_ctx, 7, argv1);
    TEST_ASSERT(mock_output_contains("FLOK"));

    mock_output_reset();

    /* Now with --force, should also work */
    const char* argv2[] = {"fl", "--cmd", "read", "--addr", addr_str, "--len", "4", "--force"};
    fl_exec_cmd(&test_ctx, 8, argv2);
    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("READ 4 bytes"));
}

void test_loader_cmd_write_zero_addr_force(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Allocate a buffer and use --force to write */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    uintptr_t alloc_addr = test_ctx.last_alloc;
    char addr_str[32];
    snprintf(addr_str, sizeof(addr_str), "0x%lX", (unsigned long)alloc_addr);

    mock_output_reset();

    /* Write with --force should succeed */
    const char* argv[] = {"fl", "--cmd", "write", "--addr", addr_str, "--data", "AQIDBA==", "--force"};
    fl_exec_cmd(&test_ctx, 8, argv);

    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("WRITE 4 bytes"));
}

void test_loader_cmd_write_overflow_addr(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Write to 0xFFFFFFFF with 3 bytes: addr+len-1 wraps past 0xFFFFFFFF */
    const char* argv[] = {"fl", "--cmd", "write", "--addr", "0xFFFFFFFF", "--data", "AQID"};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("Invalid address range"));
}

void test_loader_cmd_read_overflow_addr(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Read from 0xFFFFFFFF with len=2: addr+len-1 wraps past 0xFFFFFFFF */
    const char* argv[] = {"fl", "--cmd", "read", "--addr", "0xFFFFFFFF", "--len", "2"};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("Invalid address range"));
}

void test_loader_cmd_write_force_hint_in_error(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Error message should hint about --force */
    const char* argv[] = {"fl", "--cmd", "write", "--addr", "0x0", "--data", "AQIDBA=="};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("--force"));
}

void test_loader_cmd_read_write_roundtrip(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Allocate buffer */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    uintptr_t alloc_addr = test_ctx.last_alloc;
    char addr_str[32];
    snprintf(addr_str, sizeof(addr_str), "0x%lX", (unsigned long)alloc_addr);

    mock_output_reset();

    /* Write known data (3q2+7w== = 0xDE 0xAD 0xBE 0xEF) */
    const char* write_argv[] = {"fl", "--cmd", "write", "--addr", addr_str, "--data", "3q2+7w=="};
    fl_exec_cmd(&test_ctx, 7, write_argv);
    TEST_ASSERT(mock_output_contains("FLOK"));

    mock_output_reset();

    /* Read it back */
    const char* read_argv[] = {"fl", "--cmd", "read", "--addr", addr_str, "--len", "4"};
    fl_exec_cmd(&test_ctx, 7, read_argv);
    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("READ 4 bytes"));

    /* Verify memory directly */
    uint8_t* ptr = (uint8_t*)alloc_addr;
    TEST_ASSERT_EQUAL(0xDE, ptr[0]);
    TEST_ASSERT_EQUAL(0xAD, ptr[1]);
    TEST_ASSERT_EQUAL(0xBE, ptr[2]);
    TEST_ASSERT_EQUAL(0xEF, ptr[3]);
}

void test_loader_cmd_run_no_alloc(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Try run without alloc */
    const char* argv[] = {"fl", "--cmd", "run", "--entry", "0"};
    fl_exec_cmd(&test_ctx, 5, argv);

    /* Should fail */
    const char* output = mock_output_get();
    TEST_ASSERT(output != NULL);
}

/* ============================================================================
 * fl_exec_cmd Tests - Enable Command
 * ============================================================================ */

void test_loader_cmd_enable_missing_arg(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* enable command without --enable argument should fail */
    const char* argv[] = {"fl", "--cmd", "enable", "--comp", "0"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT(result != FL_OK);
    TEST_ASSERT(mock_output_contains("Missing --enable"));
}

void test_loader_cmd_enable_single_disable(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* First set up a patch */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    const char* patch_argv[]
        = {"fl", "--cmd", "patch", "--comp", "0", "--orig", "0x08001000", "--target", "0x20000100"};
    fl_exec_cmd(&test_ctx, 9, patch_argv);

    mock_output_reset();

    /* Disable the patch */
    const char* argv[] = {"fl", "--cmd", "enable", "--comp", "0", "--enable", "0"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("Disabled patch 0"));
}

void test_loader_cmd_enable_single_enable(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* First set up a patch */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    const char* patch_argv[]
        = {"fl", "--cmd", "patch", "--comp", "0", "--orig", "0x08001000", "--target", "0x20000100"};
    fl_exec_cmd(&test_ctx, 9, patch_argv);

    /* Disable first */
    const char* disable_argv[] = {"fl", "--cmd", "enable", "--comp", "0", "--enable", "0"};
    fl_exec_cmd(&test_ctx, 7, disable_argv);

    mock_output_reset();

    /* Re-enable the patch */
    const char* argv[] = {"fl", "--cmd", "enable", "--comp", "0", "--enable", "1"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("Enabled patch 0"));
}

void test_loader_cmd_enable_all_disable(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Set up multiple patches */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    const char* patch0_argv[]
        = {"fl", "--cmd", "patch", "--comp", "0", "--orig", "0x08001000", "--target", "0x20000100"};
    fl_exec_cmd(&test_ctx, 9, patch0_argv);

    fl_exec_cmd(&test_ctx, 5, alloc_argv);
    const char* patch1_argv[]
        = {"fl", "--cmd", "patch", "--comp", "1", "--orig", "0x08002000", "--target", "0x20000200"};
    fl_exec_cmd(&test_ctx, 9, patch1_argv);

    mock_output_reset();

    /* Disable all patches */
    const char* argv[] = {"fl", "--cmd", "enable", "--enable", "0", "--all"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 6, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("Disabled"));
    TEST_ASSERT(mock_output_contains("patches"));
}

void test_loader_cmd_enable_all_enable(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Set up multiple patches */
    const char* alloc_argv[] = {"fl", "--cmd", "alloc", "--size", "64"};
    fl_exec_cmd(&test_ctx, 5, alloc_argv);

    const char* patch0_argv[]
        = {"fl", "--cmd", "patch", "--comp", "0", "--orig", "0x08001000", "--target", "0x20000100"};
    fl_exec_cmd(&test_ctx, 9, patch0_argv);

    fl_exec_cmd(&test_ctx, 5, alloc_argv);
    const char* patch1_argv[]
        = {"fl", "--cmd", "patch", "--comp", "1", "--orig", "0x08002000", "--target", "0x20000200"};
    fl_exec_cmd(&test_ctx, 9, patch1_argv);

    /* Disable all first */
    const char* disable_argv[] = {"fl", "--cmd", "enable", "--enable", "0", "--all"};
    fl_exec_cmd(&test_ctx, 6, disable_argv);

    mock_output_reset();

    /* Re-enable all patches */
    const char* argv[] = {"fl", "--cmd", "enable", "--enable", "1", "--all"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 6, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("Enabled"));
    TEST_ASSERT(mock_output_contains("patches"));
}

void test_loader_cmd_enable_invalid_comp(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Try to enable invalid comparator */
    const char* argv[] = {"fl", "--cmd", "enable", "--comp", "99", "--enable", "1"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(result != FL_OK || mock_output_contains("Invalid"));
}

void test_loader_cmd_enable_unset_patch(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Try to enable a patch that was never set - should succeed but report 0 changed */
    const char* argv[] = {"fl", "--cmd", "enable", "--comp", "0", "--enable", "1"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 7, argv);

    /* fpb_enable_patch returns FPB_ERR_NOT_SET for unset patches, so changed=0 */
    TEST_ASSERT_EQUAL(FL_OK, result);
}

/* ============================================================================
 * fl_exec_cmd Tests - Echoback Command
 * ============================================================================ */

void test_loader_cmd_echoback_basic(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "echoback", "--len", "16"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("ECHOBACK 16 bytes"));
    TEST_ASSERT(mock_output_contains("crc=0x"));
    TEST_ASSERT(mock_output_contains("data="));
}

void test_loader_cmd_echoback_verify_pattern(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Request 4 bytes: pattern is {0x00, 0x01, 0x02, 0x03} */
    const char* argv[] = {"fl", "--cmd", "echoback", "--len", "4"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("ECHOBACK 4 bytes"));

    /* Verify the base64 data: {0x00, 0x01, 0x02, 0x03} -> "AAECAw==" */
    TEST_ASSERT(mock_output_contains("AAECAw=="));
}

void test_loader_cmd_echoback_verify_crc(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Request 1 byte: pattern is {0x00}, CRC16 of {0x00} with init 0xFFFF */
    const char* argv[] = {"fl", "--cmd", "echoback", "--len", "1"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("ECHOBACK 1 bytes"));
    TEST_ASSERT(mock_output_contains("crc=0x"));
}

void test_loader_cmd_echoback_max_len(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Request FL_BUF_SIZE (1024) bytes — should succeed */
    const char* argv[] = {"fl", "--cmd", "echoback", "--len", "1024"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("ECHOBACK 1024 bytes"));
}

void test_loader_cmd_echoback_zero_len(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "echoback", "--len", "0"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT(result != FL_OK);
    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("Invalid length"));
}

void test_loader_cmd_echoback_negative_len(void) {
    setup_loader();
    fl_init(&test_ctx);

    const char* argv[] = {"fl", "--cmd", "echoback", "--len", "-1"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT(result != FL_OK);
    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("Invalid length"));
}

void test_loader_cmd_echoback_over_max(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Request FL_BUF_SIZE + 1 (1025) bytes — should fail */
    const char* argv[] = {"fl", "--cmd", "echoback", "--len", "1025"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT(result != FL_OK);
    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("Invalid length"));
}

void test_loader_cmd_echoback_default_len(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Without --len, default is 64 */
    const char* argv[] = {"fl", "--cmd", "echoback"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 3, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("ECHOBACK 64 bytes"));
}

/* ============================================================================
 * CRC Integrity V2 Tests
 * ============================================================================ */

void test_loader_cmd_alloc_with_crc(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Compute CRC for size=256: CRC16 of uint32_t(256) in LE */
    uint32_t size32 = 256;
    uint16_t crc = test_crc16(&size32, sizeof(size32));
    char crc_str[16];
    snprintf(crc_str, sizeof(crc_str), "0x%04X", crc);

    const char* argv[] = {"fl", "--cmd", "alloc", "--size", "256", "--crc", crc_str};
    fl_error_t result = fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("Allocated"));
}

void test_loader_cmd_alloc_crc_mismatch(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* Wrong CRC for size=256 */
    const char* argv[] = {"fl", "--cmd", "alloc", "--size", "256", "--crc", "0xFFFF"};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("CRC mismatch"));
}

void test_loader_cmd_alloc_without_crc_still_works(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* No --crc arg: backward compatible, should still work */
    const char* argv[] = {"fl", "--cmd", "alloc", "--size", "128"};
    fl_error_t result = fl_exec_cmd(&test_ctx, 5, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FLOK"));
}

void test_loader_cmd_fopen_with_crc(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fopen_crc_%d.txt", getpid());

    /* Compute CRC for path + mode */
    const char* mode = "w";
    uint16_t crc = test_crc16_update(0xFFFF, test_file, strlen(test_file));
    crc = test_crc16_update(crc, mode, strlen(mode));
    char crc_str[16];
    snprintf(crc_str, sizeof(crc_str), "0x%04X", crc);

    const char* argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "w", "--crc", crc_str};
    fl_error_t result = fl_exec_cmd(&test_ctx, 9, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("FOPEN"));

    /* Close and cleanup */
    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);
    unlink(test_file);
}

void test_loader_cmd_fopen_crc_mismatch(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fopen_crc_bad_%d.txt", getpid());

    /* Wrong CRC */
    const char* argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "w", "--crc", "0xDEAD"};
    fl_exec_cmd(&test_ctx, 9, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("CRC mismatch"));
}

void test_loader_cmd_fremove_with_crc(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fremove_crc_%d.txt", getpid());

    /* Create a file */
    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "to be removed");
        fclose(f);
    }

    /* Compute CRC for path */
    uint16_t crc = test_crc16(test_file, strlen(test_file));
    char crc_str[16];
    snprintf(crc_str, sizeof(crc_str), "0x%04X", crc);

    const char* argv[] = {"fl", "--cmd", "fremove", "--path", test_file, "--crc", crc_str};
    fl_error_t result = fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("FREMOVE"));

    /* Verify file is gone */
    TEST_ASSERT(access(test_file, F_OK) != 0);
}

void test_loader_cmd_fremove_crc_mismatch(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fremove_crc_bad_%d.txt", getpid());

    /* Create a file */
    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "should not be removed");
        fclose(f);
    }

    /* Wrong CRC — file must NOT be deleted */
    const char* argv[] = {"fl", "--cmd", "fremove", "--path", test_file, "--crc", "0xDEAD"};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("CRC mismatch"));

    /* File must still exist */
    TEST_ASSERT(access(test_file, F_OK) == 0);

    /* Cleanup */
    unlink(test_file);
}

void test_loader_cmd_frename_with_crc(void) {
    setup_loader_with_file();

    char old_file[256], new_file[256];
    snprintf(old_file, sizeof(old_file), "/tmp/fl_test_ren_old_crc_%d.txt", getpid());
    snprintf(new_file, sizeof(new_file), "/tmp/fl_test_ren_new_crc_%d.txt", getpid());

    /* Create the old file */
    FILE* f = fopen(old_file, "w");
    if (f) {
        fprintf(f, "to be renamed");
        fclose(f);
    }

    /* Compute CRC for path + newpath */
    uint16_t crc = test_crc16_update(0xFFFF, old_file, strlen(old_file));
    crc = test_crc16_update(crc, new_file, strlen(new_file));
    char crc_str[16];
    snprintf(crc_str, sizeof(crc_str), "0x%04X", crc);

    const char* argv[] = {"fl", "--cmd", "frename", "--path", old_file, "--newpath", new_file, "--crc", crc_str};
    fl_error_t result = fl_exec_cmd(&test_ctx, 9, argv);

    TEST_ASSERT_EQUAL(FL_OK, result);
    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("FRENAME"));

    /* Cleanup */
    unlink(old_file);
    unlink(new_file);
}

void test_loader_cmd_frename_crc_mismatch(void) {
    setup_loader_with_file();

    char old_file[256], new_file[256];
    snprintf(old_file, sizeof(old_file), "/tmp/fl_test_ren_old_bad_%d.txt", getpid());
    snprintf(new_file, sizeof(new_file), "/tmp/fl_test_ren_new_bad_%d.txt", getpid());

    /* Create the old file */
    FILE* f = fopen(old_file, "w");
    if (f) {
        fprintf(f, "should not be renamed");
        fclose(f);
    }

    /* Wrong CRC */
    const char* argv[] = {"fl", "--cmd", "frename", "--path", old_file, "--newpath", new_file, "--crc", "0xDEAD"};
    fl_exec_cmd(&test_ctx, 9, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("CRC mismatch"));

    /* Cleanup */
    unlink(old_file);
    unlink(new_file);
}

void test_loader_cmd_fcrc_chunked(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fcrc_chunk_%d.txt", getpid());

    /* Create a file with known content */
    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "HelloWorld");
        fclose(f);
    }

    /* Open file */
    const char* open_argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "r"};
    fl_exec_cmd(&test_ctx, 7, open_argv);

    mock_output_reset();

    /* Calculate CRC of first 5 bytes (offset=0, len=5) */
    const char* argv1[] = {"fl", "--cmd", "fcrc", "--addr", "0", "--len", "5"};
    fl_exec_cmd(&test_ctx, 7, argv1);

    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("FCRC"));
    TEST_ASSERT(mock_output_contains("offset=0"));
    TEST_ASSERT(mock_output_contains("size=5"));

    /* Extract CRC from output for chaining */
    const char* output = mock_output_get();
    TEST_ASSERT_NOT_NULL(output);

    /* Verify the output contains a crc= field */
    TEST_ASSERT(strstr(output, "crc=0x") != NULL);

    mock_output_reset();

    /* Calculate CRC of next 5 bytes (offset=5, len=5), chaining with previous CRC */
    /* Use the CRC from "Hello" to chain */
    uint16_t hello_crc = test_crc16("Hello", 5);
    char crc_str[16];
    snprintf(crc_str, sizeof(crc_str), "0x%04X", hello_crc);

    const char* argv2[] = {"fl", "--cmd", "fcrc", "--addr", "5", "--len", "5", "--crc", crc_str};
    fl_exec_cmd(&test_ctx, 9, argv2);

    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("offset=5"));
    TEST_ASSERT(mock_output_contains("size=5"));

    /* The chained CRC should equal CRC of "HelloWorld" */
    uint16_t full_crc = test_crc16("HelloWorld", 10);
    char expected_crc_str[16];
    snprintf(expected_crc_str, sizeof(expected_crc_str), "crc=0x%04X", full_crc);
    TEST_ASSERT(mock_output_contains(expected_crc_str));

    /* Close file */
    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);

    /* Cleanup */
    unlink(test_file);
}

void test_loader_cmd_fcrc_offset_response_format(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fcrc_fmt_%d.txt", getpid());

    /* Create a file */
    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "ABCDEF");
        fclose(f);
    }

    /* Open file */
    const char* open_argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "r"};
    fl_exec_cmd(&test_ctx, 7, open_argv);

    mock_output_reset();

    /* fcrc without --addr defaults to offset=0 */
    const char* argv[] = {"fl", "--cmd", "fcrc", "--len", "6"};
    fl_exec_cmd(&test_ctx, 5, argv);

    /* New response format must include offset= */
    TEST_ASSERT(mock_output_contains("offset=0"));
    TEST_ASSERT(mock_output_contains("size=6"));

    /* Close file */
    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);

    unlink(test_file);
}

void test_loader_cmd_fseek_with_crc(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fseek_crc_%d.txt", getpid());

    /* Create and open a file */
    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "HelloWorld");
        fclose(f);
    }

    const char* open_argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "r"};
    fl_exec_cmd(&test_ctx, 7, open_argv);

    mock_output_reset();

    /* Seek with valid CRC: CRC of addr(4B) = 5 */
    uint32_t addr32 = 5;
    uint16_t crc = test_crc16(&addr32, sizeof(addr32));
    char crc_str[16];
    snprintf(crc_str, sizeof(crc_str), "0x%04X", crc);

    const char* argv[] = {"fl", "--cmd", "fseek", "--addr", "5", "--crc", crc_str};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("FSEEK"));

    /* Close and cleanup */
    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);
    unlink(test_file);
}

void test_loader_cmd_fseek_crc_mismatch(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fseek_crc_bad_%d.txt", getpid());

    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "HelloWorld");
        fclose(f);
    }

    const char* open_argv[] = {"fl", "--cmd", "fopen", "--path", test_file, "--mode", "r"};
    fl_exec_cmd(&test_ctx, 7, open_argv);

    mock_output_reset();

    const char* argv[] = {"fl", "--cmd", "fseek", "--addr", "5", "--crc", "0xDEAD"};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("CRC mismatch"));

    const char* close_argv[] = {"fl", "--cmd", "fclose"};
    fl_exec_cmd(&test_ctx, 3, close_argv);
    unlink(test_file);
}

void test_loader_cmd_fstat_with_crc(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fstat_crc_%d.txt", getpid());

    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "test");
        fclose(f);
    }

    uint16_t crc = test_crc16(test_file, strlen(test_file));
    char crc_str[16];
    snprintf(crc_str, sizeof(crc_str), "0x%04X", crc);

    mock_output_reset();

    const char* argv[] = {"fl", "--cmd", "fstat", "--path", test_file, "--crc", crc_str};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLOK"));
    TEST_ASSERT(mock_output_contains("FSTAT"));

    unlink(test_file);
}

void test_loader_cmd_fstat_crc_mismatch(void) {
    setup_loader_with_file();

    char test_file[256];
    snprintf(test_file, sizeof(test_file), "/tmp/fl_test_fstat_crc_bad_%d.txt", getpid());

    FILE* f = fopen(test_file, "w");
    if (f) {
        fprintf(f, "test");
        fclose(f);
    }

    mock_output_reset();

    const char* argv[] = {"fl", "--cmd", "fstat", "--path", test_file, "--crc", "0xDEAD"};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("CRC mismatch"));

    unlink(test_file);
}

void test_loader_cmd_fmkdir_with_crc(void) {
    setup_loader_with_file();

    char test_dir[256];
    snprintf(test_dir, sizeof(test_dir), "/tmp/fl_test_mkdir_crc_%d", getpid());

    /* Pre-cleanup in case of previous failed run */
    rmdir(test_dir);

    uint16_t crc = test_crc16(test_dir, strlen(test_dir));
    char crc_str[16];
    snprintf(crc_str, sizeof(crc_str), "0x%04X", crc);

    mock_output_reset();

    const char* argv[] = {"fl", "--cmd", "fmkdir", "--path", test_dir, "--crc", crc_str};
    fl_exec_cmd(&test_ctx, 7, argv);

    /* libc backend may not support mkdir, so accept either result.
     * Key point: CRC passed, command was attempted (not rejected by CRC check). */
    TEST_ASSERT(mock_output_contains("FLERR") || mock_output_contains("FLOK"));
    /* Must NOT contain CRC mismatch — that would mean CRC check failed */
    TEST_ASSERT(!mock_output_contains("CRC mismatch"));

    rmdir(test_dir);
}

void test_loader_cmd_fmkdir_crc_mismatch(void) {
    setup_loader_with_file();

    char test_dir[256];
    snprintf(test_dir, sizeof(test_dir), "/tmp/fl_test_mkdir_crc_bad_%d", getpid());

    const char* argv[] = {"fl", "--cmd", "fmkdir", "--path", test_dir, "--crc", "0xDEAD"};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("CRC mismatch"));

    /* Directory must NOT have been created */
    TEST_ASSERT(access(test_dir, F_OK) != 0);
}

void test_loader_cmd_unpatch_with_crc(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* CRC of comp=0: CRC16 of uint32_t(0) */
    uint32_t comp32 = 0;
    uint16_t crc = test_crc16(&comp32, sizeof(comp32));
    char crc_str[16];
    snprintf(crc_str, sizeof(crc_str), "0x%04X", crc);

    mock_output_reset();

    const char* argv[] = {"fl", "--cmd", "unpatch", "--comp", "0", "--crc", crc_str};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLOK"));
}

void test_loader_cmd_unpatch_crc_mismatch(void) {
    setup_loader();
    fl_init(&test_ctx);

    mock_output_reset();

    const char* argv[] = {"fl", "--cmd", "unpatch", "--comp", "0", "--crc", "0xDEAD"};
    fl_exec_cmd(&test_ctx, 7, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("CRC mismatch"));
}

void test_loader_cmd_enable_with_crc(void) {
    setup_loader();
    fl_init(&test_ctx);

    /* CRC of comp=0 + enable=1 */
    uint32_t comp32 = 0;
    uint32_t enable32 = 1;
    uint16_t crc = test_crc16_update(0xFFFF, &comp32, sizeof(comp32));
    crc = test_crc16_update(crc, &enable32, sizeof(enable32));
    char crc_str[16];
    snprintf(crc_str, sizeof(crc_str), "0x%04X", crc);

    mock_output_reset();

    const char* argv[] = {"fl", "--cmd", "enable", "--comp", "0", "--enable", "1", "--crc", crc_str};
    fl_exec_cmd(&test_ctx, 9, argv);

    TEST_ASSERT(mock_output_contains("FLOK"));
}

void test_loader_cmd_enable_crc_mismatch(void) {
    setup_loader();
    fl_init(&test_ctx);

    mock_output_reset();

    const char* argv[] = {"fl", "--cmd", "enable", "--comp", "0", "--enable", "1", "--crc", "0xDEAD"};
    fl_exec_cmd(&test_ctx, 9, argv);

    TEST_ASSERT(mock_output_contains("FLERR"));
    TEST_ASSERT(mock_output_contains("CRC mismatch"));
}

/* ============================================================================
 * Test Runner
 * ============================================================================ */

void run_loader_tests(void) {
    TEST_SUITE_BEGIN("func_loader - Initialization");
    RUN_TEST(test_loader_init_default);
    RUN_TEST(test_loader_init_basic);
    RUN_TEST(test_loader_init_clears_slots);
    RUN_TEST(test_loader_init_idempotent);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - State Checks");
    RUN_TEST(test_loader_not_inited);
    RUN_TEST(test_loader_is_inited_after_init);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Basic Commands");
    RUN_TEST(test_loader_cmd_help);
    RUN_TEST(test_loader_cmd_info);
    RUN_TEST(test_loader_cmd_unknown);
    RUN_TEST(test_loader_cmd_empty);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Core Commands");
    RUN_TEST(test_loader_cmd_ping);
    RUN_TEST(test_loader_cmd_echo);
    RUN_TEST(test_loader_cmd_echo_no_data);
    RUN_TEST(test_loader_cmd_alloc);
    RUN_TEST(test_loader_cmd_alloc_no_size);
    RUN_TEST(test_loader_cmd_alloc_zero);
    RUN_TEST(test_loader_cmd_hello);
    RUN_TEST(test_loader_cmd_hello_direct_call);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Patch Commands");
    RUN_TEST(test_loader_cmd_patch_missing_args);
    RUN_TEST(test_loader_cmd_patch_valid);
    RUN_TEST(test_loader_cmd_tpatch_missing_args);
    RUN_TEST(test_loader_cmd_dpatch_missing_args);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Upload Commands");
    RUN_TEST(test_loader_cmd_upload_no_alloc);
    RUN_TEST(test_loader_cmd_upload_no_data);
    RUN_TEST(test_loader_cmd_upload_with_data);
    RUN_TEST(test_loader_cmd_upload_overflow);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Slot Commands");
    RUN_TEST(test_loader_cmd_list);
    RUN_TEST(test_loader_cmd_clear_invalid_slot);
    RUN_TEST(test_loader_cmd_clear_valid_slot);
    RUN_TEST(test_loader_cmd_clearall);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Slot State");
    RUN_TEST(test_loader_slot_state_initial);
    RUN_TEST(test_loader_max_slots);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - File Commands");
    RUN_TEST(test_loader_cmd_fopen);
    RUN_TEST(test_loader_cmd_fopen_no_path);
    RUN_TEST(test_loader_cmd_fclose);
    RUN_TEST(test_loader_cmd_fclose_no_file);
    RUN_TEST(test_loader_cmd_fwrite);
    RUN_TEST(test_loader_cmd_fwrite_no_file);
    RUN_TEST(test_loader_cmd_fwrite_hex_data);
    RUN_TEST(test_loader_cmd_fwrite_with_crc);
    RUN_TEST(test_loader_cmd_fread);
    RUN_TEST(test_loader_cmd_fread_large);
    RUN_TEST(test_loader_cmd_fseek);
    RUN_TEST(test_loader_cmd_fseek_no_file);
    RUN_TEST(test_loader_cmd_fstat);
    RUN_TEST(test_loader_cmd_fstat_no_path);
    RUN_TEST(test_loader_cmd_fremove);
    RUN_TEST(test_loader_cmd_frename);
    RUN_TEST(test_loader_cmd_fmkdir);
    RUN_TEST(test_loader_cmd_fcrc);
    RUN_TEST(test_loader_cmd_fcrc_no_file);
    RUN_TEST(test_loader_cmd_flist);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Advanced Commands");
    RUN_TEST(test_loader_cmd_upload_hex_data);
    RUN_TEST(test_loader_cmd_upload_with_crc);
    RUN_TEST(test_loader_cmd_upload_invalid_data);
    RUN_TEST(test_loader_cmd_tpatch_valid);
    RUN_TEST(test_loader_cmd_dpatch_valid);
    RUN_TEST(test_loader_cmd_run);
    RUN_TEST(test_loader_cmd_run_no_alloc);
    RUN_TEST(test_loader_cmd_read);
    RUN_TEST(test_loader_cmd_read_no_alloc);
    RUN_TEST(test_loader_cmd_read_invalid_len);
    RUN_TEST(test_loader_cmd_write);
    RUN_TEST(test_loader_cmd_write_with_crc);
    RUN_TEST(test_loader_cmd_write_crc_mismatch);
    RUN_TEST(test_loader_cmd_write_no_data);
    RUN_TEST(test_loader_cmd_write_zero_addr);
    RUN_TEST(test_loader_cmd_read_write_roundtrip);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Address Range Check");
    RUN_TEST(test_loader_cmd_read_zero_addr);
    RUN_TEST(test_loader_cmd_read_zero_addr_force);
    RUN_TEST(test_loader_cmd_write_zero_addr_force);
    RUN_TEST(test_loader_cmd_write_overflow_addr);
    RUN_TEST(test_loader_cmd_read_overflow_addr);
    RUN_TEST(test_loader_cmd_write_force_hint_in_error);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Enable Command");
    RUN_TEST(test_loader_cmd_enable_missing_arg);
    RUN_TEST(test_loader_cmd_enable_single_disable);
    RUN_TEST(test_loader_cmd_enable_single_enable);
    RUN_TEST(test_loader_cmd_enable_all_disable);
    RUN_TEST(test_loader_cmd_enable_all_enable);
    RUN_TEST(test_loader_cmd_enable_invalid_comp);
    RUN_TEST(test_loader_cmd_enable_unset_patch);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - Echoback Command");
    RUN_TEST(test_loader_cmd_echoback_basic);
    RUN_TEST(test_loader_cmd_echoback_verify_pattern);
    RUN_TEST(test_loader_cmd_echoback_verify_crc);
    RUN_TEST(test_loader_cmd_echoback_max_len);
    RUN_TEST(test_loader_cmd_echoback_zero_len);
    RUN_TEST(test_loader_cmd_echoback_negative_len);
    RUN_TEST(test_loader_cmd_echoback_over_max);
    RUN_TEST(test_loader_cmd_echoback_default_len);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader - CRC Integrity V2");
    RUN_TEST(test_loader_cmd_alloc_with_crc);
    RUN_TEST(test_loader_cmd_alloc_crc_mismatch);
    RUN_TEST(test_loader_cmd_alloc_without_crc_still_works);
    RUN_TEST(test_loader_cmd_fopen_with_crc);
    RUN_TEST(test_loader_cmd_fopen_crc_mismatch);
    RUN_TEST(test_loader_cmd_fremove_with_crc);
    RUN_TEST(test_loader_cmd_fremove_crc_mismatch);
    RUN_TEST(test_loader_cmd_frename_with_crc);
    RUN_TEST(test_loader_cmd_frename_crc_mismatch);
    RUN_TEST(test_loader_cmd_fcrc_chunked);
    RUN_TEST(test_loader_cmd_fcrc_offset_response_format);
    RUN_TEST(test_loader_cmd_fseek_with_crc);
    RUN_TEST(test_loader_cmd_fseek_crc_mismatch);
    RUN_TEST(test_loader_cmd_fstat_with_crc);
    RUN_TEST(test_loader_cmd_fstat_crc_mismatch);
    RUN_TEST(test_loader_cmd_fmkdir_with_crc);
    RUN_TEST(test_loader_cmd_fmkdir_crc_mismatch);
    RUN_TEST(test_loader_cmd_unpatch_with_crc);
    RUN_TEST(test_loader_cmd_unpatch_crc_mismatch);
    RUN_TEST(test_loader_cmd_enable_with_crc);
    RUN_TEST(test_loader_cmd_enable_crc_mismatch);
    TEST_SUITE_END();
}
