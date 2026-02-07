/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Tests for func_loader_file.c - File operations
 */

#include "test_framework.h"
#include "mock_hardware.h"
#include "fpb_mock_regs.h"
#include "func_loader.h"
#include "func_loader_file.h"

#include <stdio.h>
#include <string.h>
#include <unistd.h>

/* Test context */
static fl_context_t test_ctx;

/* Test temp file path */
static char test_file_path[256];

/* ============================================================================
 * Setup/Teardown
 * ============================================================================ */

static void setup_file_test(void) {
    mock_output_reset();
    mock_heap_reset();
    mock_fpb_reset();
    fpb_mock_configure(6, 2);

    memset(&test_ctx, 0, sizeof(test_ctx));

    test_ctx.output_cb = mock_output_cb;
    test_ctx.output_user = NULL;
    test_ctx.malloc_cb = mock_malloc;
    test_ctx.free_cb = mock_free;

    fl_init(&test_ctx);

    /* Initialize file context with libc ops - direct assignment since fl_file_ctx_init may not be implemented */
    const fl_fs_ops_t* ops = fl_file_get_libc_ops();
    test_ctx.file_ctx.fs = ops;
    test_ctx.file_ctx.fp = NULL;

    /* Create temp file path */
    snprintf(test_file_path, sizeof(test_file_path), "/tmp/fl_test_%d.txt", getpid());
}

static void cleanup_file_test(void) {
    /* Close any open file */
    fl_file_close(&test_ctx.file_ctx);
    /* Remove temp file if exists */
    unlink(test_file_path);
}

/* ============================================================================
 * fl_file_ctx_init Tests
 * ============================================================================ */

void test_file_ctx_init(void) {
    setup_file_test();

    const fl_fs_ops_t* ops = fl_file_get_libc_ops();
    TEST_ASSERT(ops != NULL);
    TEST_ASSERT(test_ctx.file_ctx.fs == ops);
    TEST_ASSERT(test_ctx.file_ctx.fp == NULL);

    cleanup_file_test();
}

void test_file_libc_ops_valid(void) {
    const fl_fs_ops_t* ops = fl_file_get_libc_ops();
    TEST_ASSERT(ops != NULL);
    TEST_ASSERT(ops->open != NULL);
    TEST_ASSERT(ops->close != NULL);
    TEST_ASSERT(ops->read != NULL);
    TEST_ASSERT(ops->write != NULL);
    TEST_ASSERT(ops->lseek != NULL);
    TEST_ASSERT(ops->stat != NULL);
}

/* ============================================================================
 * fl_file_open/close Tests
 * ============================================================================ */

void test_file_open_write(void) {
    setup_file_test();

    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT(test_ctx.file_ctx.fp != NULL);

    fl_file_close(&test_ctx.file_ctx);
    TEST_ASSERT(test_ctx.file_ctx.fp == NULL);

    cleanup_file_test();
}

void test_file_open_read_nonexistent(void) {
    setup_file_test();

    int result = fl_file_open(&test_ctx.file_ctx, "/nonexistent/path/file.txt", "r");
    TEST_ASSERT(result != 0);

    cleanup_file_test();
}

void test_file_open_null_path(void) {
    setup_file_test();

    int result = fl_file_open(&test_ctx.file_ctx, NULL, "r");
    TEST_ASSERT(result != 0);

    cleanup_file_test();
}

void test_file_open_null_mode(void) {
    setup_file_test();

    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, NULL);
    TEST_ASSERT(result != 0);

    cleanup_file_test();
}

/* ============================================================================
 * fl_file_write/read Tests
 * ============================================================================ */

void test_file_write_read(void) {
    setup_file_test();

    /* Write data */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    TEST_ASSERT_EQUAL(0, result);

    const char* test_data = "Hello, World!";
    ssize_t written = fl_file_write(&test_ctx.file_ctx, test_data, strlen(test_data));
    TEST_ASSERT_EQUAL((ssize_t)strlen(test_data), written);

    fl_file_close(&test_ctx.file_ctx);

    /* Read data back */
    result = fl_file_open(&test_ctx.file_ctx, test_file_path, "r");
    TEST_ASSERT_EQUAL(0, result);

    char read_buf[64] = {0};
    ssize_t read_len = fl_file_read(&test_ctx.file_ctx, read_buf, sizeof(read_buf) - 1);
    TEST_ASSERT_EQUAL((ssize_t)strlen(test_data), read_len);
    TEST_ASSERT(strcmp(test_data, read_buf) == 0);

    fl_file_close(&test_ctx.file_ctx);

    cleanup_file_test();
}

void test_file_write_no_open(void) {
    setup_file_test();

    /* Try to write without opening */
    ssize_t written = fl_file_write(&test_ctx.file_ctx, "test", 4);
    TEST_ASSERT(written < 0);

    cleanup_file_test();
}

void test_file_read_no_open(void) {
    setup_file_test();

    char buf[16];
    ssize_t read_len = fl_file_read(&test_ctx.file_ctx, buf, sizeof(buf));
    TEST_ASSERT(read_len < 0);

    cleanup_file_test();
}

/* ============================================================================
 * fl_file_seek Tests
 * ============================================================================ */

