/*
 * Inject patch for String::toUpperCase()
 *
 * Target: String::toUpperCase()
 * Simple test - just print a message
 */

#include <stdio.h>

/* FPB_INJECT */
__attribute__((section(".fpb.text"), used)) extern "C" void toUpperCase(void* str) {
    (void)str;
    printf("Hijacked toUpperCase!\n");
}
