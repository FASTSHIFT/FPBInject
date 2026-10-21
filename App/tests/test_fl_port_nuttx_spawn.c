/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Unit tests for the spawn flavour of the NuttX exec back-end
 * (fl_port_nuttx.c built with CONFIG_FPBINJECT_EXEC_INHERIT_PRIORITY)
 *
 * Same approach as test_fl_port_nuttx.c, which covers the system() flavour:
 * the port source is #included so nuttx_exec_cb() can be called directly and
 * main() driven with a scripted stdin. task_spawn(), waitpid(),
 * sched_getparam() and posix_spawnattr_setstacksize() are replaced by mocks, so
 * no task is ever created. The target is compiled with -D__NuttX__
 * -DCONFIG_FPBINJECT_EXEC_INHERIT_PRIORITY=1 -DCONFIG_NSH_LIBRARY=1 and, on purpose,
 * without CONFIG_SYSTEM_SYSTEM.
 */
#include "test_framework.h"
#include "mock_hardware.h"
#include "fl_codec.h"
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

/* ============================================================================
 * Mocks
 * ============================================================================ */
typedef int (*mock_main_t)(int argc, char* argv[]);

int nsh_system(int argc, char* argv[]) {
    (void)argc;
    (void)argv;
    return 0;
}

/* sched_getparam(): priority of the fl task */
static int g_fl_priority;
static int g_getparam_errno; /* != 0: fail with this errno */

/* posix_spawnattr_setstacksize() (NuttX only) */
static size_t g_stacksize;
static int g_setstack_err; /* != 0: fail with this error number */

/* task_spawn(): the nsh_system task */
static int g_spawn_calls;
static pid_t g_spawn_pid; /* returned: the child, or -errno */
static char g_spawn_name[32];
static mock_main_t g_spawn_entry;
static char g_spawn_arg0[32];
static char g_spawn_arg1[1200];
static bool g_spawn_arg2_null;
static int g_spawn_priority;
static short g_spawn_flags;
static size_t g_spawn_stacksize;

/* waitpid() */
static int g_wait_calls;
static pid_t g_wait_pid;
static int g_wait_options;
static int g_wait_errno; /* != 0: waitpid() fails with this errno */
static int g_child_status;

int mock_sched_getparam(pid_t pid, struct sched_param* param);
int mock_posix_spawnattr_setstacksize(posix_spawnattr_t* attr, size_t size);
int mock_task_spawn(const char* name, mock_main_t entry, const posix_spawn_file_actions_t* actions,
                    const posix_spawnattr_t* attr, char* const argv[], char* const envp[]);
pid_t mock_waitpid(pid_t pid, int* stat_loc, int options);

int mock_sched_getparam(pid_t pid, struct sched_param* param) {
    (void)pid;
    if (g_getparam_errno != 0) {
        errno = g_getparam_errno;
        return -1;
    }
    param->sched_priority = g_fl_priority;
    return 0;
}

int mock_posix_spawnattr_setstacksize(posix_spawnattr_t* attr, size_t size) {
    (void)attr;
    g_stacksize = size;
    return g_setstack_err;
}

int mock_task_spawn(const char* name, mock_main_t entry, const posix_spawn_file_actions_t* actions,
                    const posix_spawnattr_t* attr, char* const argv[], char* const envp[]) {
    (void)actions;
    (void)envp;
    g_spawn_calls++;
    snprintf(g_spawn_name, sizeof(g_spawn_name), "%s", name);
    g_spawn_entry = entry;
    snprintf(g_spawn_arg0, sizeof(g_spawn_arg0), "%s", argv[0]);
    snprintf(g_spawn_arg1, sizeof(g_spawn_arg1), "%s", argv[1]);
    g_spawn_arg2_null = argv[2] == NULL;
    struct sched_param param = {0};
    posix_spawnattr_getschedparam(attr, &param);
    g_spawn_priority = param.sched_priority;
    posix_spawnattr_getflags(attr, &g_spawn_flags);
    g_spawn_stacksize = g_stacksize;
    return g_spawn_pid;
}

pid_t mock_waitpid(pid_t pid, int* stat_loc, int options) {
    g_wait_calls++;
    g_wait_pid = pid;
    g_wait_options = options;
    if (g_wait_errno != 0) {
        errno = g_wait_errno;
        return -1;
    }
    if (stat_loc) {
        *stat_loc = g_child_status;
    }
    return pid;
}

/* Pull in the port with the system calls redirected and its main() renamed */
#define sched_getparam mock_sched_getparam
#define posix_spawnattr_setstacksize mock_posix_spawnattr_setstacksize
#define task_spawn mock_task_spawn
#define waitpid mock_waitpid
#define main fl_port_main
#include "../func_loader/fl_port_nuttx.c"
#undef main
#undef waitpid
#undef task_spawn
#undef posix_spawnattr_setstacksize
#undef sched_getparam

