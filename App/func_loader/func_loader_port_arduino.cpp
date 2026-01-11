/**
 * @file   func_loader_port_arduino.cpp
 * @brief  Arduino/STM32 platform porting for func_loader
 */

#include "func_loader.h"
#include <Arduino.h>

static int platform_serial_read(uint8_t* buf, size_t len) {
    size_t count = 0;
    while (count < len && Serial.available()) {
        buf[count++] = Serial.read();
    }
    return (int)count;
}

static int platform_serial_write(const uint8_t* buf, size_t len) {
    return (int)Serial.write(buf, len);
}

static int platform_serial_available(void) {
    return Serial.available();
}

static uint32_t platform_get_tick_ms(void) {
    return millis();
}

void func_loader_run(void) {
    Serial.begin(115200);

    while (!Serial) {
        ;
    }

    delay(100);

    fl_platform_t platform;
    platform.serial_read = platform_serial_read;
    platform.serial_write = platform_serial_write;
    platform.serial_available = platform_serial_available;
    platform.malloc = NULL;
    platform.free = NULL;
    platform.get_tick_ms = platform_get_tick_ms;

    if (fl_init(&platform) != 0) {
        Serial.println("[ERR] Failed to initialize func_loader");
        while (1) {
            delay(1000);
        }
    }

    fl_print("=====================================");
    fl_print("FPBInject Function Loader v1.0");
    fl_print("=====================================");
    fl_print("Type --cmd help for available commands");
    fl_print("");

    for (;;) {
        fl_process();
    }
}
