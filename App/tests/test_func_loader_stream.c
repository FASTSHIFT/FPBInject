/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Tests for func_loader_stream.c - Serial stream processing
 */

#include "test_framework.h"
#include "mock_hardware.h"
#include "stubs.h"

/* Test context and stream */
static fl_context_t test_ctx;
static fl_stream_t test_stream;

/* ============================================================================
 * Setup/Teardown
 * ============================================================================ */

static void setup_stream(void) {
    mock_output_reset();
    mock_serial_reset();
    mock_heap_reset();
    memset(&test_ctx, 0, sizeof(test_ctx));
    memset(&test_stream, 0, sizeof(test_stream));

    test_ctx.output_cb = mock_output_cb;
    test_ctx.output_user = NULL;
    test_ctx.malloc_cb = mock_malloc;
    test_ctx.free_cb = mock_free;

    fl_init(&test_ctx);
}

/* ============================================================================
 * fl_stream_init Tests
 * ============================================================================ */

void test_stream_init_basic(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    TEST_ASSERT_EQUAL(&test_ctx, test_stream.ctx);
    TEST_ASSERT_EQUAL(0, test_stream.buf_len);
}

void test_stream_init_clears_buffer(void) {
    setup_stream();

    /* Pre-fill buffer */
    memset(test_stream.buf, 'X', sizeof(test_stream.buf));
    test_stream.buf_len = 100;

    fl_stream_init(&test_stream, &test_ctx);

    TEST_ASSERT_EQUAL(0, test_stream.buf_len);
}

void test_stream_init_null_ctx(void) {
    setup_stream();

    /* Should handle NULL gracefully or set ctx to NULL */
    fl_stream_init(&test_stream, NULL);
    TEST_ASSERT_EQUAL(NULL, test_stream.ctx);
}

/* ============================================================================
 * fl_stream_process Tests - Basic Processing
 * ============================================================================ */

void test_stream_process_empty(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Process empty string */
    int result = fl_stream_process(&test_stream, "", 0);

    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_EQUAL(0, test_stream.buf_len);
}

void test_stream_process_partial_line(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Process partial line (no newline) */
    const char* data = "hel";
    int result = fl_stream_process(&test_stream, data, 3);

    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_EQUAL(3, test_stream.buf_len);
    TEST_ASSERT(memcmp(test_stream.buf, "hel", 3) == 0);
}

void test_stream_process_complete_line(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Process complete line with newline */
    const char* data = "help\n";
    int result = fl_stream_process(&test_stream, data, 5);

    /* Should have executed the command and cleared buffer */
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_EQUAL(0, test_stream.buf_len);
}

void test_stream_process_crlf(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Process line with CRLF */
    const char* data = "info\r\n";
    int result = fl_stream_process(&test_stream, data, 6);

    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_EQUAL(0, test_stream.buf_len);
}

void test_stream_process_multiple_lines(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Process multiple lines at once */
    const char* data = "help\ninfo\n";
    int result = fl_stream_process(&test_stream, data, 10);

    /* Both commands should be executed, buffer cleared */
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_EQUAL(0, test_stream.buf_len);
}

void test_stream_process_split_line(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* First part of line */
    fl_stream_process(&test_stream, "he", 2);
    TEST_ASSERT_EQUAL(2, test_stream.buf_len);

    /* Second part with newline */
    fl_stream_process(&test_stream, "lp\n", 3);
    TEST_ASSERT_EQUAL(0, test_stream.buf_len);
}

/* ============================================================================
 * fl_stream_process Tests - Buffer Management
 * ============================================================================ */

void test_stream_buffer_overflow(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Fill buffer to near capacity */
    char long_data[FL_STREAM_BUF_SIZE + 10];
    memset(long_data, 'A', sizeof(long_data));

    /* Should handle overflow gracefully */
    int result = fl_stream_process(&test_stream, long_data, FL_STREAM_BUF_SIZE - 1);

    /* Buffer should be at limit */
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT(test_stream.buf_len <= FL_STREAM_BUF_SIZE);
}