/* ============================================================================
 * Helpers
 * ============================================================================ */
static void reset_mocks(void) {
    g_fl_priority = 110;
    g_getparam_errno = 0;
    g_stacksize = 0;
    g_setstack_err = 0;
    g_spawn_calls = 0;
    g_spawn_pid = 4343;
    g_spawn_name[0] = '\0';
    g_spawn_entry = NULL;
    g_spawn_arg0[0] = '\0';
    g_spawn_arg1[0] = '\0';
    g_spawn_arg2_null = false;
    g_spawn_priority = -1;
    g_spawn_flags = 0;
    g_spawn_stacksize = 0;
    g_wait_calls = 0;
    g_wait_pid = 0;
    g_wait_options = -1;
    g_wait_errno = 0;
    g_child_status = 0;
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

static void exec_line(char* out, size_t size, const char* cmd, int seq, int timeout_ms) {
    char b64[512];
    fl_base64_encode((const uint8_t*)cmd, strlen(cmd), b64, sizeof(b64));
    snprintf(out, size, "fl -c exec -d %s --seq %d --timeout %d -r 0x%04X\n", b64, seq, timeout_ms,
             (unsigned)request_crc(seq, (uint32_t)timeout_ms, cmd));
}

static char g_capture[16384];

/* Run the port's main() with scripted stdin and capture what it prints */
static int run_port(const char* stdin_text, int argc, char** argv) {
    char in_path[] = "/tmp/fl_port_spawn_in_XXXXXX";
    char out_path[] = "/tmp/fl_port_spawn_out_XXXXXX";
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
 * What is spawned
 * ============================================================================ */
void test_command_line_is_run_by_an_nsh_system_task(void) {
    reset_mocks();
    TEST_ASSERT_EQUAL(0, nuttx_exec_cb(NULL, "ls -l /data", 0));
    TEST_ASSERT_EQUAL(1, g_spawn_calls);
    TEST_ASSERT_STR_EQUAL("flexec", g_spawn_name);
    TEST_ASSERT(g_spawn_entry == nsh_system);
    TEST_ASSERT_STR_EQUAL("-c", g_spawn_arg0);
    TEST_ASSERT_STR_EQUAL("ls -l /data", g_spawn_arg1);
    TEST_ASSERT_TRUE(g_spawn_arg2_null);
    TEST_ASSERT_EQUAL(4343, g_wait_pid);
}

void test_every_line_goes_to_the_shell_unchanged(void) {
    const char* lines[]
        = {"ping 10.0.0.1", "echo a | grep a", "echo \"a b\" > /tmp/x; cat $HOME", "  ps  ", "FOO=1 free"};
    for (size_t i = 0; i < sizeof(lines) / sizeof(lines[0]); i++) {
        reset_mocks();
        nuttx_exec_cb(NULL, lines[i], 0);
        TEST_ASSERT_EQUAL(1, g_spawn_calls);
        TEST_ASSERT_STR_EQUAL(lines[i], g_spawn_arg1);
    }
}

void test_task_inherits_the_priority_of_the_fl_task(void) {
    reset_mocks();
    g_fl_priority = 110;
    nuttx_exec_cb(NULL, "ls", 0);
    TEST_ASSERT_EQUAL(110, g_spawn_priority);
    TEST_ASSERT(g_spawn_flags & POSIX_SPAWN_SETSCHEDPARAM);

    reset_mocks();
    g_fl_priority = 87;
    nuttx_exec_cb(NULL, "ls", 0);
    TEST_ASSERT_EQUAL(87, g_spawn_priority);
}

void test_task_uses_the_configured_stack_size(void) {
    reset_mocks();
    nuttx_exec_cb(NULL, "ls", 0);
    TEST_ASSERT_EQUAL(2048, g_spawn_stacksize);
}

/* ============================================================================
 * Result, timeout, failures
 * ============================================================================ */
void test_status_is_the_raw_wait_status_like_system(void) {
    reset_mocks();
    g_child_status = 3 << 8;
    TEST_ASSERT_EQUAL(3 << 8, nuttx_exec_cb(NULL, "false", 0));
    TEST_ASSERT_EQUAL(1, g_wait_calls);
    TEST_ASSERT_EQUAL(0, g_wait_options); /* blocking */
}

void test_timeout_is_accepted_but_not_enforced(void) {
    reset_mocks();
    g_child_status = 9;
    TEST_ASSERT_EQUAL(9, nuttx_exec_cb(NULL, "sleep 1", 1));
    TEST_ASSERT_EQUAL(1, g_wait_calls);
    TEST_ASSERT_EQUAL(0, g_wait_options); /* still a blocking wait */
}

void test_user_pointer_is_unused(void) {
    reset_mocks();
    int marker = 0;
    TEST_ASSERT_EQUAL(0, nuttx_exec_cb(&marker, "ls", 0));
    TEST_ASSERT_EQUAL(0, marker);
}

void test_task_spawn_failure_returns_its_negative_errno(void) {
    reset_mocks();
    g_spawn_pid = -ENOMEM;
    TEST_ASSERT_EQUAL(-ENOMEM, nuttx_exec_cb(NULL, "ls", 0));
    TEST_ASSERT_EQUAL(0, g_wait_calls);
}

void test_getparam_failure_stops_before_spawning(void) {
    reset_mocks();
    g_getparam_errno = EPERM;
    TEST_ASSERT_EQUAL(-EPERM, nuttx_exec_cb(NULL, "ls", 0));
    TEST_ASSERT_EQUAL(0, g_spawn_calls);
}

void test_stack_size_failure_stops_before_spawning(void) {
    reset_mocks();
    g_setstack_err = EINVAL;
    TEST_ASSERT_EQUAL(-EINVAL, nuttx_exec_cb(NULL, "ls", 0));
    TEST_ASSERT_EQUAL(0, g_spawn_calls);
    TEST_ASSERT_EQUAL(0, g_wait_calls);
}

void test_waitpid_failure_is_reported(void) {
    reset_mocks();
    g_wait_errno = ECHILD;
    TEST_ASSERT_EQUAL(-ECHILD, nuttx_exec_cb(NULL, "ls", 0));
}

/* ============================================================================
 * Port wiring: exec_cb is installed without CONFIG_SYSTEM_SYSTEM
 * ============================================================================ */
void test_port_info_reports_exec_enabled(void) {
    reset_mocks();
    run_lines("fl -c info\nq\n");
    TEST_ASSERT(captured("Exec: enabled"));
}

void test_port_exec_runs_the_command_and_reports_the_status(void) {
    reset_mocks();
    g_child_status = 7 << 8;
    char line[1100];
    exec_line(line, sizeof(line), "echo \"a b\" > /tmp/x; cat $HOME", 5, 1500);
    char input[1200];
    snprintf(input, sizeof(input), "%squit\n", line);
    run_lines(input);

    TEST_ASSERT_EQUAL(1, g_spawn_calls);
    TEST_ASSERT_STR_EQUAL("echo \"a b\" > /tmp/x; cat $HOME", g_spawn_arg1);
    char result[96];
    snprintf(result, sizeof(result), "[FLOK] EXEC seq=5 ret=%d crc=0x%04X", 7 << 8, (unsigned)result_crc(5, 7 << 8));
    TEST_ASSERT(captured("[FLEXEC] seq=5 crc=0x"));
    TEST_ASSERT(captured(result));
    /* start line comes before the result line */
    TEST_ASSERT(strstr(g_capture, "[FLEXEC] seq=5") < strstr(g_capture, result));
}

void test_port_exec_spawn_failure_reports_errno(void) {
    reset_mocks();
    g_spawn_pid = -ENOMEM;
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
    reset_mocks();
    char line[1100];
    exec_line(line, sizeof(line), "touch /a", 8, 0);
    char input[2300];
    snprintf(input, sizeof(input), "%s%squit\n", line, line);
    run_lines(input);
    TEST_ASSERT_EQUAL(1, g_spawn_calls);
    TEST_ASSERT(captured("replay=1"));
}

/* ============================================================================
 * Runner
 * ============================================================================ */
static void run_spawn_tests(void) {
    TEST_SUITE_BEGIN("fl_port_nuttx spawn - what is spawned");
    RUN_TEST(test_command_line_is_run_by_an_nsh_system_task);
    RUN_TEST(test_every_line_goes_to_the_shell_unchanged);
    RUN_TEST(test_task_inherits_the_priority_of_the_fl_task);
    RUN_TEST(test_task_uses_the_configured_stack_size);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fl_port_nuttx spawn - result and failures");
    RUN_TEST(test_status_is_the_raw_wait_status_like_system);
    RUN_TEST(test_timeout_is_accepted_but_not_enforced);
    RUN_TEST(test_user_pointer_is_unused);
    RUN_TEST(test_task_spawn_failure_returns_its_negative_errno);
    RUN_TEST(test_getparam_failure_stops_before_spawning);
    RUN_TEST(test_stack_size_failure_stops_before_spawning);
    RUN_TEST(test_waitpid_failure_is_reported);
    TEST_SUITE_END();

    TEST_SUITE_BEGIN("fl_port_nuttx spawn - port wiring");
    RUN_TEST(test_port_info_reports_exec_enabled);
    RUN_TEST(test_port_exec_runs_the_command_and_reports_the_status);
    RUN_TEST(test_port_exec_spawn_failure_reports_errno);
    RUN_TEST(test_port_exec_repeat_is_not_run_twice);
    TEST_SUITE_END();
}

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    printf("\n");
    printf("============================================================\n");
    printf("  FPBInject NuttX Port (exec spawn) Unit Tests              \n");
    printf("============================================================\n");
    printf("\n");

    test_framework_init();
    run_spawn_tests();

    return test_framework_report();
}