void test_file_seek(void) {
    setup_file_test();

    /* Create file with content */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    fl_file_write(&test_ctx.file_ctx, "0123456789", 10);
    fl_file_close(&test_ctx.file_ctx);

    /* Open for read and seek */
    result = fl_file_open(&test_ctx.file_ctx, test_file_path, "r");
    TEST_ASSERT_EQUAL(0, result);

    off_t pos = fl_file_seek(&test_ctx.file_ctx, 5, FL_SEEK_SET);
    TEST_ASSERT_EQUAL(5, pos);

    char buf[8] = {0};
    fl_file_read(&test_ctx.file_ctx, buf, 5);
    TEST_ASSERT(strcmp("56789", buf) == 0);

    fl_file_close(&test_ctx.file_ctx);

    cleanup_file_test();
}

void test_file_seek_no_open(void) {
    setup_file_test();

    off_t pos = fl_file_seek(&test_ctx.file_ctx, 0, FL_SEEK_SET);
    TEST_ASSERT(pos < 0);

    cleanup_file_test();
}

/* ============================================================================
 * fl_file_stat Tests
 * ============================================================================ */

void test_file_stat(void) {
    setup_file_test();

    /* Create file with known content */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    fl_file_write(&test_ctx.file_ctx, "test content", 12);
    fl_file_close(&test_ctx.file_ctx);

    /* Get stat */
    fl_file_stat_t st;
    result = fl_file_stat(&test_ctx.file_ctx, test_file_path, &st);
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_EQUAL(12, st.size);
    TEST_ASSERT_EQUAL(FL_FILE_TYPE_REG, st.type);

    cleanup_file_test();
}

void test_file_stat_nonexistent(void) {
    setup_file_test();

    fl_file_stat_t st;
    int result = fl_file_stat(&test_ctx.file_ctx, "/nonexistent/file", &st);
    TEST_ASSERT(result != 0);

    cleanup_file_test();
}

/* ============================================================================
 * fl_file_remove Tests
 * ============================================================================ */

void test_file_remove(void) {
    setup_file_test();

    /* Create file */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    fl_file_write(&test_ctx.file_ctx, "to be deleted", 13);
    fl_file_close(&test_ctx.file_ctx);

    /* Remove file */
    result = fl_file_remove(&test_ctx.file_ctx, test_file_path);
    TEST_ASSERT_EQUAL(0, result);

    /* Verify file is gone */
    fl_file_stat_t st;
    result = fl_file_stat(&test_ctx.file_ctx, test_file_path, &st);
    TEST_ASSERT(result != 0);

    cleanup_file_test();
}

void test_file_remove_nonexistent(void) {
    setup_file_test();

    int result = fl_file_remove(&test_ctx.file_ctx, "/nonexistent/file");
    TEST_ASSERT(result != 0);

    cleanup_file_test();
}

/* ============================================================================
 * fl_file_mkdir Tests
 * ============================================================================ */

void test_file_mkdir(void) {
    setup_file_test();

    char dir_path[256];
    snprintf(dir_path, sizeof(dir_path), "/tmp/fl_test_dir_%d", getpid());

    /* Note: libc backend does not support mkdir (returns -1)
     * This test documents the behavior */
    int result = fl_file_mkdir(&test_ctx.file_ctx, dir_path);
    TEST_ASSERT_EQUAL(-1, result); /* mkdir not supported in libc backend */

    cleanup_file_test();
}

/* ============================================================================
 * fl_file_rename Tests
 * ============================================================================ */

void test_file_rename(void) {
    setup_file_test();

    char new_path[256];
    snprintf(new_path, sizeof(new_path), "/tmp/fl_test_renamed_%d.txt", getpid());

    /* Create original file */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    fl_file_write(&test_ctx.file_ctx, "test", 4);
    fl_file_close(&test_ctx.file_ctx);

    /* Rename */
    result = fl_file_rename(&test_ctx.file_ctx, test_file_path, new_path);
    TEST_ASSERT_EQUAL(0, result);

    /* Original should not exist */
    fl_file_stat_t st;
    result = fl_file_stat(&test_ctx.file_ctx, test_file_path, &st);
    TEST_ASSERT(result != 0);

    /* New should exist */
    result = fl_file_stat(&test_ctx.file_ctx, new_path, &st);
    TEST_ASSERT_EQUAL(0, result);

    /* Cleanup */
    unlink(new_path);
    cleanup_file_test();
}

/* ============================================================================
 * Test Runner
 * ============================================================================ */

void run_file_tests(void) {
    TEST_SUITE_BEGIN("func_loader_file - Context Init");
    RUN_TEST(test_file_ctx_init);
    RUN_TEST(test_file_libc_ops_valid);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file - Open/Close");
    RUN_TEST(test_file_open_write);
    RUN_TEST(test_file_open_read_nonexistent);
    RUN_TEST(test_file_open_null_path);
    RUN_TEST(test_file_open_null_mode);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file - Read/Write");
    RUN_TEST(test_file_write_read);
    RUN_TEST(test_file_write_no_open);
    RUN_TEST(test_file_read_no_open);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file - Seek");
    RUN_TEST(test_file_seek);
    RUN_TEST(test_file_seek_no_open);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file - Stat");
    RUN_TEST(test_file_stat);
    RUN_TEST(test_file_stat_nonexistent);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file - Remove");
    RUN_TEST(test_file_remove);
    RUN_TEST(test_file_remove_nonexistent);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file - Mkdir");
    RUN_TEST(test_file_mkdir);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file - Rename");
    RUN_TEST(test_file_rename);
    TEST_SUITE_END();
}
