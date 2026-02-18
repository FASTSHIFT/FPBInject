/*
 * MIT License
 * Copyright (c) 2024 _VIFEXTech
 *
 * Tests for func_loader_file_fatfs.c - FatFS backend
 */

#include "test_framework.h"
#include "mock_hardware.h"
#include "mock_fatfs.h"
#include "func_loader.h"
#include "func_loader_file.h"

#include <stdio.h>
#include <string.h>
#include <unistd.h>

/* Declare FatFS ops getter */
extern const fl_fs_ops_t* fl_file_get_fatfs_ops(void);

/* Test context */
static fl_context_t test_ctx;

/* Test temp file path */
static char test_file_path[256];

/* ============================================================================
 * Setup/Teardown
 * ============================================================================ */

static void setup_fatfs_test(void) {
    mock_output_reset();
    mock_heap_reset();
    mock_fatfs_reset();

    memset(&test_ctx, 0, sizeof(test_ctx));

    test_ctx.output_cb = mock_output_cb;
    test_ctx.output_user = NULL;
    test_ctx.malloc_cb = mock_malloc;
    test_ctx.free_cb = mock_free;

    fl_init(&test_ctx);

    /* Initialize file context with FatFS ops */
    const fl_fs_ops_t* ops = fl_file_get_fatfs_ops();
    test_ctx.file_ctx.fs = ops;
    test_ctx.file_ctx.fp = NULL;

    /* Create temp file path */
    snprintf(test_file_path, sizeof(test_file_path), "/tmp/fl_fatfs_test_%d.txt", getpid());
}

static void cleanup_fatfs_test(void) {
    fl_file_close(&test_ctx.file_ctx);
    unlink(test_file_path);
}

/* ============================================================================
 * FatFS Ops Validation Tests
 * ============================================================================ */

void test_fatfs_ops_valid(void) {
    const fl_fs_ops_t* ops = fl_file_get_fatfs_ops();
    TEST_ASSERT_NOT_NULL(ops);
    TEST_ASSERT_NOT_NULL(ops->open);
    TEST_ASSERT_NOT_NULL(ops->close);
    TEST_ASSERT_NOT_NULL(ops->read);
    TEST_ASSERT_NOT_NULL(ops->write);
    TEST_ASSERT_NOT_NULL(ops->lseek);
    TEST_ASSERT_NOT_NULL(ops->fsync);
    TEST_ASSERT_NOT_NULL(ops->stat);
    TEST_ASSERT_NOT_NULL(ops->opendir);
    TEST_ASSERT_NOT_NULL(ops->readdir);
    TEST_ASSERT_NOT_NULL(ops->closedir);
    TEST_ASSERT_NOT_NULL(ops->unlink);
    TEST_ASSERT_NOT_NULL(ops->mkdir);
    TEST_ASSERT_NOT_NULL(ops->rename);
}

/* ============================================================================
 * Open/Close Tests
 * ============================================================================ */

void test_fatfs_open_write(void) {
    setup_fatfs_test();

    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_NOT_NULL(test_ctx.file_ctx.fp);
    TEST_ASSERT_EQUAL(1, mock_fatfs_get_open_count());

    result = fl_file_close(&test_ctx.file_ctx);
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_NULL(test_ctx.file_ctx.fp);
    TEST_ASSERT_EQUAL(1, mock_fatfs_get_close_count());

    cleanup_fatfs_test();
}

void test_fatfs_open_read(void) {
    setup_fatfs_test();

    /* Create file first */
    FILE* f = fopen(test_file_path, "w");
    fprintf(f, "test");
    fclose(f);

    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "r");
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_NOT_NULL(test_ctx.file_ctx.fp);

    fl_file_close(&test_ctx.file_ctx);
    cleanup_fatfs_test();
}

void test_fatfs_open_nonexistent(void) {
    setup_fatfs_test();

    int result = fl_file_open(&test_ctx.file_ctx, "/nonexistent/path/file.txt", "r");
    TEST_ASSERT(result != 0);

    cleanup_fatfs_test();
}

