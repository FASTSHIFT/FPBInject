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
 * @file   func_loader_port_arduino.cpp
 * @brief  Arduino/STM32 porting layer
 *
 * Supports three allocation modes (selected via CMake FL_ALLOC_MODE):
 *   - FL_ALLOC_STATIC: Static buffer allocation (default)
 *   - FL_ALLOC_LIBC:   Use standard libc malloc/free
 *   - FL_ALLOC_UMM:    Use umm_malloc (embedded allocator)
 */

#include "func_loader.h"
#include "func_loader_stream.h"
#include <Arduino.h>
#include <stdio.h>

/* Include UMM_MALLOC header only when needed */
#if defined(FL_ALLOC_UMM)
#include "umm_malloc.h"
#endif

/* Include stdlib for LIBC malloc */
#if defined(FL_ALLOC_LIBC)
#include <stdlib.h>
#endif

/* Include func_allocator for FL_ALLOC_STATIC */
#if defined(FL_ALLOC_STATIC)
#include "func_allocator.h"
#endif

#define LED_PIN PC13

/* ==========================================================================
 * Memory Allocation Configuration
 * ========================================================================== */

#if defined(FL_ALLOC_STATIC)
/* --------------------------------------------------------------------------
 * Static Allocation Mode (with func_allocator)
 * -------------------------------------------------------------------------- */
#define ALLOC_MODE_NAME "STATIC"

static uint8_t s_code_buf[1024] __attribute__((aligned(4), section(".ram_code")));
static func_alloc_t s_alloc;

static void* malloc_cb(size_t size) {
    return func_malloc(&s_alloc, size);
}

static void free_cb(void* ptr) {
    func_free(&s_alloc, ptr);
}

static void alloc_init(void) {
    func_alloc_init(&s_alloc, s_code_buf, sizeof(s_code_buf));
}

static void print_alloc_info(void) {
    printf("Buffer: %u bytes @ 0x%08lX (STATIC, blocks: %u)\n", (unsigned)sizeof(s_code_buf), (unsigned long)s_code_buf,
           (unsigned)s_alloc.block_count);
}

#elif defined(FL_ALLOC_LIBC)
/* --------------------------------------------------------------------------
 * LIBC malloc/free Mode
 * -------------------------------------------------------------------------- */
#define ALLOC_MODE_NAME "LIBC"

static void alloc_init(void) {
    /* Nothing to initialize for libc malloc */
}

static void print_alloc_info(void) {
    printf("Allocator: LIBC malloc/free");
}

#elif defined(FL_ALLOC_UMM)
/* --------------------------------------------------------------------------
 * UMM_MALLOC Mode
 * -------------------------------------------------------------------------- */
#define ALLOC_MODE_NAME "UMM"

static uint8_t s_heap_buf[1024] __attribute__((aligned(4)));

static void alloc_init(void) {
    umm_init_heap(s_heap_buf, sizeof(s_heap_buf));
}

static void print_alloc_info(void) {
    printf("Heap: %u bytes @ 0x%08lX (UMM_MALLOC)\n", (unsigned)sizeof(s_heap_buf), (unsigned long)s_heap_buf);
}

#else
#error "No allocation mode defined"
#endif

/* ==========================================================================
 * Common Code
 * ========================================================================== */

/* Serial callbacks */
static int serial_read_cb(uint8_t* buf, size_t len) {
    size_t n = 0;
    while (n < len && Serial.available()) {
        buf[n++] = Serial.read();
    }
    return (int)n;
}

static int serial_write_cb(const uint8_t* buf, size_t len) {
    return (int)Serial.write(buf, len);
}

static int serial_available_cb(void) {
    return Serial.available();
}

static void blink_led() {
    static uint32_t last_time = 0;
    static bool led_state = false;

    if (millis() - last_time < 500) {
        return;
    }

    led_state = !led_state;

    String str = led_state ? "led on" : "led off";
    str += "\n";
    str.toUpperCase();

    Serial.print(str);

    digitalWrite(LED_PIN, led_state);

    Serial.printf("LED GPIO state: %d\n", digitalRead(LED_PIN));

    last_time = millis();
}

void func_loader_run(void) {
    pinMode(LED_PIN, OUTPUT);

    /* Initialize allocator (mode-specific) */
    alloc_init();

    static fl_context_t s_ctx;
    fl_init_default(&s_ctx);
#ifdef FL_ALLOC_STATIC
    s_ctx.malloc_cb = malloc_cb;
    s_ctx.free_cb = free_cb;
#elif defined(FL_ALLOC_LIBC)
    s_ctx.malloc_cb = malloc;
    s_ctx.free_cb = free;
#elif defined(FL_ALLOC_UMM)
    s_ctx.malloc_cb = umm_malloc;
    s_ctx.free_cb = umm_free;
#endif

    static fl_stream_t s_stream;
    static const fl_serial_t s_serial = {
        .read_cb = serial_read_cb,
        .write_cb = serial_write_cb,
        .available_cb = serial_available_cb,
    };

    /* Line buffer for stream processing */
    static char s_line_buf[512];
    fl_stream_init(&s_stream, &s_ctx, &s_serial, s_line_buf, sizeof(s_line_buf));
    fl_init(&s_ctx);

    printf("=====================================\n");
    printf("FPBInject Function Loader v1.0\n");
    printf("=====================================\n");
    printf("Type fl --cmd help for commands\n");

    printf("Toggle LED pin: %d\n", LED_PIN);
    printf("Alloc mode: %s\n", ALLOC_MODE_NAME);
    print_alloc_info();

    for (;;) {
        fl_stream_process(&s_stream);
        blink_led();
    }
}
