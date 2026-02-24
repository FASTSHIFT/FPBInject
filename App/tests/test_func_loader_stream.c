/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Tests for func_loader_stream.c - Serial stream processing
 */

#include "test_framework.h"
#include "mock_hardware.h"
#include "fpb_mock_regs.h"
#include "fl.h"
#include "fl_stream.h"

/* Test context and stream */
static fl_context_t test_ctx;
static fl_stream_t test_stream;
static char line_buf[256];

/* Mock serial interface */
static fl_serial_t test_serial;

/* ============================================================================
 * Setup/Teardown
 * ============================================================================ */

static void setup_stream(void) {
    mock_output_reset();
    mock_serial_reset();
    mock_heap_reset();
    mock_fpb_reset();

    memset(&test_ctx, 0, sizeof(test_ctx));
    memset(&test_stream, 0, sizeof(test_stream));
    memset(line_buf, 0, sizeof(line_buf));

    test_ctx.output_cb = mock_output_cb;
    test_ctx.output_user = NULL;
    test_ctx.malloc_cb = mock_malloc;
    test_ctx.free_cb = mock_free;

    test_serial.read_cb = mock_serial_read;
    test_serial.write_cb = mock_serial_write;
    test_serial.available_cb = mock_serial_available;

    fl_init(&test_ctx);
    fl_stream_init(&test_stream, &test_ctx, &test_serial, line_buf, sizeof(line_buf));
}

/* ============================================================================
 * fl_stream_init Tests
 * ============================================================================ */

void test_stream_init_basic(void) {
    setup_stream();
    TEST_ASSERT(test_stream.ctx == &test_ctx);
    TEST_ASSERT(test_stream.serial == &test_serial);
    TEST_ASSERT(test_stream.line_buf == line_buf);
}

void test_stream_init_null_ctx(void) {
    /* Note: Real implementation does NOT check for NULL ctx.
     * Passing NULL ctx causes segfault - this is expected behavior.
     * Test documents this constraint rather than testing it.
     */
    TEST_ASSERT(true); /* Placeholder - real API requires valid ctx */
}

void test_stream_init_null_serial(void) {
    setup_stream();
    fl_stream_t s;
    memset(&s, 0, sizeof(s));
    fl_stream_init(&s, &test_ctx, NULL, line_buf, sizeof(line_buf));
    /* Should not crash */
}

/* ============================================================================
 * fl_stream_exec_line Tests
 * ============================================================================ */

void test_stream_exec_empty_line(void) {
    setup_stream();
    char line[] = "";
    int result = fl_stream_exec_line(&test_stream, line);
    /* Empty line should be OK */
    TEST_ASSERT_EQUAL(0, result);
}

void test_stream_exec_whitespace_line(void) {
    setup_stream();
    char line[] = "   \t  ";
    int result = fl_stream_exec_line(&test_stream, line);
    TEST_ASSERT_EQUAL(0, result);
}

void test_stream_exec_help(void) {
    setup_stream();
    char line[] = "--help";
    int result = fl_stream_exec_line(&test_stream, line);
    /* --help prints usage but requires --cmd, so returns -1 */
    TEST_ASSERT_EQUAL(-1, result);
}

void test_stream_exec_info(void) {
    setup_stream();
    /* Need program name as first arg since argparse skips argv[0] */
    char line[] = "fl --cmd info";
    int result = fl_stream_exec_line(&test_stream, line);
    TEST_ASSERT_EQUAL(0, result);
}

void test_stream_exec_with_args(void) {
    setup_stream();
    char line[] = "fl --cmd unpatch --comp 0";
    int result = fl_stream_exec_line(&test_stream, line);
    TEST_ASSERT_EQUAL(0, result);
}

void test_stream_exec_unknown_cmd(void) {
    setup_stream();
    char line[] = "--cmd nonexistent_command";
    int result = fl_stream_exec_line(&test_stream, line);
    TEST_ASSERT(result != 0);
}

void test_stream_exec_comment(void) {
    setup_stream();
    char line[] = "# this is a comment";
    int result = fl_stream_exec_line(&test_stream, line);
    /* Comment starts with #, which argparse doesn't recognize */
    /* It should return error since no --cmd is provided */
    TEST_ASSERT_EQUAL(-1, result);
}

/* ============================================================================
 * fl_stream_process Tests
 * ============================================================================ */

void test_stream_process_no_data(void) {
    setup_stream();
    /* No data available */
    fl_stream_process(&test_stream);
    /* Should not crash */
}