void test_fatfs_open_fail_mock(void) {
    setup_fatfs_test();
    mock_fatfs_set_fail_open(1);

    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    TEST_ASSERT(result != 0);

    cleanup_fatfs_test();
}

void test_fatfs_open_null_params(void) {
    setup_fatfs_test();

    int result = fl_file_open(NULL, test_file_path, "w");
    TEST_ASSERT(result != 0);

    result = fl_file_open(&test_ctx.file_ctx, NULL, "w");
    TEST_ASSERT(result != 0);

    result = fl_file_open(&test_ctx.file_ctx, test_file_path, NULL);
    TEST_ASSERT(result != 0);

    cleanup_fatfs_test();
}

/* ============================================================================
 * Read/Write Tests
 * ============================================================================ */

void test_fatfs_write_read(void) {
    setup_fatfs_test();

    /* Write */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    TEST_ASSERT_EQUAL(0, result);

    const char* test_data = "Hello FatFS!";
    ssize_t written = fl_file_write(&test_ctx.file_ctx, test_data, strlen(test_data));
    TEST_ASSERT_EQUAL((ssize_t)strlen(test_data), written);
    TEST_ASSERT_EQUAL(1, mock_fatfs_get_write_count());

    fl_file_close(&test_ctx.file_ctx);

    /* Read back */
    result = fl_file_open(&test_ctx.file_ctx, test_file_path, "r");
    TEST_ASSERT_EQUAL(0, result);

    char buf[64] = {0};
    ssize_t nread = fl_file_read(&test_ctx.file_ctx, buf, sizeof(buf) - 1);
    TEST_ASSERT_EQUAL((ssize_t)strlen(test_data), nread);
    TEST_ASSERT_STR_EQUAL(test_data, buf);
    TEST_ASSERT_EQUAL(1, mock_fatfs_get_read_count());

    fl_file_close(&test_ctx.file_ctx);
    cleanup_fatfs_test();
}

void test_fatfs_write_fail_mock(void) {
    setup_fatfs_test();

    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    TEST_ASSERT_EQUAL(0, result);

    mock_fatfs_set_fail_write(1);
    ssize_t written = fl_file_write(&test_ctx.file_ctx, "test", 4);
    TEST_ASSERT(written < 0);

    fl_file_close(&test_ctx.file_ctx);
    cleanup_fatfs_test();
}

void test_fatfs_read_fail_mock(void) {
    setup_fatfs_test();

    /* Create file */
    FILE* f = fopen(test_file_path, "w");
    fprintf(f, "test data");
    fclose(f);

    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "r");
    TEST_ASSERT_EQUAL(0, result);

    mock_fatfs_set_fail_read(1);
    char buf[32];
    ssize_t nread = fl_file_read(&test_ctx.file_ctx, buf, sizeof(buf));
    TEST_ASSERT(nread < 0);

    fl_file_close(&test_ctx.file_ctx);
    cleanup_fatfs_test();
}

void test_fatfs_write_no_open(void) {
    setup_fatfs_test();

    ssize_t written = fl_file_write(&test_ctx.file_ctx, "test", 4);
    TEST_ASSERT(written < 0);

    cleanup_fatfs_test();
}

void test_fatfs_read_no_open(void) {
    setup_fatfs_test();

    char buf[16];
    ssize_t nread = fl_file_read(&test_ctx.file_ctx, buf, sizeof(buf));
    TEST_ASSERT(nread < 0);

    cleanup_fatfs_test();
}

/* ============================================================================
 * Seek Tests
 * ============================================================================ */

