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
 * @file   func_loader_stream.c
 * @brief  Stream processing implementation
 */

#include "func_loader_stream.h"
#include <string.h>

static void stream_output(void* user, const char* str) {
    fl_stream_t* s = (fl_stream_t*)user;
    if (s->serial && s->serial->write_cb) {
        s->serial->write_cb((const uint8_t*)str, strlen(str));
    }
}

void fl_stream_init(fl_stream_t* s, fl_context_t* ctx, const fl_serial_t* serial, char* line_buf, size_t line_size) {
    s->ctx = ctx;
    s->serial = serial;
    s->line_buf = line_buf;
    s->line_size = line_size;
    s->line_pos = 0;

    ctx->output_cb = stream_output;
    ctx->output_user = s;
}

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

int fl_stream_exec_line(fl_stream_t* s, char* line) {
    static const char* argv[FL_MAX_ARGC];
    int argc = parse_line(line, argv, FL_MAX_ARGC);
    if (argc > 0) {
        return fl_exec_cmd(s->ctx, argc, argv);
    }
    return 0;
}

void fl_stream_process(fl_stream_t* s) {
    if (!s->serial || !s->serial->available_cb || !s->serial->read_cb) {
        return;
    }

    while (s->serial->available_cb() > 0) {
        uint8_t c;
        if (s->serial->read_cb(&c, 1) != 1)
            break;

        if (c == '\n' || c == '\r') {
            if (s->line_pos > 0) {
                s->line_buf[s->line_pos] = '\0';
                fl_stream_exec_line(s, s->line_buf);
                s->line_pos = 0;
            }
            continue;
        }

        if (c == '\b' || c == 0x7F) {
            if (s->line_pos > 0)
                s->line_pos--;
            continue;
        }

        if (s->line_pos < s->line_size - 1) {
            s->line_buf[s->line_pos++] = c;
        }
    }
}