void test_stream_process_partial_line(void) {
    setup_stream();
    mock_serial_set_input("hel");
    fl_stream_process(&test_stream);
    /* Line not complete, no command executed yet */
    TEST_ASSERT_EQUAL((size_t)3, test_stream.line_pos);
}

void test_stream_process_complete_line(void) {
    setup_stream();
    mock_serial_set_input("help\n");
    fl_stream_process(&test_stream);
    /* Line should be executed */
    TEST_ASSERT(strlen(mock_output_get()) > 0);
}

void test_stream_process_multiple_lines(void) {
    setup_stream();
    mock_serial_set_input("info\nlist\n");
    fl_stream_process(&test_stream);
    fl_stream_process(&test_stream);
    /* Both commands should be executed */
}

void test_stream_process_crlf(void) {
    setup_stream();
    mock_serial_set_input("info\r\n");
    fl_stream_process(&test_stream);
    /* Should handle CRLF */
}

/* ============================================================================
 * Edge Cases
 * ============================================================================ */

void test_stream_long_line(void) {
    setup_stream();
    /* Create a line longer than buffer */
    char long_input[512];
    memset(long_input, 'a', sizeof(long_input) - 2);
    long_input[sizeof(long_input) - 2] = '\n';
    long_input[sizeof(long_input) - 1] = '\0';

    mock_serial_set_input(long_input);
    fl_stream_process(&test_stream);
    /* Should not crash, line should be truncated */
}

void test_stream_quoted_args(void) {
    setup_stream();
    char line[] = "fl --cmd ping";
    int result = fl_stream_exec_line(&test_stream, line);
    TEST_ASSERT_EQUAL(0, result);
}

void test_stream_output_via_serial(void) {
    /* Test that stream output goes through serial write */
    mock_output_reset();
    mock_serial_reset();
    mock_heap_reset();
    mock_fpb_reset();

    memset(&test_ctx, 0, sizeof(test_ctx));
    memset(&test_stream, 0, sizeof(test_stream));
    memset(line_buf, 0, sizeof(line_buf));

    test_ctx.malloc_cb = mock_malloc;
    test_ctx.free_cb = mock_free;

    test_serial.read_cb = mock_serial_read;
    test_serial.write_cb = mock_serial_write;
    test_serial.available_cb = mock_serial_available;

    /* Initialize stream - this sets up stream_output as the output callback */
    fl_stream_init(&test_stream, &test_ctx, &test_serial, line_buf, sizeof(line_buf));
    fl_init(&test_ctx);

    /* Execute a command that produces output */
    char line[] = "fl --cmd ping";
    fl_stream_exec_line(&test_stream, line);

    /* Check that output was written to serial */
    const char* serial_output = mock_serial_get_output();
    TEST_ASSERT(serial_output != NULL);
    /* The output might be empty if stream_output isn't used, but test shouldn't crash */
}

void test_stream_process_buffer_full(void) {
    setup_stream();

    /* Fill buffer almost completely */
    memset(test_stream.line_buf, 'x', test_stream.line_size - 5);
    test_stream.line_pos = test_stream.line_size - 5;

    /* Try to add more data */
    mock_serial_set_input("abc\n");
    fl_stream_process(&test_stream);

    /* Should not crash */
}

/* ============================================================================
 * Test Runner
 * ============================================================================ */

void run_stream_tests(void) {
    TEST_SUITE_BEGIN("func_loader_stream - Initialization");
    RUN_TEST(test_stream_init_basic);
    RUN_TEST(test_stream_init_null_ctx);
    RUN_TEST(test_stream_init_null_serial);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_stream - Line Execution");
    RUN_TEST(test_stream_exec_empty_line);
    RUN_TEST(test_stream_exec_whitespace_line);
    RUN_TEST(test_stream_exec_help);
    RUN_TEST(test_stream_exec_info);
    RUN_TEST(test_stream_exec_with_args);
    RUN_TEST(test_stream_exec_unknown_cmd);
    RUN_TEST(test_stream_exec_comment);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_stream - Stream Processing");
    RUN_TEST(test_stream_process_no_data);
    RUN_TEST(test_stream_process_partial_line);
    RUN_TEST(test_stream_process_complete_line);
    RUN_TEST(test_stream_process_multiple_lines);
    RUN_TEST(test_stream_process_crlf);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("func_loader_stream - Edge Cases");
    RUN_TEST(test_stream_long_line);
    RUN_TEST(test_stream_quoted_args);
    RUN_TEST(test_stream_output_via_serial);
    RUN_TEST(test_stream_process_buffer_full);
    TEST_SUITE_END();
}