void test_fatfs_seek_set(void) {
    setup_fatfs_test();

    /* Create file */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    fl_file_write(&test_ctx.file_ctx, "0123456789", 10);
    fl_file_close(&test_ctx.file_ctx);

    /* Seek and read */
    result = fl_file_open(&test_ctx.file_ctx, test_file_path, "r");
    TEST_ASSERT_EQUAL(0, result);

    off_t pos = fl_file_seek(&test_ctx.file_ctx, 5, FL_SEEK_SET);
    TEST_ASSERT_EQUAL(5, pos);

    char buf[8] = {0};
    fl_file_read(&test_ctx.file_ctx, buf, 5);
    TEST_ASSERT_STR_EQUAL("56789", buf);

    fl_file_close(&test_ctx.file_ctx);
    cleanup_fatfs_test();
}

void test_fatfs_seek_cur(void) {
    setup_fatfs_test();

    /* Create file */
    fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    fl_file_write(&test_ctx.file_ctx, "0123456789", 10);
    fl_file_close(&test_ctx.file_ctx);

    /* Seek relative */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "r");
    TEST_ASSERT_EQUAL(0, result);
    fl_file_seek(&test_ctx.file_ctx, 3, FL_SEEK_SET);
    off_t pos = fl_file_seek(&test_ctx.file_ctx, 2, FL_SEEK_CUR);
    TEST_ASSERT_EQUAL(5, pos);

    fl_file_close(&test_ctx.file_ctx);
    cleanup_fatfs_test();
}

void test_fatfs_seek_end(void) {
    setup_fatfs_test();

    /* Create file */
    fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    fl_file_write(&test_ctx.file_ctx, "0123456789", 10);
    fl_file_close(&test_ctx.file_ctx);

    /* Seek from end */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "r");
    TEST_ASSERT_EQUAL(0, result);
    off_t pos = fl_file_seek(&test_ctx.file_ctx, -3, FL_SEEK_END);
    TEST_ASSERT_EQUAL(7, pos);

    char buf[5] = {0};
    fl_file_read(&test_ctx.file_ctx, buf, 3);
    TEST_ASSERT_STR_EQUAL("789", buf);

    fl_file_close(&test_ctx.file_ctx);
    cleanup_fatfs_test();
}

void test_fatfs_seek_no_open(void) {
    setup_fatfs_test();

    off_t pos = fl_file_seek(&test_ctx.file_ctx, 0, FL_SEEK_SET);
    TEST_ASSERT(pos < 0);

    cleanup_fatfs_test();
}

/* ============================================================================
 * Stat Tests
 * ============================================================================ */

void test_fatfs_stat(void) {
    setup_fatfs_test();

    /* Create file */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    fl_file_write(&test_ctx.file_ctx, "test content", 12);
    fl_file_close(&test_ctx.file_ctx);

    fl_file_stat_t st;
    result = fl_file_stat(&test_ctx.file_ctx, test_file_path, &st);
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_EQUAL(12, st.size);
    TEST_ASSERT_EQUAL(FL_FILE_TYPE_REG, st.type);

    cleanup_fatfs_test();
}

void test_fatfs_stat_dir(void) {
    setup_fatfs_test();

    fl_file_stat_t st;
    int result = fl_file_stat(&test_ctx.file_ctx, "/tmp", &st);
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_EQUAL(FL_FILE_TYPE_DIR, st.type);

    cleanup_fatfs_test();
}

void test_fatfs_stat_nonexistent(void) {
    setup_fatfs_test();

    fl_file_stat_t st;
    int result = fl_file_stat(&test_ctx.file_ctx, "/nonexistent/file", &st);
    TEST_ASSERT(result != 0);

    cleanup_fatfs_test();
}

void test_fatfs_stat_fail_mock(void) {
    setup_fatfs_test();
    mock_fatfs_set_fail_stat(1);

    fl_file_stat_t st;
    int result = fl_file_stat(&test_ctx.file_ctx, test_file_path, &st);
    TEST_ASSERT(result != 0);

    cleanup_fatfs_test();
}

/* ============================================================================
 * Directory Tests
 * ============================================================================ */

static int list_cb_counter(const fl_dirent_t* entry, void* user) {
    if (entry->name[0] != '.') {
        (*(int*)user)++;
    }
    return 0;
}

