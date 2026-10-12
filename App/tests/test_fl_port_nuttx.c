/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Unit tests for the NuttX porting layer (fl_port_nuttx.c)
 *
 * The port source is #included here so its static functions (nuttx_exec_cb,
 * the output/cache callbacks) can be tested directly and its main() can be
 * driven end to end with a scripted stdin. The NuttX headers come from
 * Tools/nuttx_mock and the C library's system() is replaced by a mock, so
 * no shell is ever started. The target is compiled with
 * -D__NuttX__ -DCONFIG_SYSTEM_SYSTEM=1 (the setup in which the port installs
 * its exec callback).
 */
#include "test_framework.h"
#include "mock_hardware.h"
#include "fl_codec.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* ============================================================================
 * Mock system()
 * ============================================================================ */

static int g_system_calls;
static char g_system_cmd[1200];
static int g_system_ret;
static int g_system_errno;

int mock_system(const char* cmd);

int mock_system(const char* cmd) {
    g_system_calls++;
    snprintf(g_system_cmd, sizeof(g_system_cmd), "%s", cmd);
    if (g_system_ret < 0) {
        errno = g_system_errno;
    }
    return g_system_ret;
}

/* Pull in the port with system() redirected and its main() renamed */
#define system mock_system
#define main fl_port_main
#include "../func_loader/fl_port_nuttx.c"
#undef main
#undef system

/* ============================================================================
 * Helpers
 * ============================================================================ */

static void reset_system_mock(void) {
    g_system_calls = 0;
    g_system_cmd[0] = '\0';
    g_system_ret = 0;
    g_system_errno = 0;
}

static void put_le32(uint8_t* p, uint32_t v) {
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
    p[2] = (uint8_t)(v >> 16);
    p[3] = (uint8_t)(v >> 24);
}

static uint16_t request_crc(int32_t seq, uint32_t timeout, const char* cmd) {
    uint8_t hdr[12];
    put_le32(hdr, (uint32_t)seq);
    put_le32(hdr + 4, timeout);
    put_le32(hdr + 8, (uint32_t)strlen(cmd));
    return fl_crc16_base(fl_crc16_base(0xFFFF, hdr, sizeof(hdr)), cmd, strlen(cmd));
}

static uint16_t result_crc(int32_t seq, int32_t ret) {
    uint8_t b[8];
    put_le32(b, (uint32_t)seq);
    put_le32(b + 4, (uint32_t)ret);
    return fl_crc16_base(0xFFFF, b, sizeof(b));
}

/* Build one interactive-mode line: fl -c exec -d <b64> --seq N --timeout MS -r CRC */
static void exec_line(char* out, size_t size, const char* cmd, int seq, int timeout_ms) {
    char b64[512];
    fl_base64_encode((const uint8_t*)cmd, strlen(cmd), b64, sizeof(b64));
    snprintf(out, size, "fl -c exec -d %s --seq %d --timeout %d -r 0x%04X\n", b64, seq, timeout_ms,
             (unsigned)request_crc(seq, (uint32_t)timeout_ms, cmd));
}

static char g_capture[16384];

/* Run the port's main() with scripted stdin and capture everything it prints
 * to stdout in g_capture. Nothing is asserted while stdout is redirected. */
static int run_port(const char* stdin_text, int argc, char** argv) {
    char in_path[] = "/tmp/fl_port_in_XXXXXX";
    char out_path[] = "/tmp/fl_port_out_XXXXXX";

    int in_fd = mkstemp(in_path);
    int out_fd = mkstemp(out_path);
    if (in_fd < 0 || out_fd < 0) {
        g_capture[0] = '\0';
        return -999;
    }
    if (write(in_fd, stdin_text, strlen(stdin_text)) < 0) {
        close(in_fd);
        close(out_fd);
        return -998;
    }
    close(in_fd);

    fflush(stdout);
    int saved_stdout = dup(STDOUT_FILENO);
    dup2(out_fd, STDOUT_FILENO);
    close(out_fd);
    FILE* in = freopen(in_path, "r", stdin);

    int ret = in ? fl_port_main(argc, argv) : -997;

    fflush(stdout);
    dup2(saved_stdout, STDOUT_FILENO);
    close(saved_stdout);

    FILE* f = fopen(out_path, "r");
    size_t n = f ? fread(g_capture, 1, sizeof(g_capture) - 1, f) : 0;
    g_capture[n] = '\0';
    if (f) {
        fclose(f);
    }
    unlink(in_path);
    unlink(out_path);
    return ret;
}

