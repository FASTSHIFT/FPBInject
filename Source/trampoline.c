/**
 * @file   trampoline.c
 * @brief  Trampoline functions for FPB injection
 *
 * These functions are placed in Flash and serve as intermediate jump points.
 * FPB REMAP redirects to these trampolines, which then jump to RAM code.
 *
 * Flow: Original Function -> (FPB REMAP) -> Trampoline -> (indirect jump) -> RAM Code
 *
 * This approach avoids runtime Flash modification while still allowing
 * dynamic code injection to RAM.
 */

#include <stdint.h>

/**
 * RAM location where target addresses are stored.
 * Each FPB comparator has a corresponding slot:
 *   trampoline_targets[0] = target for comparator 0
 *   trampoline_targets[1] = target for comparator 1
 *   ...
 */
#define TRAMPOLINE_TARGET_COUNT  6  /* STM32F103 has 6 FPB comparators */

/* Target address table in RAM - initialized to 0 (no redirect) */
volatile uint32_t trampoline_targets[TRAMPOLINE_TARGET_COUNT] __attribute__((section(".noinit")));

/**
 * Default handler when trampoline target is not set.
 * This prevents crash if FPB is enabled but target not configured.
 */
__attribute__((naked))
void trampoline_default(void) {
    __asm volatile(
        "bx lr\n"  /* Just return */
    );
}

/**
 * Trampoline 0 - for FPB comparator 0
 * Loads target address from trampoline_targets[0] and jumps to it.
 * Uses R12 as scratch register (caller-saved, safe to clobber).
 */
__attribute__((naked, section(".trampoline")))
void trampoline_0(void) {
    __asm volatile(
        "push {r12}\n"                      /* Save R12 */
        "ldr r12, =trampoline_targets\n"    /* Load base address */
        "ldr r12, [r12, #0]\n"              /* Load target[0] */
        "cmp r12, #0\n"                     /* Check if target is set */
        "beq 1f\n"                          /* If zero, return */
        "str r12, [sp]\n"                   /* Store target on stack */
        "pop {pc}\n"                        /* Pop to PC (jump) */
        "1:\n"
        "pop {r12}\n"                       /* Restore R12 */
        "bx lr\n"                           /* Return if no target */
    );
}

/**
 * Trampoline 1 - for FPB comparator 1
 */
__attribute__((naked, section(".trampoline")))
void trampoline_1(void) {
    __asm volatile(
        "push {r12}\n"
        "ldr r12, =trampoline_targets\n"
        "ldr r12, [r12, #4]\n"              /* Load target[1] */
        "cmp r12, #0\n"
        "beq 1f\n"
        "str r12, [sp]\n"
        "pop {pc}\n"
        "1:\n"
        "pop {r12}\n"
        "bx lr\n"
    );
}

/**
 * Trampoline 2 - for FPB comparator 2
 */
__attribute__((naked, section(".trampoline")))
void trampoline_2(void) {
    __asm volatile(
        "push {r12}\n"
        "ldr r12, =trampoline_targets\n"
        "ldr r12, [r12, #8]\n"              /* Load target[2] */
        "cmp r12, #0\n"
        "beq 1f\n"
        "str r12, [sp]\n"
        "pop {pc}\n"
        "1:\n"
        "pop {r12}\n"
        "bx lr\n"
    );
}

/**
 * Trampoline 3 - for FPB comparator 3
 */
__attribute__((naked, section(".trampoline")))
void trampoline_3(void) {
    __asm volatile(
        "push {r12}\n"
        "ldr r12, =trampoline_targets\n"
        "ldr r12, [r12, #12]\n"             /* Load target[3] */
        "cmp r12, #0\n"
        "beq 1f\n"
        "str r12, [sp]\n"
        "pop {pc}\n"
        "1:\n"
        "pop {r12}\n"
        "bx lr\n"
    );
}

/**
 * Trampoline 4 - for FPB comparator 4
 */
__attribute__((naked, section(".trampoline")))
void trampoline_4(void) {
    __asm volatile(
        "push {r12}\n"
        "ldr r12, =trampoline_targets\n"
        "ldr r12, [r12, #16]\n"             /* Load target[4] */
        "cmp r12, #0\n"
        "beq 1f\n"
        "str r12, [sp]\n"
        "pop {pc}\n"
        "1:\n"
        "pop {r12}\n"
        "bx lr\n"
    );
}

/**
 * Trampoline 5 - for FPB comparator 5
 */
__attribute__((naked, section(".trampoline")))
void trampoline_5(void) {
    __asm volatile(
        "push {r12}\n"
        "ldr r12, =trampoline_targets\n"
        "ldr r12, [r12, #20]\n"             /* Load target[5] */
        "cmp r12, #0\n"
        "beq 1f\n"
        "str r12, [sp]\n"
        "pop {pc}\n"
        "1:\n"
        "pop {r12}\n"
        "bx lr\n"
    );
}

/* Trampoline address table (in Flash, for lookup) */
void (* const trampoline_table[TRAMPOLINE_TARGET_COUNT])(void) = {
    trampoline_0,
    trampoline_1,
    trampoline_2,
    trampoline_3,
    trampoline_4,
    trampoline_5,
};

/**
 * @brief  Set trampoline target for a specific comparator
 * @param  comp: Comparator index (0-5)
 * @param  target: Target address (with Thumb bit set)
 */
void trampoline_set_target(uint32_t comp, uint32_t target) {
    if (comp < TRAMPOLINE_TARGET_COUNT) {
        trampoline_targets[comp] = target;
    }
}

/**
 * @brief  Clear trampoline target
 * @param  comp: Comparator index (0-5)
 */
void trampoline_clear_target(uint32_t comp) {
    if (comp < TRAMPOLINE_TARGET_COUNT) {
        trampoline_targets[comp] = 0;
    }
}

/**
 * @brief  Get trampoline function address for a comparator
 * @param  comp: Comparator index (0-5)
 * @return Trampoline function address (with Thumb bit)
 */
uint32_t trampoline_get_address(uint32_t comp) {
    if (comp < TRAMPOLINE_TARGET_COUNT) {
        return (uint32_t)trampoline_table[comp] | 1;  /* Add Thumb bit */
    }
    return 0;
}