void test_stream_buffer_reset_after_line(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Add data then complete line */
    fl_stream_process(&test_stream, "test", 4);
    TEST_ASSERT_EQUAL(4, test_stream.buf_len);

    fl_stream_process(&test_stream, "\n", 1);
    TEST_ASSERT_EQUAL(0, test_stream.buf_len);
}

/* ============================================================================
 * fl_stream_exec_line Tests
 * ============================================================================ */

void test_stream_exec_line_simple(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Manually prepare buffer */
    strcpy(test_stream.buf, "help");
    test_stream.buf_len = 4;

    int result = fl_stream_exec_line(&test_stream);

    TEST_ASSERT_EQUAL(0, result);
}

void test_stream_exec_line_with_args(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Command with arguments */
    strcpy(test_stream.buf, "clear 0");
    test_stream.buf_len = 7;

    int result = fl_stream_exec_line(&test_stream);

    /* Should parse and execute with args */
    TEST_ASSERT_EQUAL(0, result);
}

void test_stream_exec_line_empty(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Empty line */
    test_stream.buf[0] = '\0';
    test_stream.buf_len = 0;

    int result = fl_stream_exec_line(&test_stream);

    /* Empty should be OK */
    TEST_ASSERT_EQUAL(0, result);
}

void test_stream_exec_line_whitespace(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Whitespace only */
    strcpy(test_stream.buf, "   ");
    test_stream.buf_len = 3;

    int result = fl_stream_exec_line(&test_stream);

    /* Should handle gracefully */
    TEST_ASSERT_EQUAL(0, result);
}

/* ============================================================================
 * Edge Cases
 * ============================================================================ */

void test_stream_null_data(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Null data with zero length should be OK */
    int result = fl_stream_process(&test_stream, NULL, 0);

    TEST_ASSERT_EQUAL(0, result);
}

void test_stream_special_chars(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Special characters in data */
    const char* data = "test\t123\n";
    int result = fl_stream_process(&test_stream, data, 9);

    /* Should process without crash */
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_EQUAL(0, test_stream.buf_len);
}

void test_stream_binary_data(void) {
    setup_stream();
    fl_stream_init(&test_stream, &test_ctx);

    /* Binary data (with null in middle) */
    char data[] = {'a', 'b', 0, 'c', '\n'};
    int result = fl_stream_process(&test_stream, data, 5);

    /* Should handle binary data */
    TEST_ASSERT_EQUAL(0, result);
    TEST_ASSERT_EQUAL(0, test_stream.buf_len);
}

/* ============================================================================
 * Test Runner
 * ============================================================================ */

void run_loader_stream_tests(void) {
    TEST_SUITE_BEGIN("func_loader_stream - Initialization");
    RUN_TEST(test_stream_init_basic);
    RUN_TEST(test_stream_init_clears_buffer);
    RUN_TEST(test_stream_init_null_ctx);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_stream - Basic Processing");
    RUN_TEST(test_stream_process_empty);
    RUN_TEST(test_stream_process_partial_line);
    RUN_TEST(test_stream_process_complete_line);
    RUN_TEST(test_stream_process_crlf);
    RUN_TEST(test_stream_process_multiple_lines);
    RUN_TEST(test_stream_process_split_line);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_stream - Buffer Management");
    RUN_TEST(test_stream_buffer_overflow);
    RUN_TEST(test_stream_buffer_reset_after_line);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_stream - Line Execution");
    RUN_TEST(test_stream_exec_line_simple);
    RUN_TEST(test_stream_exec_line_with_args);
    RUN_TEST(test_stream_exec_line_empty);
    RUN_TEST(test_stream_exec_line_whitespace);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_stream - Edge Cases");
    RUN_TEST(test_stream_null_data);
    RUN_TEST(test_stream_special_chars);
    RUN_TEST(test_stream_binary_data);
    TEST_SUITE_END();
}
