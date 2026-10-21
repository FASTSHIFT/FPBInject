/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

/**
 * @file   func_loader_port_nuttx.c
 * @brief  NuttX porting layer
 *
 * Register as NSH builtin command.
 *
 * Kconfig example:
 *   config FPBINJECT_FL
 *       tristate "FPBInject Function Loader"
 *       default n
 *       ---help---
 *           FPB-based runtime code injection tool.
 *
 * Make.defs example:
 *   ifneq ($(CONFIG_FPBINJECT_FL),)
 *   PROGNAME = fl
 *   PRIORITY = SCHED_PRIORITY_DEFAULT
 *   STACKSIZE = 4096
 *   MODULE = $(CONFIG_FPBINJECT_FL)
 *   endif
 *
 * Usage:
 *   nsh> fl --cmd ping
 *   nsh> fl --cmd info
 *   nsh> fl   # interactive mode
 *
 * Exec back-end (the "exec" command runs a shell command line), chosen at
 * build time. With neither available exec_cb stays NULL ("No exec_cb").
 *   CONFIG_FPBINJECT_EXEC_INHERIT_PRIORITY=y (Kconfig default)
 *                            task_spawn(nsh_system) with the priority of the
 *                            fl task. Needs CONFIG_NSH_LIBRARY, CONFIG_SCHED_WAITPID
 *                            and a build that is not CONFIG_BUILD_KERNEL
 *                            (task_spawn); the Kconfig option depends on all of
 *                            them. Not CONFIG_SYSTEM_SYSTEM.
 *   CONFIG_FPBINJECT_EXEC_INHERIT_PRIORITY=n
 *                            system(): needs CONFIG_SYSTEM_SYSTEM. Its shell
 *                            task runs at CONFIG_SYSTEM_SYSTEM_PRIORITY.
 * Neither back-end enforces timeout_ms.
 */

#ifdef __NuttX__

#include "fl.h"
#include "fl_stream.h"
#include <nuttx/config.h>
#include <nuttx/cache.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

/* Exec back-end switch (Kconfig FPBINJECT_EXEC_INHERIT_PRIORITY). The macros can
 * also be given on the command line, which is what the host tests do. */
#ifndef FL_NUTTX_EXEC_INHERIT_PRIORITY
#ifdef CONFIG_FPBINJECT_EXEC_INHERIT_PRIORITY
#define FL_NUTTX_EXEC_INHERIT_PRIORITY 1
#else
#define FL_NUTTX_EXEC_INHERIT_PRIORITY 0
#endif
#endif

#if FL_NUTTX_EXEC_INHERIT_PRIORITY
/* What this back-end calls. Kconfig takes care of it; the check keeps a
 * hand-written configuration from ending in a link error. */
#ifndef CONFIG_NSH_LIBRARY
#error "FPBINJECT_EXEC_INHERIT_PRIORITY needs CONFIG_NSH_LIBRARY (nsh_system)"
#endif
#ifndef CONFIG_SCHED_WAITPID
#error "FPBINJECT_EXEC_INHERIT_PRIORITY needs CONFIG_SCHED_WAITPID (waitpid)"
#endif
#include <nshlib/nshlib.h>
#include <sched.h>
#include <spawn.h>
#include <sys/wait.h>

/* Stack of the nsh_system task. The own Kconfig value, so that the back-end
 * does not depend on CONFIG_SYSTEM_SYSTEM_STACKSIZE. */
#ifndef FL_NUTTX_EXEC_STACKSIZE
#ifdef CONFIG_FPBINJECT_EXEC_STACKSIZE
#define FL_NUTTX_EXEC_STACKSIZE CONFIG_FPBINJECT_EXEC_STACKSIZE
#else
#define FL_NUTTX_EXEC_STACKSIZE 4096
#endif
#endif

#define FL_NUTTX_HAVE_EXEC 1
#elif defined(CONFIG_SYSTEM_SYSTEM)
#define FL_NUTTX_HAVE_EXEC 1
#else
#define FL_NUTTX_HAVE_EXEC 0
#endif

#ifndef FL_NUTTX_BUF_SIZE
#define FL_NUTTX_BUF_SIZE -1
#endif

