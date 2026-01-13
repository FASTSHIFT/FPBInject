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
 * @file   blink.c
 * @brief  FPBInject Demo - PC13 LED toggle + FPB injection demo
 *
 * This demo demonstrates:
 * 1. PC13 LED blinking (500ms period)
 * 2. FPB code injection - replace original LED toggle function at runtime
 *
 * Hardware requirements:
 * - STM32F103C8T6 (Blue Pill)
 * - ST-Link debugger
 * - LED connected to PC13 (most Blue Pill boards have onboard LED)
 */

#include "blink.h"
#include "fpb_inject.h"
#include <Arduino.h>

/* LED pin definition - PC13 is Blue Pill onboard LED */
#define LED_PIN PC13

/* Demo counter */
static volatile uint32_t g_demo_counter = 0;

/**
 * @brief Original LED toggle function - normal blink (500ms)
 */
__attribute__((noinline)) void original_led_toggle(void) {
    togglePin(LED_PIN);
    delay_ms(500);
}

/**
 * @brief Injected LED toggle function - fast blink (100ms)
 */
__attribute__((noinline)) void injected_led_toggle(void) {
    togglePin(LED_PIN);
    delay_ms(100);
}

/**
 * @brief Initialize blink module
 */
void blink_init(void) {
    /* Initialize PC13 as output */
    pinMode(LED_PIN, OUTPUT);

    /* Initialize LED to off state (active low) */
    digitalWrite_HIGH(LED_PIN);

    /* Initialize FPB unit */
    fpb_init();

    /* Print startup info */
    Serial.println("================================");
    Serial.println("FPBInject Demo - STM32F103");
    Serial.println("================================");
    Serial.println("Starting LED blink demo...");
    Serial.println("Original: 500ms blink");
    Serial.println("After FPB inject: 100ms blink");
    Serial.println("");
    Serial.print("Original function addr: 0x");
    Serial.println((uint32_t)original_led_toggle, HEX);
    Serial.print("Injected function addr: 0x");
    Serial.println((uint32_t)injected_led_toggle, HEX);
    Serial.println("");

    g_demo_counter = 0;
}

/**
 * @brief Blink main loop
 */
void blink_loop(void) {
    g_demo_counter++;

    /* Demo: first 10 times use original function, then use FPB injection */
    if (g_demo_counter == 10) {
        Serial.println("[FPB] Enabling code injection...");
        /* Use FPB to redirect original_led_toggle to injected_led_toggle */
        fpb_set_patch(0, (uint32_t)original_led_toggle, (uint32_t)injected_led_toggle);
        Serial.println("[FPB] Injection complete! LED should blink faster now.");
    }

    /* At 20th time, disable FPB injection, restore original function */
    if (g_demo_counter == 20) {
        Serial.println("[FPB] Disabling code injection...");
        fpb_clear_patch(0);
        Serial.println("[FPB] Original function restored! LED should blink slower now.");
    }

    /* At 30th time, re-enable injection */
    if (g_demo_counter == 30) {
        Serial.println("[FPB] Re-enabling code injection...");
        fpb_set_patch(0, (uint32_t)original_led_toggle, (uint32_t)injected_led_toggle);
        g_demo_counter = 10; /* Loop demo */
    }

    /* Call LED toggle function - FPB will redirect at hardware level */
    original_led_toggle();
}

/**
 * @brief Run blink demo
 */
void blink_run(void) {
    blink_init();
    for (;;) {
        blink_loop();
    }
}
