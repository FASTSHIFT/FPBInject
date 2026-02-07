/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Hardware abstraction mock implementation
 */

#include "mock_hardware.h"
#include "fpb_mock_regs.h"
#include <stdlib.h>
#include <stdio.h>

/* ============================================================================
 * FPB Register Mock - delegates to fpb_mock_regs.c
 * ============================================================================ */

mock_fpb_regs_t mock_fpb_regs;
mock_call_stats_t g_mock_call_stats;

void mock_fpb_reset(void) {
    /* Reset the fpb_mock_regs variables used by fpb_inject.c */
    fpb_mock_reset();

    /* Also reset our local mock_fpb_regs for backward compatibility */
    memset(&mock_fpb_regs, 0, sizeof(mock_fpb_regs));

    /* Configure with default comparators (like STM32F103) */
    fpb_mock_configure(6, 2);
    mock_fpb_regs.ctrl = (6 << FPB_CTRL_NUM_CODE_SHIFT) | (2 << FPB_CTRL_NUM_LIT_SHIFT);

    mock_reset_call_stats();
}

void mock_fpb_configure(uint8_t num_code, uint8_t num_lit) {
    fpb_mock_configure(num_code, num_lit);
    mock_fpb_regs.ctrl = (num_code << FPB_CTRL_NUM_CODE_SHIFT) | (num_lit << FPB_CTRL_NUM_LIT_SHIFT);
}

uint32_t mock_fpb_get_ctrl(void) {
    return fpb_mock_ctrl_read();
}
uint32_t mock_fpb_get_remap(void) {
    return mock_fpb_remap;
}
uint32_t mock_fpb_get_comp(uint8_t index) {
    return (index < 8) ? mock_fpb_comp[index] : 0;
}
bool mock_fpb_is_enabled(void) {
    return (fpb_mock_ctrl_read() & FPB_CTRL_ENABLE) != 0;
}
bool mock_fpb_comp_is_enabled(uint8_t index) {
    return (index < 8) && (mock_fpb_comp[index] & FPB_COMP_ENABLE);
}

void mock_reset_call_stats(void) {
    memset(&g_mock_call_stats, 0, sizeof(g_mock_call_stats));
}
const mock_call_stats_t* mock_get_call_stats(void) {
    return &g_mock_call_stats;
}

/* ============================================================================
 * Mock Serial
 * ============================================================================ */

mock_serial_t g_mock_serial;

void mock_serial_reset(void) {
    memset(&g_mock_serial, 0, sizeof(g_mock_serial));
}

void mock_serial_set_input(const char* data) {
    g_mock_serial.rx_len = strlen(data);
    if (g_mock_serial.rx_len >= MOCK_SERIAL_BUF_SIZE) {
        g_mock_serial.rx_len = MOCK_SERIAL_BUF_SIZE - 1;
    }
    memcpy(g_mock_serial.rx_buffer, data, g_mock_serial.rx_len);
    g_mock_serial.rx_pos = 0;
}

int mock_serial_read(uint8_t* buf, size_t len) {
    size_t available = g_mock_serial.rx_len - g_mock_serial.rx_pos;
    if (available == 0)
        return 0;
    if (len > available)
        len = available;
    memcpy(buf, g_mock_serial.rx_buffer + g_mock_serial.rx_pos, len);
    g_mock_serial.rx_pos += len;
    return (int)len;
}

int mock_serial_write(const uint8_t* buf, size_t len) {
    size_t space = MOCK_SERIAL_BUF_SIZE - g_mock_serial.tx_len - 1;
    if (len > space)
        len = space;
    memcpy(g_mock_serial.tx_buffer + g_mock_serial.tx_len, buf, len);
    g_mock_serial.tx_len += len;
    g_mock_serial.tx_buffer[g_mock_serial.tx_len] = '\0';
    return (int)len;
}

int mock_serial_available(void) {
    return (int)(g_mock_serial.rx_len - g_mock_serial.rx_pos);
}

const char* mock_serial_get_output(void) {
    return g_mock_serial.tx_buffer;
}

/* ============================================================================
 * Mock Output Capture
 * ============================================================================ */

char g_mock_output_buffer[MOCK_OUTPUT_BUF_SIZE];
size_t g_mock_output_len = 0;

void mock_output_reset(void) {
    g_mock_output_buffer[0] = '\0';
    g_mock_output_len = 0;
}

void mock_output_cb(void* user, const char* str) {
    (void)user;
    size_t len = strlen(str);
    size_t space = MOCK_OUTPUT_BUF_SIZE - g_mock_output_len - 1;
    if (len > space)
        len = space;
    memcpy(g_mock_output_buffer + g_mock_output_len, str, len);
    g_mock_output_len += len;
    g_mock_output_buffer[g_mock_output_len] = '\0';
}

const char* mock_output_get(void) {
    return g_mock_output_buffer;
}

bool mock_output_contains(const char* substr) {
    return strstr(g_mock_output_buffer, substr) != NULL;
}

/* ============================================================================
 * Mock Memory Allocator
 * ============================================================================ */

static uint8_t g_mock_heap[MOCK_HEAP_SIZE];
static size_t g_mock_heap_pos = 0;

void mock_heap_reset(void) {
    g_mock_heap_pos = 0;
    memset(g_mock_heap, 0, sizeof(g_mock_heap));
    g_mock_call_stats.malloc_count = 0;
    g_mock_call_stats.free_count = 0;
    g_mock_call_stats.total_allocated = 0;
    g_mock_call_stats.total_freed = 0;
}

void* mock_malloc(size_t size) {
    /* Align to 8 bytes */
    size = (size + 7) & ~7;
    if (g_mock_heap_pos + size > MOCK_HEAP_SIZE) {
        return NULL;
    }
    void* ptr = &g_mock_heap[g_mock_heap_pos];
    g_mock_heap_pos += size;
    g_mock_call_stats.malloc_count++;
    g_mock_call_stats.total_allocated += size;
    return ptr;
}

void mock_free(void* ptr) {
    (void)ptr; /* Simple bump allocator, no actual free */
    g_mock_call_stats.free_count++;
}