#ifndef FL_NUTTX_LINE_SIZE
#define FL_NUTTX_LINE_SIZE 1024
#endif

/* Include func_allocator for static buffer mode */
#if FL_NUTTX_BUF_SIZE > 0
#include "fl_allocator.h"
#endif

/* Output callback */
static void nuttx_output_cb(void* user, const char* str) {
    (void)user;
    fputs(str, stdout);
    fflush(stdout); /* Ensure output is sent immediately */
}

/* Flush dcache callback */
static void nuttx_flush_dcache_cb(uintptr_t start, uintptr_t end) {
    up_flush_dcache(start, end);
}

/* Invalidate icache callback */
static void nuttx_invalidate_icache_cb(uintptr_t start, uintptr_t end) {
    up_invalidate_icache(start, end);
}

#if FL_NUTTX_EXEC_INHERIT_PRIORITY
/**
 * @brief Exec callback: like system(), but the shell task runs at the priority of this (fl) task
 *
 * system() gives its shell task the fixed CONFIG_SYSTEM_SYSTEM_PRIORITY, so a
 * busy task between that and fl's own (higher) priority can starve the
 * command while fl sits in waitpid(). A program that the shell starts keeps
 * the priority registered for it, as with any NSH command.
 *
 * @param user       Unused
 * @param cmdline    Command line, run by nsh_system() as "-c <cmdline>"
 * @param timeout_ms Accepted but NOT enforced
 * @return Raw waitpid() status as system() returns it, or a negative errno
 *         when the command could not be started or waited for
 * @note   stdout/stderr are inherited, i.e. the console
 */
static int nuttx_exec_cb(void* user, const char* cmdline, uint32_t timeout_ms) {
    (void)user;
    (void)timeout_ms;

    struct sched_param param;
    if (sched_getparam(0, &param) < 0) {
        return errno > 0 ? -errno : -EIO;
    }

    posix_spawnattr_t attr;
    int err = posix_spawnattr_init(&attr);
    if (err != 0) {
        return -err;
    }
    err = posix_spawnattr_setschedparam(&attr, &param);
    if (err == 0) {
        err = posix_spawnattr_setflags(&attr, POSIX_SPAWN_SETSCHEDPARAM);
    }
    if (err == 0) {
        err = posix_spawnattr_setstacksize(&attr, FL_NUTTX_EXEC_STACKSIZE);
    }

    pid_t pid = -err;
    if (err == 0) {
        /* task_spawn() wants char *const argv[]; the strings are copied, never written */
        char* const sh_argv[3] = {(char*)"-c", (char*)cmdline, NULL};
        pid = task_spawn("flexec", nsh_system, NULL, &attr, sh_argv, NULL);
    }
    posix_spawnattr_destroy(&attr);
    if (pid < 0) {
        return pid; /* negative errno, as in system() */
    }

    int rc = 0;
    if (waitpid(pid, &rc, 0) < 0) {
        return errno > 0 ? -errno : -EIO;
    }
    return rc;
}
#elif defined(CONFIG_SYSTEM_SYSTEM)
/**
 * @brief Exec callback: run the command line through NSH via system()
 *
 * system() blocks (waitpid) until the command exits and has no timeout
 * support, so do not run commands that block for a long time.
 *
 * @param user       Unused
 * @param cmdline    Command line to run
 * @param timeout_ms Accepted but NOT enforced
 * @return system() status, or a negative errno when the shell task could not be started
 * @note   stdout/stderr are inherited, i.e. the console
 */
static int nuttx_exec_cb(void* user, const char* cmdline, uint32_t timeout_ms) {
    (void)user;
    (void)timeout_ms;

    const int ret = system(cmdline);
    if (ret < 0) {
        /* system() returns ERROR (-1) and sets errno when it cannot spawn or
         * wait for the shell task. Report that as -errno (fl_exec_cb_t
         * contract) so the host sees the real cause. */
        return errno > 0 ? -errno : -EIO;
    }
    return ret;
}
#endif

/* ==========================================================================
 * Memory Allocation Configuration
 * ========================================================================== */

#if FL_NUTTX_BUF_SIZE > 0
/* Static allocation with func_allocator */
static uint8_t s_code_buf[FL_NUTTX_BUF_SIZE] __attribute__((aligned(4)));
static fl_alloc_t s_alloc;

