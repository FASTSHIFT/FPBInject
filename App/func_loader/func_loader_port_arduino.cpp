/**
 * @file   func_loader_port_arduino.cpp
 * @brief  Arduino/STM32 porting layer (static allocation)
 */

#include "func_loader.h"
#include "func_loader_stream.h"
#include <Arduino.h>

#define LED_PIN PC13

/* Static code buffer */
static uint8_t s_code_buf[4096] __attribute__((aligned(4), section(".ram_code")));
static char s_line_buf[2048];

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

/* Instances */
static fl_context_t s_ctx = {
    .output_cb = NULL,
    .output_user = NULL,
    .malloc_cb = NULL,
    .free_cb = NULL,
    .static_buf = s_code_buf,
    .static_size = sizeof(s_code_buf),
    .static_used = 0,
    .dyn_base = 0,
    .dyn_size = 0,
    .dyn_used = 0,
};

static const fl_serial_t s_serial = {
    .read_cb = serial_read_cb,
    .write_cb = serial_write_cb,
    .available_cb = serial_available_cb,
};

static fl_stream_t s_stream;

/* Output helper for banner */
static void banner_output(void* user, const char* str) {
    (void)user;
    Serial.print(str);
}

static void blink_led() {
    static uint32_t last_time = 0;

    if (millis() - last_time < 500) {
        return;
    }

    togglePin(LED_PIN);
    last_time = millis();
}

void func_loader_run(void) {
    Serial.begin(115200);
    pinMode(LED_PIN, OUTPUT);

    fl_init(&s_ctx);
    fl_stream_init(&s_stream, &s_ctx, &s_serial, s_line_buf, sizeof(s_line_buf));

    /* Print banner */
    s_ctx.output_cb = banner_output;
    s_ctx.output_user = NULL;

    Serial.println("=====================================");
    Serial.println("FPBInject Function Loader v1.0");
    Serial.println("=====================================");
    Serial.println("Type --cmd help for commands");
    Serial.println("");

    /* Restore stream output */
    s_ctx.output_cb = NULL;
    fl_stream_init(&s_stream, &s_ctx, &s_serial, s_line_buf, sizeof(s_line_buf));

    for (;;) {
        fl_stream_process(&s_stream);
        blink_led();
    }
}
