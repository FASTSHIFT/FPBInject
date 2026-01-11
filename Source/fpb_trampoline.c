/**
 * @file   fpb_trampoline.c
 * @brief  Trampoline functions for FPB injection
 *
 * These functions are placed in Flash and serve as intermediate jump points.
 * FPB REMAP redirects to these trampolines, which then jump to RAM code.
 *
 * Flow: Original Function -> (FPB REMAP) -> Trampoline -> (indirect jump) -> RAM Code
 *
 * This approach avoids runtime Flash modification while still allowing
 * dynamic code injection to RAM.
 *
 * Configuration macros (defined via CMake options):
 *   FPB_NO_TRAMPOLINE    - Disable trampoline entirely (when FPB can REMAP to RAM directly)
 *   FPB_TRAMPOLINE_NO_ASM - Use simple C instead of assembly (no argument preservation)
 */

#include "fpb_trampoline.h"

#ifndef FPB_NO_TRAMPOLINE

/**
 * When FPB_TRAMPOLINE_NO_ASM is NOT defined (default):
 *   - Uses inline assembly to jump without disturbing R0-R3
 *   - Required when the injected code needs the original function's arguments
 *   - Slightly larger code size
 *
 * When FPB_TRAMPOLINE_NO_ASM is defined:
 *   - Uses simple C function pointer call
 *   - Arguments may be clobbered before reaching injected code
 *   - Suitable for hooks that don't need original arguments
 *   - Smaller code size, no assembly dependency
 */

/* Target address table in RAM - initialized to 0 (no redirect) */
volatile uint32_t fpb_trampoline_targets[FPB_TRAMPOLINE_COUNT] __attribute__((section(".noinit")));

#ifndef FPB_TRAMPOLINE_NO_ASM
/*============================================================================
 * Assembly-based trampolines (preserve function arguments in R0-R3)
 *============================================================================*/

/**
 * Macro to define a trampoline function with preserved arguments.
 * Uses R12 as scratch register (caller-saved, safe to clobber).
 *
 * @param n  Trampoline index (0-5)
 */
#define DEFINE_TRAMPOLINE_ASM(n)                                              \
    __attribute__((naked, section(".trampoline")))                            \
    void fpb_trampoline_##n(void) {                                           \
        __asm volatile(                                                       \
            "push {r12}\n"                      /* Save R12 */                \
            "ldr r12, =fpb_trampoline_targets\n" /* Load base address */      \
            "ldr r12, [r12, %0]\n"              /* Load target[n] */          \
            "cmp r12, #0\n"                     /* Check if target is set */  \
            "beq 1f\n"                          /* If zero, return */         \
            "str r12, [sp]\n"                   /* Store target on stack */   \
            "pop {pc}\n"                        /* Pop to PC (jump) */        \
            "1:\n"                                                            \
            "pop {r12}\n"                       /* Restore R12 */             \
            "bx lr\n"                           /* Return if no target */     \
            :                                                                 \
            : "i" ((n) * 4)                     /* Immediate offset */        \
        );                                                                    \
    }

/* Generate all 6 trampolines */
DEFINE_TRAMPOLINE_ASM(0)
DEFINE_TRAMPOLINE_ASM(1)
DEFINE_TRAMPOLINE_ASM(2)
DEFINE_TRAMPOLINE_ASM(3)
DEFINE_TRAMPOLINE_ASM(4)
DEFINE_TRAMPOLINE_ASM(5)

#else /* FPB_TRAMPOLINE_NO_ASM */
/*============================================================================
 * C-based trampolines (simpler, but don't preserve arguments)
 *============================================================================*/

typedef void (*fpb_trampoline_func_t)(void);

/**
 * Macro to define a simple C trampoline function.
 * Arguments are NOT preserved - suitable for no-args hooks only.
 *
 * @param n  Trampoline index (0-5)
 */
#define DEFINE_TRAMPOLINE_C(n)                                                \
    __attribute__((section(".trampoline")))                                   \
    void fpb_trampoline_##n(void) {                                           \
        if (fpb_trampoline_targets[n]) {                                      \
            ((fpb_trampoline_func_t)(fpb_trampoline_targets[n] & ~1u))();     \
        }                                                                     \
    }

/* Generate all 6 trampolines */
DEFINE_TRAMPOLINE_C(0)
DEFINE_TRAMPOLINE_C(1)
DEFINE_TRAMPOLINE_C(2)
DEFINE_TRAMPOLINE_C(3)
DEFINE_TRAMPOLINE_C(4)
DEFINE_TRAMPOLINE_C(5)

#endif /* FPB_TRAMPOLINE_NO_ASM */

/* Trampoline address table (in Flash, for lookup) */
void (* const fpb_trampoline_table[FPB_TRAMPOLINE_COUNT])(void) = {
    fpb_trampoline_0,
    fpb_trampoline_1,
    fpb_trampoline_2,
    fpb_trampoline_3,
    fpb_trampoline_4,
    fpb_trampoline_5,
};

void fpb_trampoline_set_target(uint32_t comp, uint32_t target) {
    if (comp < FPB_TRAMPOLINE_COUNT) {
        fpb_trampoline_targets[comp] = target;
    }
}

void fpb_trampoline_clear_target(uint32_t comp) {
    if (comp < FPB_TRAMPOLINE_COUNT) {
        fpb_trampoline_targets[comp] = 0;
    }
}

uint32_t fpb_trampoline_get_address(uint32_t comp) {
    if (comp < FPB_TRAMPOLINE_COUNT) {
        return (uint32_t)fpb_trampoline_table[comp] | 1;  /* Add Thumb bit */
    }
    return 0;
}

#endif /* !FPB_NO_TRAMPOLINE */