static bool captured(const char* text) {
    return strstr(g_capture, text) != NULL;
}

static int run_lines(const char* stdin_text) {
    char* argv[] = {(char*)"fl"};
    return run_port(stdin_text, 1, argv);
}

/* ============================================================================
 * nuttx_exec_cb
 * ============================================================================ */

void test_exec_cb_passes_command_to_system(void) {
    reset_system_mock();

    int ret = nuttx_exec_cb(NULL, "ls -l /data", 0);

    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT_EQUAL(1, g_system_calls);
    TEST_ASSERT_STR_EQUAL("ls -l /data", g_system_cmd);
}

void test_exec_cb_returns_command_status(void) {
    reset_system_mock();
    g_system_ret = 3 << 8; /* what waitpid-style status looks like */

    TEST_ASSERT_EQUAL(3 << 8, nuttx_exec_cb(NULL, "false", 0));
}

void test_exec_cb_ignores_timeout(void) {
    reset_system_mock();
    g_system_ret = 5;

    /* v1 does not enforce the timeout: any value reaches system() unchanged
     * and does not change the outcome */
    TEST_ASSERT_EQUAL(5, nuttx_exec_cb(NULL, "sleep 1", 0));
    TEST_ASSERT_EQUAL(5, nuttx_exec_cb(NULL, "sleep 1", 1));
    TEST_ASSERT_EQUAL(5, nuttx_exec_cb(NULL, "sleep 1", 600000));
    TEST_ASSERT_EQUAL(3, g_system_calls);
}

void test_exec_cb_failure_returns_negative_errno(void) {
    reset_system_mock();
    g_system_ret = -1;
    g_system_errno = ENOMEM;

    TEST_ASSERT_EQUAL(-ENOMEM, nuttx_exec_cb(NULL, "ls", 0));

    g_system_errno = EAGAIN;
    TEST_ASSERT_EQUAL(-EAGAIN, nuttx_exec_cb(NULL, "ls", 0));
}

void test_exec_cb_failure_without_errno_falls_back_to_eio(void) {
    reset_system_mock();
    g_system_ret = -1;
    g_system_errno = 0;

    TEST_ASSERT_EQUAL(-EIO, nuttx_exec_cb(NULL, "ls", 0));
}

void test_exec_cb_user_pointer_is_unused(void) {
    reset_system_mock();
    int marker = 0;

    TEST_ASSERT_EQUAL(0, nuttx_exec_cb(&marker, "ls", 0));
    TEST_ASSERT_EQUAL(0, marker);
}

/* ============================================================================
 * Port wiring: main() / interactive mode
 * ============================================================================ */

void test_port_banner_and_exit_marker(void) {
    reset_system_mock();

    int ret = run_lines("quit\n");

    TEST_ASSERT_EQUAL(0, ret);
    TEST_ASSERT(captured("FPBInject Function Loader (NuttX)"));
    TEST_ASSERT(captured("Buffer: 1024 bytes"));
    TEST_ASSERT(captured("STATIC"));
    TEST_ASSERT(captured("[FLEXIT]"));
}

void test_port_info_reports_exec_enabled(void) {
    reset_system_mock();

    run_lines("fl -c info\nq\n");

    TEST_ASSERT(captured("Exec: enabled"));
    TEST_ASSERT(captured("Platform: NuttX"));
}

void test_port_exec_runs_command_through_system(void) {
    reset_system_mock();
    g_system_ret = 7;
    char line[1100];
    exec_line(line, sizeof(line), "echo \"a b\" > /tmp/x; cat $HOME", 5, 1500);
    char input[1200];
    snprintf(input, sizeof(input), "%squit\n", line);

    run_lines(input);

    TEST_ASSERT_EQUAL(1, g_system_calls);
    TEST_ASSERT_STR_EQUAL("echo \"a b\" > /tmp/x; cat $HOME", g_system_cmd);

    char start[64], result[96];
    snprintf(start, sizeof(start), "[FLEXEC] seq=5 crc=0x");
    snprintf(result, sizeof(result), "[FLOK] EXEC seq=5 ret=7 crc=0x%04X", (unsigned)result_crc(5, 7));
    TEST_ASSERT(captured(start));
    TEST_ASSERT(captured(result));
    /* start line comes before the result line */
    TEST_ASSERT(strstr(g_capture, start) < strstr(g_capture, result));
}

