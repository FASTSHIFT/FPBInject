/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Mock FPB registers implementation for host-based testing
 *
 * The FPB_CTRL register has read-only bits for num_code and num_lit.
 * We simulate this by storing these separately and combining on read.
 * Since we can't intercept writes directly with a simple macro,
 * we use a post-write hook approach.
 */

#include "fpb_mock_regs.h"
#include <string.h>

/* Mock FPB register storage */
uint32_t mock_fpb_ctrl_rw = 0; /* R/W bits written by code */
uint32_t mock_fpb_ctrl_ro = 0; /* R/O bits (num_code, num_lit) - set by configure */
uint32_t mock_fpb_remap = 0;
uint32_t mock_fpb_comp[10] = {0}; /* 8 code + 2 literal comparators (FPB_MAX_COMP) */

/* Mock debug registers for debugmon testing */
uint32_t mock_dhcsr = 0;
uint32_t mock_demcr = 0;
uint32_t mock_dfsr = 0;

/* Combined register that the code reads/writes */
static uint32_t mock_fpb_ctrl_combined = 0;

/* FPB CTRL register bits */
#define FPB_CTRL_NUM_CODE_SHIFT 4
#define FPB_CTRL_NUM_LIT_SHIFT 8

uint32_t fpb_mock_ctrl_read(void) {
    /* Always return combined with R/O bits preserved */
    return (mock_fpb_ctrl_combined & ~FPB_CTRL_RO_MASK) | mock_fpb_ctrl_ro;
}

void fpb_mock_ctrl_write(uint32_t value) {
    /* Store the written value but preserve R/O bits on next read */
    mock_fpb_ctrl_combined = value;
}

uint32_t* fpb_mock_get_ctrl_ptr(void) {
    /* Before returning pointer, ensure R/O bits are present for reads */
    mock_fpb_ctrl_combined = (mock_fpb_ctrl_combined & ~FPB_CTRL_RO_MASK) | mock_fpb_ctrl_ro;
    return &mock_fpb_ctrl_combined;
}

void fpb_mock_reset(void) {
    mock_fpb_ctrl_rw = 0;
    mock_fpb_ctrl_ro = 0;
    mock_fpb_ctrl_combined = 0;
    mock_fpb_remap = 0;
    memset(mock_fpb_comp, 0, sizeof(mock_fpb_comp));

    /* Reset debug registers */
    mock_dhcsr = 0;
    mock_demcr = 0;
    mock_dfsr = 0;
}

void fpb_mock_configure(uint8_t num_code, uint8_t num_lit) {
    /* Reset registers */
    fpb_mock_reset();

    /* Configure R/O bits with number of comparators */
    mock_fpb_ctrl_ro = ((uint32_t)num_code << FPB_CTRL_NUM_CODE_SHIFT) | ((uint32_t)num_lit << FPB_CTRL_NUM_LIT_SHIFT);
    mock_fpb_ctrl_combined = mock_fpb_ctrl_ro;

    /* Configure FP_REMAP with RMPSPT bit set (bit 29 = remap supported) */
    mock_fpb_remap = (1UL << 29);
}

void fpb_mock_set_dfsr(uint32_t value) {
    mock_dfsr = value;
}

uint32_t fpb_mock_get_demcr(void) {
    return mock_demcr;
}