void test_fatfs_list_cb(void) {
    setup_fatfs_test();

    int entry_count = 0;
    int result = fl_file_list_cb(&test_ctx.file_ctx, "/tmp", list_cb_counter, &entry_count);
    TEST_ASSERT(result >= 0);

    cleanup_fatfs_test();
}

void test_fatfs_list_cb_null_params(void) {
    setup_fatfs_test();

    int result = fl_file_list_cb(NULL, "/tmp", NULL, NULL);
    TEST_ASSERT(result < 0);

    result = fl_file_list_cb(&test_ctx.file_ctx, NULL, NULL, NULL);
    TEST_ASSERT(result < 0);

    cleanup_fatfs_test();
}

/* ============================================================================
 * Remove Tests
 * ============================================================================ */

void test_fatfs_remove(void) {
    setup_fatfs_test();

    /* Create file */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    fl_file_write(&test_ctx.file_ctx, "to delete", 9);
    fl_file_close(&test_ctx.file_ctx);

    /* Remove */
    result = fl_file_remove(&test_ctx.file_ctx, test_file_path);
    TEST_ASSERT_EQUAL(0, result);

    /* Verify gone */
    fl_file_stat_t st;
    result = fl_file_stat(&test_ctx.file_ctx, test_file_path, &st);
    TEST_ASSERT(result != 0);

    cleanup_fatfs_test();
}

void test_fatfs_remove_nonexistent(void) {
    setup_fatfs_test();

    int result = fl_file_remove(&test_ctx.file_ctx, "/nonexistent/file");
    TEST_ASSERT(result != 0);

    cleanup_fatfs_test();
}

/* ============================================================================
 * Mkdir Tests
 * ============================================================================ */

void test_fatfs_mkdir(void) {
    setup_fatfs_test();

    char dir_path[256];
    snprintf(dir_path, sizeof(dir_path), "/tmp/fl_fatfs_dir_%d", getpid());

    int result = fl_file_mkdir(&test_ctx.file_ctx, dir_path);
    TEST_ASSERT_EQUAL(0, result);

    /* Verify exists */
    fl_file_stat_t st;
    result = fl_file_stat(&test_ctx.file_ctx, dir_path, &st);
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_EQUAL(FL_FILE_TYPE_DIR, st.type);

    /* Cleanup */
    rmdir(dir_path);
    cleanup_fatfs_test();
}

/* ============================================================================
 * Rename Tests
 * ============================================================================ */

void test_fatfs_rename(void) {
    setup_fatfs_test();

    char new_path[256];
    snprintf(new_path, sizeof(new_path), "/tmp/fl_fatfs_renamed_%d.txt", getpid());

    /* Create file */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    fl_file_write(&test_ctx.file_ctx, "test", 4);
    fl_file_close(&test_ctx.file_ctx);

    /* Rename */
    result = fl_file_rename(&test_ctx.file_ctx, test_file_path, new_path);
    TEST_ASSERT_EQUAL(0, result);

    /* Old should not exist */
    fl_file_stat_t st;
    result = fl_file_stat(&test_ctx.file_ctx, test_file_path, &st);
    TEST_ASSERT(result != 0);

    /* New should exist */
    result = fl_file_stat(&test_ctx.file_ctx, new_path, &st);
    TEST_ASSERT_EQUAL(0, result);

    unlink(new_path);
    cleanup_fatfs_test();
}

/* ============================================================================
 * Append Mode Test
 * ============================================================================ */

void test_fatfs_open_append(void) {
    setup_fatfs_test();

    /* Create with initial content */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    fl_file_write(&test_ctx.file_ctx, "Hello", 5);
    fl_file_close(&test_ctx.file_ctx);

    /* Append */
    result = fl_file_open(&test_ctx.file_ctx, test_file_path, "a");
    TEST_ASSERT_EQUAL(0, result);
    fl_file_write(&test_ctx.file_ctx, "World", 5);
    fl_file_close(&test_ctx.file_ctx);

    /* Verify */
    result = fl_file_open(&test_ctx.file_ctx, test_file_path, "r");
    char buf[20] = {0};
    fl_file_read(&test_ctx.file_ctx, buf, 10);
    TEST_ASSERT_STR_EQUAL("HelloWorld", buf);
    fl_file_close(&test_ctx.file_ctx);

    cleanup_fatfs_test();
}