void test_port_exec_spawn_failure_reports_errno(void) {
    reset_system_mock();
    g_system_ret = -1;
    g_system_errno = ENOMEM;
    char line[1100];
    exec_line(line, sizeof(line), "ls", 6, 0);
    char input[1200];
    snprintf(input, sizeof(input), "%squit\n", line);

    run_lines(input);

    char result[96];
    snprintf(result, sizeof(result), "[FLERR] EXEC seq=6 ret=%d crc=0x%04X spawn failed", -ENOMEM,
             (unsigned)result_crc(6, -ENOMEM));
    TEST_ASSERT(captured(result));
}

void test_port_exec_repeat_is_not_run_twice(void) {
    reset_system_mock();
    char line[1100];
    exec_line(line, sizeof(line), "touch /a", 8, 0);
    char input[2300];
    snprintf(input, sizeof(input), "%s%squit\n", line, line);

    run_lines(input);

    TEST_ASSERT_EQUAL(1, g_system_calls);
    TEST_ASSERT(captured("replay=1"));
}

void test_port_first_command_from_argv(void) {
    reset_system_mock();
    char* argv[] = {(char*)"fl", (char*)"-c", (char*)"ping"};

    run_port("quit\n", 3, argv);

    TEST_ASSERT(captured("PONG"));
}

void test_port_first_command_error_is_reported(void) {
    reset_system_mock();
    char* argv[] = {(char*)"fl", (char*)"-c", (char*)"nosuchcmd"};

    run_port("quit\n", 3, argv);

    TEST_ASSERT(captured("Error: "));
    TEST_ASSERT(captured("[FLEXIT]"));
}

void test_port_unknown_command_prints_fl_error(void) {
    reset_system_mock();

    run_lines("bogus\n\nexit\n");

    TEST_ASSERT(captured("fl_error: "));
    TEST_ASSERT(captured("[FLEXIT]"));
}

void test_port_exit_marker_on_eof(void) {
    reset_system_mock();

    run_lines("");

    TEST_ASSERT(captured("[FLEXIT]"));
}

void test_port_alloc_and_upload_use_cache_callbacks(void) {
    reset_system_mock();

    run_lines("fl -c alloc -s 64\nfl -c upload -a 0 -d AQIDBA==\nquit\n");

    TEST_ASSERT(captured("Allocated 64"));
    TEST_ASSERT(captured("Uploaded 4 bytes"));
}

/* ============================================================================
 * Runner
 * ============================================================================ */

static void run_port_tests(void) {
    TEST_SUITE_BEGIN("fl_port_nuttx - nuttx_exec_cb");
    RUN_TEST(test_exec_cb_passes_command_to_system);
    RUN_TEST(test_exec_cb_returns_command_status);
    RUN_TEST(test_exec_cb_ignores_timeout);
    RUN_TEST(test_exec_cb_failure_returns_negative_errno);
    RUN_TEST(test_exec_cb_failure_without_errno_falls_back_to_eio);
    RUN_TEST(test_exec_cb_user_pointer_is_unused);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fl_port_nuttx - main / interactive mode");
    RUN_TEST(test_port_banner_and_exit_marker);
    RUN_TEST(test_port_info_reports_exec_enabled);
    RUN_TEST(test_port_exec_runs_command_through_system);
    RUN_TEST(test_port_exec_spawn_failure_reports_errno);
    RUN_TEST(test_port_exec_repeat_is_not_run_twice);
    RUN_TEST(test_port_first_command_from_argv);
    RUN_TEST(test_port_first_command_error_is_reported);
    RUN_TEST(test_port_unknown_command_prints_fl_error);
    RUN_TEST(test_port_exit_marker_on_eof);
    RUN_TEST(test_port_alloc_and_upload_use_cache_callbacks);
    TEST_SUITE_END();
}

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    printf("\n");
    printf("============================================================\n");
    printf("  FPBInject NuttX Port Unit Tests                           \n");
    printf("============================================================\n");
    printf("\n");

    test_framework_init();

    run_port_tests();

    return test_framework_report();
}
