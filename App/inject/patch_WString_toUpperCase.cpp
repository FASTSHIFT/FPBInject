/*
 * Inject patch for String::toUpperCase()
 *
 * Target: String::toUpperCase()
 * Simple test - just print a message
 */

#include <stdio.h>

extern "C" __attribute__((used, section(".text.inject"), nothrow)) void inject_toUpperCase(void* str) {
    (void)str;
    printf("Hijacked toUpperCase!\n");
}
