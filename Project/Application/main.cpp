/*
 * MIT License
 * Copyright (c) 2017 - 2025 _VIFEXTech
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
 * @brief  FPBInject main entry point
 *
 * Use macro switch to select run mode:
 * - APP_BLINK: LED blink + FPB injection demo
 * - APP_TEST: FPB functionality test
 * - APP_FUNC_LOADER: Function loader (serial interaction)
 */

#include <Arduino.h>

/*===========================================================================
 * Application Selection - Only one can be enabled
 *===========================================================================*/

#define APP_BLINK 1
#define APP_TEST 2
#define APP_FUNC_LOADER 3

#ifndef APP_SELECT
#define APP_SELECT APP_BLINK
#endif

/*===========================================================================
 * Include corresponding module based on selection
 *===========================================================================*/

#if APP_SELECT == APP_BLINK
#include "blink.h"
#elif APP_SELECT == APP_TEST
#include "test.h"
#elif APP_SELECT == APP_FUNC_LOADER
#include "func_loader.h"
#endif

/*===========================================================================
 * Main Function
 *===========================================================================*/

int main(void)
{
    /* Initialize MCU core */
    Core_Init();

#if APP_SELECT == APP_BLINK
    /* LED blink + FPB injection demo */
    blink_run();

#elif APP_SELECT == APP_TEST
    /* FPB functionality test */
    Serial.begin(115200);
    test_run();

#elif APP_SELECT == APP_FUNC_LOADER
    /* Function loader mode */
    Serial.begin(115200);
    func_loader_run();

#else
#error "Invalid APP_SELECT value"
#endif

    /* Should never reach here */
    for (;;) {
        __asm volatile("wfi");
    }
}
