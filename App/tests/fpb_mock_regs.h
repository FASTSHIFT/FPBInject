/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Mock FPB registers for host-based unit testing
 *
 * This header provides mock implementations of FPB hardware registers
 * and ARM barrier instructions for testing fpb_inject.c on host systems.
 */

#ifndef __FPB_MOCK_REGS_H
#define __FPB_MOCK_REGS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Mock FPB registers - defined in fpb_mock_regs.c */
extern uint32_t mock_fpb_ctrl_rw; /* R/W bits (enable, key, etc.) */
extern uint32_t mock_fpb_ctrl_ro; /* R/O bits (num_code, num_lit) */
extern uint32_t mock_fpb_remap;
extern uint32_t mock_fpb_comp[8];

/* FPB_CTRL mask for read-only bits (num_code at bits 7:4, num_lit at bits 11:8) */
#define FPB_CTRL_RO_MASK 0x00000FF0

/* Override FPB register access macros with read/write separation */
#undef FPB_CTRL
#undef FPB_REMAP
#undef FPB_COMP

/* FPB_CTRL read: combine R/W and R/O bits */
/* FPB_CTRL write: only modify R/W bits, preserve R/O bits */
uint32_t fpb_mock_ctrl_read(void);
void fpb_mock_ctrl_write(uint32_t value);

#define FPB_CTRL_READ fpb_mock_ctrl_read()
#define FPB_CTRL_WRITE(val) fpb_mock_ctrl_write(val)

/* For read-modify-write patterns in the real code, we need a workaround */
/* The real code does: FPB_CTRL = value; to write */
/* We can't override assignment easily, so we'll use the simple approach */
/* and make the mock smarter about preserving RO bits */
#define FPB_CTRL (*fpb_mock_get_ctrl_ptr())
uint32_t* fpb_mock_get_ctrl_ptr(void);

#define FPB_REMAP mock_fpb_remap
#define FPB_COMP(n) mock_fpb_comp[n]

/* Mock debug registers for debugmon testing */
extern uint32_t mock_dhcsr;
extern uint32_t mock_demcr;
extern uint32_t mock_dfsr;

/* Override memory barrier instructions (no-op on host) */
#undef dsb
#undef isb

static inline void dsb(void) {
    /* No-op on host */
}

static inline void isb(void) {
    /* No-op on host */
}

/* Mock control functions */
void fpb_mock_reset(void);
void fpb_mock_configure(uint8_t num_code, uint8_t num_lit);

/* Mock debug register control */
void fpb_mock_set_dfsr(uint32_t value);
uint32_t fpb_mock_get_demcr(void);

#ifdef __cplusplus
}
#endif

#endif /* __FPB_MOCK_REGS_H */
