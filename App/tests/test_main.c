/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Main Test Runner for FPBInject Firmware Tests
 *
 * Runs all host-based mock tests with coverage support.
 * Build with: gcc -g -O0 --coverage -o test_runner test_main.c ...
 */

#include <stdio.h>
#include <stdlib.h>
#include "test_framework.h"
#include "mock_hardware.h"

/* External test runners */
extern void run_allocator_tests(void);
extern void run_loader_tests(void);
extern void run_stream_tests(void);
extern void run_fpb_tests(void);
extern void run_file_tests(void);
extern void run_fpb_debugmon_tests(void);
extern void run_fpb_trampoline_tests(void);

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    printf("╔══════════════════════════════════════════════════════════════╗\n");
    printf("║           FPBInject Firmware Unit Tests                      ║\n");
    printf("║           Host-based Mock Testing with Coverage              ║\n");
    printf("╚══════════════════════════════════════════════════════════════╝\n\n");

    /* Initialize test framework */
    test_framework_init();

    /* Run all test suites */
    printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    printf("Running: func_allocator tests\n");
    printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    run_allocator_tests();

    printf("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    printf("Running: func_loader tests\n");
    printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    run_loader_tests();

    printf("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    printf("Running: func_loader_stream tests\n");
    printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    run_stream_tests();

    printf("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    printf("Running: fpb_inject tests\n");
    printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    run_fpb_tests();

    printf("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    printf("Running: fpb_debugmon tests\n");
    printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    run_fpb_debugmon_tests();

    printf("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    printf("Running: fpb_trampoline tests\n");
    printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    run_fpb_trampoline_tests();

    printf("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    printf("Running: func_loader_file tests\n");
    printf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
    run_file_tests();

    printf("\n");

    /* Print final report */
    int exit_code = test_framework_report();

    printf("\n");
    if (exit_code == 0) {
        printf("🎉 All tests passed!\n");
    } else {
        printf("❌ Some tests failed. Exit code: %d\n", exit_code);
    }

    return exit_code;
}
