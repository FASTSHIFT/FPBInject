/*
 * Simple test C file for decompilation testing
 * Compile with: arm-none-eabi-gcc -c -o test_func.o test_func.c -mcpu=cortex-m3 -mthumb
 * Link with: arm-none-eabi-gcc -o test_func.elf test_func.o -nostartfiles -Wl,-Ttext=0x08000000
 */

#include <stdint.h>

volatile uint32_t counter = 0;

/* Simple function for testing */
void simple_func(void) {
    counter++;
}

/* Function with parameters */
int add_numbers(int a, int b) {
    return a + b;
}

/* Function with loop */
uint32_t sum_array(uint32_t *arr, uint32_t len) {
    uint32_t sum = 0;
    for (uint32_t i = 0; i < len; i++) {
        sum += arr[i];
    }
    return sum;
}

/* Main entry point (minimal) */
void _start(void) {
    simple_func();
    add_numbers(1, 2);
    while (1) {}
}