static void* nuttx_malloc_cb(size_t size) {
    return fl_malloc(&s_alloc, size);
}

static void nuttx_free_cb(void* ptr) {
    fl_free(&s_alloc, ptr);
}

static void nuttx_alloc_init(void) {
    fl_alloc_init(&s_alloc, s_code_buf, sizeof(s_code_buf));
}

static void nuttx_print_alloc_info(void) {
    printf("Buffer: %u bytes @ 0x%08lX (STATIC, blocks: %u)\n", (unsigned)sizeof(s_code_buf), (unsigned long)s_code_buf,
           (unsigned)s_alloc.block_count);
}
#else
/* Dynamic allocation with libc malloc/free */
static void nuttx_alloc_init(void) {
    /* Nothing to initialize for libc malloc */
}

static void nuttx_print_alloc_info(void) {
    printf("Allocator: LIBC malloc/free\n");
}
#endif

static int interactive_mode(fl_context_t* ctx, int argc_first, char** argv_first) {
    char line[FL_NUTTX_LINE_SIZE];
    static const char* argv[32];

    printf("FPBInject Function Loader (NuttX)\n");
    nuttx_print_alloc_info();
    printf("Type --cmd <command> or 'quit' to exit\n\n");

    /* Execute first command if provided */
    if (argc_first > 1) {
        const fl_error_t ret = fl_exec_cmd(ctx, argc_first, (const char**)argv_first);
        if (ret != FL_OK) {
            printf("Error: %d\n", ret);
        }
    }

    while (1) {
        printf("fl> ");
        fflush(stdout);

        if (!fgets(line, sizeof(line), stdin)) {
            break;
        }

        /* Remove newline */
        size_t len = strlen(line);
        if (len > 0 && line[len - 1] == '\n') {
            line[len - 1] = '\0';
        }

        if (strcmp(line, "quit") == 0 || strcmp(line, "exit") == 0 || strcmp(line, "q") == 0) {
            break;
        }

        if (line[0] == '\0') {
            continue;
        }

        int argc = fl_stream_parse_line(line, argv, sizeof(argv) / sizeof(argv[0]));
        if (argc > 0) {
            const fl_error_t ret = fl_exec_cmd(ctx, argc, argv);
            if (ret != FL_OK) {
                printf("fl_error: %d. Type 'q' to exit\n\n", (int)ret);
            }
        }
    }

    /* Explicit exit marker (host detects this instead of guessing the shell
     * prompt). Uses the [FLxxx] protocol family; fires on every exit path. */
    printf("[FLEXIT]\n");
    fflush(stdout);

    return 0;
}

/**
 * @brief NuttX application entry point
 */
int main(int argc, char** argv) {
    static fl_context_t ctx = {0};

    if (!fl_is_inited(&ctx)) {
        fl_init_default(&ctx);
        ctx.output_cb = nuttx_output_cb;
        ctx.flush_dcache_cb = nuttx_flush_dcache_cb;
        ctx.invalidate_icache_cb = nuttx_invalidate_icache_cb;

        /* Report to host via 'info': this port always runs the interactive
         * fl loop, so being able to reach 'info' at all means we're in it. */
        ctx.interactive = true;
        ctx.platform_desc = "NuttX";

#if FL_NUTTX_HAVE_EXEC
        /* exec needs an exec back-end (see the top of this file); without
         * one exec_cb stays NULL and the command reports "No exec_cb". */
        ctx.exec_cb = nuttx_exec_cb;
#endif

        /* Initialize allocator */
        nuttx_alloc_init();

#if FL_NUTTX_BUF_SIZE > 0
        /* Static allocation mode */
        ctx.malloc_cb = nuttx_malloc_cb;
        ctx.free_cb = nuttx_free_cb;
#else
        /* Dynamic allocation mode */
        ctx.malloc_cb = malloc;
        ctx.free_cb = free;
#endif
#if FL_USE_FILE && FL_FILE_USE_POSIX
        /* Initialize file transfer context with POSIX ops */
        ctx.file_ctx.fs = fl_file_get_posix_ops();
#endif
        fl_init(&ctx);
    }

    return interactive_mode(&ctx, argc, argv);
}

#endif /* __NuttX__ */
