/*
 * MIT License
 * Copyright (c) 2017 - 2022 _VIFEXTech
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
 * @file   main.cpp
 * @brief  FPBInject Demo - PC13 LED翻转 + FPB注入演示
 *
 * 本Demo演示:
 * 1. PC13 LED闪烁 (500ms周期)
 * 2. FPB代码注入功能 - 在运行时替换原始LED翻转函数
 *
 * 硬件要求:
 * - STM32F103C8T6 (Blue Pill)
 * - ST-Link调试器
 * - PC13连接LED (大多数Blue Pill板载)
 */

#include "fpb_inject.h"
#include <Arduino.h>

/* LED引脚定义 - PC13是Blue Pill板载LED */
#define LED_PIN PC13

/* 原始LED翻转函数 - 正常闪烁 (500ms) */
__attribute__((noinline)) void original_led_toggle(void) {
  togglePin(LED_PIN);
  delay_ms(500);
}

/* 注入后的LED翻转函数 - 快速闪烁 (100ms) */
__attribute__((noinline)) void injected_led_toggle(void) {
  togglePin(LED_PIN);
  delay_ms(100);
}

/* 当前使用的LED函数指针 */
typedef void (*led_func_t)(void);
volatile led_func_t current_led_func = original_led_toggle;

/* 演示计数器 */
static volatile uint32_t demo_counter = 0;

/**
 * @brief 初始化设置
 */
static void setup() {
  /* 初始化PC13为输出模式 */
  pinMode(LED_PIN, OUTPUT);

  /* 初始化LED为熄灭状态 (低电平有效) */
  digitalWrite_HIGH(LED_PIN);

  /* 初始化FPB单元 */
  FPB_Init();

  /* 打印启动信息 (如果有串口) */
  Serial.begin(115200);
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
}

/**
 * @brief 主循环
 */
static void loop() {
  demo_counter++;

  /* 演示：前10次使用原始函数，之后使用FPB注入 */
  if (demo_counter == 10) {
    Serial.println("[FPB] Enabling code injection...");
    /* 使用FPB将original_led_toggle重定向到injected_led_toggle */
    FPB_SetPatch(0, (uint32_t)original_led_toggle,
                 (uint32_t)injected_led_toggle);

    Serial.println("[FPB] Injection complete! LED should blink faster now.");
  }

  /* 在第20次禁用FPB注入，恢复原始功能 */
  if (demo_counter == 20) {
    Serial.println("[FPB] Disabling code injection...");
    FPB_ClearPatch(0);

    Serial.println(
        "[FPB] Original function restored! LED should blink slower now.");
  }

  /* 第30次重新启用注入 */
  if (demo_counter == 30) {
    Serial.println("[FPB] Re-enabling code injection...");
    FPB_SetPatch(0, (uint32_t)original_led_toggle,
                 (uint32_t)injected_led_toggle);
    demo_counter = 10; /* 循环演示 */
  }

  /* 调用LED翻转函数 - FPB会在硬件层面进行重定向 */
  original_led_toggle();
}

/**
 * @brief  Main Function
 */
int main(void) {
  Core_Init();
  setup();
  for (;;)
    loop();
}
