/*
 * MIT License
 * Copyright (c) 2024 _VIFEXTech
 *
 * Main entry for FatFS backend tests
 */

#include "test_framework.h"
#include <stdio.h>

/* External test runners */
extern void run_fatfs_tests(void);

int main(int argc, char** argv) {
    (void)argc;
    (void)argv;

    printf("========================================\n");
    printf("FPBInject FatFS Backend Unit Tests\n");
    printf("========================================\n");

    test_framework_init();

    run_fatfs_tests();

    return test_framework_report();
}
