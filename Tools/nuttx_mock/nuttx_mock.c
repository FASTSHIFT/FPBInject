/**
 * @file nuttx_mock.c
 * @brief Testable NuttX mock implementations
 *
 * Provides mock implementations of NuttX APIs for host-based unit testing.
 * These track state and allow verification of calls.
 */

#include "nuttx_mock.h"
#include <string.h>
#include <stdio.h>

/* ============================================================================
 * Mock State
 * ============================================================================ */

/* Debugpoint storage */
#define MAX_MOCK_DEBUGPOINTS 8

typedef struct {
    bool active;
    int type;
    void* addr;
    size_t size;
    debug_callback_t callback;
    void* arg;
} mock_debugpoint_t;

static mock_debugpoint_t g_mock_debugpoints[MAX_MOCK_DEBUGPOINTS];

/* Register context */
#define NUM_REGS 32
static uint32_t g_mock_regs[NUM_REGS];

/* Debug monitor state */
static bool g_mock_debugmon_enabled = false;

/* IRQ handlers */
#define MAX_IRQS 256
static xcpt_t g_mock_irq_handlers[MAX_IRQS];
static void* g_mock_irq_args[MAX_IRQS];

/* ============================================================================
 * Debugpoint API Implementation
 * ============================================================================ */

int up_debugpoint_add(int type, void* addr, size_t size,
                      debug_callback_t callback, void* arg) {
    for (int i = 0; i < MAX_MOCK_DEBUGPOINTS; i++) {
        if (!g_mock_debugpoints[i].active) {
            g_mock_debugpoints[i].active = true;
            g_mock_debugpoints[i].type = type;
            g_mock_debugpoints[i].addr = addr;
            g_mock_debugpoints[i].size = size;
            g_mock_debugpoints[i].callback = callback;
            g_mock_debugpoints[i].arg = arg;
            return 0;
        }
    }
    return -1; /* No free slot */
}

int up_debugpoint_remove(int type, void* addr, size_t size) {
    for (int i = 0; i < MAX_MOCK_DEBUGPOINTS; i++) {
        if (g_mock_debugpoints[i].active &&
            g_mock_debugpoints[i].type == type &&
            g_mock_debugpoints[i].addr == addr &&
            g_mock_debugpoints[i].size == size) {
            g_mock_debugpoints[i].active = false;
            return 0;
        }
    }
    return -1;
}

/* ============================================================================
 * IRQ API Implementation
 * ============================================================================ */

int irq_attach(int irq, xcpt_t handler, void* arg) {
    if (irq < 0 || irq >= MAX_IRQS) {
        return -1;
    }
    g_mock_irq_handlers[irq] = handler;
    g_mock_irq_args[irq] = arg;
    return 0;
}

void up_enable_irq(int irq) {
    (void)irq;
    /* No-op for mock */
}

void up_disable_irq(int irq) {
    (void)irq;
    /* No-op for mock */
}

/* ============================================================================
 * Register Context Implementation
 * ============================================================================ */

uint32_t* running_regs(void) {
    return g_mock_regs;
}

/* ============================================================================
 * DebugMonitor Implementation
 * ============================================================================ */

int arm_enable_dbgmonitor(void) {
    g_mock_debugmon_enabled = true;
    return 0;
}

int arm_dbgmonitor(int irq, void* context, void* arg) {
    (void)irq;
    (void)context;
    (void)arg;
    return 0;
}

/* ============================================================================
 * Test Helper Functions
 * ============================================================================ */

void nuttx_mock_reset(void) {
    memset(g_mock_debugpoints, 0, sizeof(g_mock_debugpoints));
    memset(g_mock_regs, 0, sizeof(g_mock_regs));
    memset(g_mock_irq_handlers, 0, sizeof(g_mock_irq_handlers));
    memset(g_mock_irq_args, 0, sizeof(g_mock_irq_args));
    g_mock_debugmon_enabled = false;
}

void nuttx_mock_set_pc(uint32_t pc) {
    g_mock_regs[REG_PC] = pc;
}

uint32_t nuttx_mock_get_pc(void) {
    return g_mock_regs[REG_PC];
}

bool nuttx_mock_debugmon_is_enabled(void) {
    return g_mock_debugmon_enabled;
}

int nuttx_mock_get_debugpoint_count(void) {
    int count = 0;
    for (int i = 0; i < MAX_MOCK_DEBUGPOINTS; i++) {
        if (g_mock_debugpoints[i].active) {
            count++;
        }
    }
    return count;
}

int nuttx_mock_trigger_breakpoint(uint32_t addr) {
    for (int i = 0; i < MAX_MOCK_DEBUGPOINTS; i++) {
        if (g_mock_debugpoints[i].active &&
            (uint32_t)(uintptr_t)g_mock_debugpoints[i].addr == (addr & ~1UL)) {
            /* Simulate breakpoint hit */
            g_mock_regs[REG_PC] = addr;
            if (g_mock_debugpoints[i].callback) {
                g_mock_debugpoints[i].callback(
                    g_mock_debugpoints[i].type,
                    g_mock_debugpoints[i].addr,
                    g_mock_debugpoints[i].size,
                    g_mock_debugpoints[i].arg);
            }
            return 0;
        }
    }
    return -1; /* No matching breakpoint */
}

xcpt_t nuttx_mock_get_irq_handler(int irq) {
    if (irq < 0 || irq >= MAX_IRQS) {
        return NULL;
    }
    return g_mock_irq_handlers[irq];
}
