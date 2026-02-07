/**
 * @file nuttx_mock.h
 * @brief Testable NuttX mock API declarations
 *
 * This header provides mock implementations of NuttX APIs for host-based
 * unit testing. Unlike the static inline versions in individual headers,
 * these are proper functions that can be used to verify calls and state.
 */

#ifndef __NUTTX_MOCK_H
#define __NUTTX_MOCK_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================================
 * Debugpoint Mock API
 * ============================================================================ */

/* Debugpoint types (match NuttX) */
#define DEBUGPOINT_BREAKPOINT    1
#define DEBUGPOINT_STEPPOINT     2
#define DEBUGPOINT_WATCHPOINT_RO 3
#define DEBUGPOINT_WATCHPOINT_WO 4
#define DEBUGPOINT_WATCHPOINT_RW 5

/* Debugpoint callback type */
typedef void (*debug_callback_t)(int type, void* addr, size_t size, void* arg);

/* NuttX debugpoint API - mock implementations */
int up_debugpoint_add(int type, void* addr, size_t size,
                      debug_callback_t callback, void* arg);
int up_debugpoint_remove(int type, void* addr, size_t size);

/* ============================================================================
 * IRQ Mock API
 * ============================================================================ */

typedef int (*xcpt_t)(int irq, void* context, void* arg);

int irq_attach(int irq, xcpt_t handler, void* arg);
void up_enable_irq(int irq);
void up_disable_irq(int irq);

/* ============================================================================
 * Register Context Mock API
 * ============================================================================ */

/* IRQ related register offsets - Cortex-M style */
#define REG_R0   0
#define REG_R1   1
#define REG_R2   2
#define REG_R3   3
#define REG_R12  4
#define REG_R14  5 /* LR */
#define REG_R15  6 /* PC */
#define REG_XPSR 7
#define REG_PC   REG_R15

/* Get current task's register context */
uint32_t* running_regs(void);

/* ============================================================================
 * DebugMonitor Mock API
 * ============================================================================ */

#define CONFIG_ARCH_HAVE_DEBUG 1
#define NVIC_IRQ_DBGMONITOR    12

int arm_enable_dbgmonitor(void);
int arm_dbgmonitor(int irq, void* context, void* arg);

/* ============================================================================
 * Test Helper Functions
 * ============================================================================ */

/**
 * @brief Reset all mock state to initial values
 */
void nuttx_mock_reset(void);

/**
 * @brief Set PC register value in mock context
 */
void nuttx_mock_set_pc(uint32_t pc);

/**
 * @brief Get PC register value from mock context
 */
uint32_t nuttx_mock_get_pc(void);

/**
 * @brief Check if debug monitor is enabled
 */
bool nuttx_mock_debugmon_is_enabled(void);

/**
 * @brief Get count of active debugpoints
 */
int nuttx_mock_get_debugpoint_count(void);

/**
 * @brief Simulate a breakpoint hit at given address
 * @return 0 if breakpoint found and callback called, -1 otherwise
 */
int nuttx_mock_trigger_breakpoint(uint32_t addr);

/**
 * @brief Get the last attached IRQ handler
 */
xcpt_t nuttx_mock_get_irq_handler(int irq);

#ifdef __cplusplus
}
#endif

#endif /* __NUTTX_MOCK_H */
