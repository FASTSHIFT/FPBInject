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
 */

#ifdef __NuttX__

#include "fl.h"
#include <nuttx/config.h>
#include <nuttx/cache.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

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

/* ==========================================================================
 * Memory Allocation Configuration
 * ========================================================================== */

#if FL_NUTTX_BUF_SIZE > 0
/* Static allocation with func_allocator */
static uint8_t s_code_buf[FL_NUTTX_BUF_SIZE] __attribute__((aligned(4)));
static func_alloc_t s_alloc;

static void* nuttx_malloc_cb(size_t size) {
    return func_malloc(&s_alloc, size);
}

static void nuttx_free_cb(void* ptr) {
    func_free(&s_alloc, ptr);
}

static void nuttx_alloc_init(void) {
    func_alloc_init(&s_alloc, s_code_buf, sizeof(s_code_buf));
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

static int parse_line(char* line, const char** argv, int max_argc) {
    int argc = 0;
    char* p = line;
    bool in_quote = false;
    bool in_arg = false;

    while (*p && argc < max_argc) {
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

    return argc;
}

static int interactive_mode(fl_context_t* ctx) {
    char line[FL_NUTTX_LINE_SIZE];
    static const char* argv[32];

    printf("FPBInject Function Loader (NuttX)\n");
    nuttx_print_alloc_info();
    printf("Type --cmd <command> or 'quit' to exit\n\n");

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

        int argc = parse_line(line, argv, sizeof(argv) / sizeof(argv[0]));
        if (argc > 0) {
            fl_exec_cmd(ctx, argc, argv);
        }
    }

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

    if (argc > 1) {
        printf("[FLERR] Enter '%s' to start interactive mode\n", argv[0]);
        return 0;
    }

    /* No arguments - interactive mode */
    return interactive_mode(&ctx);
}

#endif /* __NuttX__ */
