/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Hardware abstraction mock for unit testing on host
 */

#ifndef __MOCK_HARDWARE_H
#define __MOCK_HARDWARE_H

#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================================
 * FPB Register Simulation
 * ============================================================================ */

typedef struct {
    uint32_t ctrl;
    uint32_t remap;
    uint32_t comp[8];
} mock_fpb_regs_t;

extern mock_fpb_regs_t mock_fpb_regs;

/* FPB CTRL register bits */
#define FPB_CTRL_ENABLE (1UL << 0)
#define FPB_CTRL_KEY (1UL << 1)
#define FPB_CTRL_NUM_CODE_SHIFT 4
#define FPB_CTRL_NUM_LIT_SHIFT 8
#define FPB_COMP_ENABLE (1UL << 0)

/* ============================================================================
 * Mock Control Functions
 * ============================================================================ */

void mock_fpb_reset(void);
void mock_fpb_configure(uint8_t num_code, uint8_t num_lit);
uint32_t mock_fpb_get_ctrl(void);
uint32_t mock_fpb_get_remap(void);
uint32_t mock_fpb_get_comp(uint8_t index);
bool mock_fpb_is_enabled(void);
bool mock_fpb_comp_is_enabled(uint8_t index);

/* ============================================================================
 * Call Statistics
 * ============================================================================ */

typedef struct {
    uint32_t dsb_count;
    uint32_t isb_count;
    uint32_t malloc_count;
    uint32_t free_count;
    size_t total_allocated;
    size_t total_freed;
} mock_call_stats_t;

extern mock_call_stats_t g_mock_call_stats;

void mock_reset_call_stats(void);
const mock_call_stats_t* mock_get_call_stats(void);

/* ============================================================================
 * Mock Serial for Stream Testing
 * ============================================================================ */

#define MOCK_SERIAL_BUF_SIZE 1024

typedef struct {
    char rx_buffer[MOCK_SERIAL_BUF_SIZE];
    size_t rx_pos;
    size_t rx_len;
    char tx_buffer[MOCK_SERIAL_BUF_SIZE];
    size_t tx_len;
} mock_serial_t;

extern mock_serial_t g_mock_serial;

void mock_serial_reset(void);
void mock_serial_set_input(const char* data);
int mock_serial_read(uint8_t* buf, size_t len);
int mock_serial_write(const uint8_t* buf, size_t len);
int mock_serial_available(void);
const char* mock_serial_get_output(void);

/* ============================================================================
 * Mock Output Capture
 * ============================================================================ */

#define MOCK_OUTPUT_BUF_SIZE 4096

extern char g_mock_output_buffer[MOCK_OUTPUT_BUF_SIZE];
extern size_t g_mock_output_len;

void mock_output_reset(void);
void mock_output_cb(void* user, const char* str);
const char* mock_output_get(void);
bool mock_output_contains(const char* substr);

/* ============================================================================
 * Mock Memory Allocator
 * ============================================================================ */

#define MOCK_HEAP_SIZE 8192

void mock_heap_reset(void);
void* mock_malloc(size_t size);
void mock_free(void* ptr);

#ifdef __cplusplus
}
#endif

#endif /* __MOCK_HARDWARE_H */