/* ============================================================================
 * Large Data Tests
 * ============================================================================ */

void test_fatfs_write_large(void) {
    setup_fatfs_test();

    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    TEST_ASSERT_EQUAL(0, result);

    char large_data[2048];
    memset(large_data, 'X', sizeof(large_data));
    ssize_t written = fl_file_write(&test_ctx.file_ctx, large_data, sizeof(large_data));
    TEST_ASSERT_EQUAL(2048, written);

    fl_file_close(&test_ctx.file_ctx);
    cleanup_fatfs_test();
}

void test_fatfs_read_large(void) {
    setup_fatfs_test();

    /* Create large file */
    int result = fl_file_open(&test_ctx.file_ctx, test_file_path, "w");
    char large_data[2048];
    memset(large_data, 'Y', sizeof(large_data));
    fl_file_write(&test_ctx.file_ctx, large_data, sizeof(large_data));
    fl_file_close(&test_ctx.file_ctx);

    /* Read back */
    result = fl_file_open(&test_ctx.file_ctx, test_file_path, "r");
    TEST_ASSERT_EQUAL(0, result);

    char read_buf[2048];
    ssize_t nread = fl_file_read(&test_ctx.file_ctx, read_buf, sizeof(read_buf));
    TEST_ASSERT_EQUAL(2048, nread);
    TEST_ASSERT_EQUAL_MEMORY(large_data, read_buf, sizeof(large_data));

    fl_file_close(&test_ctx.file_ctx);
    cleanup_fatfs_test();
}

/* ============================================================================
 * Test Runner
 * ============================================================================ */

void run_fatfs_tests(void) {
    TEST_SUITE_BEGIN("func_loader_file_fatfs - Ops Validation");
    RUN_TEST(test_fatfs_ops_valid);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file_fatfs - Open/Close");
    RUN_TEST(test_fatfs_open_write);
    RUN_TEST(test_fatfs_open_read);
    RUN_TEST(test_fatfs_open_nonexistent);
    RUN_TEST(test_fatfs_open_fail_mock);
    RUN_TEST(test_fatfs_open_null_params);
    RUN_TEST(test_fatfs_open_append);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file_fatfs - Read/Write");
    RUN_TEST(test_fatfs_write_read);
    RUN_TEST(test_fatfs_write_fail_mock);
    RUN_TEST(test_fatfs_read_fail_mock);
    RUN_TEST(test_fatfs_write_no_open);
    RUN_TEST(test_fatfs_read_no_open);
    RUN_TEST(test_fatfs_write_large);
    RUN_TEST(test_fatfs_read_large);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file_fatfs - Seek");
    RUN_TEST(test_fatfs_seek_set);
    RUN_TEST(test_fatfs_seek_cur);
    RUN_TEST(test_fatfs_seek_end);
    RUN_TEST(test_fatfs_seek_no_open);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file_fatfs - Stat");
    RUN_TEST(test_fatfs_stat);
    RUN_TEST(test_fatfs_stat_dir);
    RUN_TEST(test_fatfs_stat_nonexistent);
    RUN_TEST(test_fatfs_stat_fail_mock);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file_fatfs - Directory");
    RUN_TEST(test_fatfs_list_cb);
    RUN_TEST(test_fatfs_list_cb_null_params);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file_fatfs - Remove");
    RUN_TEST(test_fatfs_remove);
    RUN_TEST(test_fatfs_remove_nonexistent);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file_fatfs - Mkdir");
    RUN_TEST(test_fatfs_mkdir);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_file_fatfs - Rename");
    RUN_TEST(test_fatfs_rename);
    TEST_SUITE_END();
}
