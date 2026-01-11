/**
 * @file   fault_handler.c
 * @brief  HardFault handler with diagnostic output
 */

#include <stdint.h>
#include "stm32f10x.h"

/* Forward declaration for printf-like output */
extern int _write(int fd, char *ptr, int len);

static void fault_print(const char *str) {
    int len = 0;
    while (str[len]) len++;
    _write(1, (char*)str, len);
}

static void fault_print_hex(uint32_t val) {
    char buf[12];
    buf[0] = '0';
    buf[1] = 'x';
    for (int i = 0; i < 8; i++) {
        int nibble = (val >> (28 - i * 4)) & 0xF;
        buf[2 + i] = nibble < 10 ? '0' + nibble : 'A' + nibble - 10;
    }
    buf[10] = '\0';
    fault_print(buf);
}

/**
 * @brief  HardFault handler - prints diagnostic info
 * @note   This function is called when a HardFault occurs
 */
void HardFault_Handler(void) {
    /* Get stacked registers */
    __asm volatile(
        "TST LR, #4\n"
        "ITE EQ\n"
        "MRSEQ R0, MSP\n"
        "MRSNE R0, PSP\n"
        "B HardFault_Handler_C\n"
    );
}

void HardFault_Handler_C(uint32_t *stack) {
    /* Stack contains: R0, R1, R2, R3, R12, LR, PC, xPSR */
    uint32_t r0 = stack[0];
    uint32_t r1 = stack[1];
    uint32_t r2 = stack[2];
    uint32_t r3 = stack[3];
    uint32_t r12 = stack[4];
    uint32_t lr = stack[5];
    uint32_t pc = stack[6];
    uint32_t psr = stack[7];

    /* Get fault status registers */
    uint32_t cfsr = SCB->CFSR;
    uint32_t hfsr = SCB->HFSR;
    uint32_t bfar = SCB->BFAR;
    uint32_t mmfar = SCB->MMFAR;

    fault_print("\r\n\r\n*** HARD FAULT ***\r\n");

    fault_print("PC:  "); fault_print_hex(pc); fault_print("\r\n");
    fault_print("LR:  "); fault_print_hex(lr); fault_print("\r\n");
    fault_print("R0:  "); fault_print_hex(r0); fault_print("\r\n");
    fault_print("R1:  "); fault_print_hex(r1); fault_print("\r\n");
    fault_print("R2:  "); fault_print_hex(r2); fault_print("\r\n");
    fault_print("R3:  "); fault_print_hex(r3); fault_print("\r\n");
    fault_print("R12: "); fault_print_hex(r12); fault_print("\r\n");
    fault_print("PSR: "); fault_print_hex(psr); fault_print("\r\n");

    fault_print("\r\nFault Status:\r\n");
    fault_print("CFSR:  "); fault_print_hex(cfsr); fault_print("\r\n");
    fault_print("HFSR:  "); fault_print_hex(hfsr); fault_print("\r\n");

    if (cfsr & 0x80) {
        fault_print("MMFAR: "); fault_print_hex(mmfar); fault_print("\r\n");
    }
    if (cfsr & 0x8000) {
        fault_print("BFAR:  "); fault_print_hex(bfar); fault_print("\r\n");
    }

    /* Decode common faults */
    if (cfsr & 0x01) fault_print("  IACCVIOL: Instruction access violation\r\n");
    if (cfsr & 0x02) fault_print("  DACCVIOL: Data access violation\r\n");
    if (cfsr & 0x08) fault_print("  MUNSTKERR: Unstacking error\r\n");
    if (cfsr & 0x10) fault_print("  MSTKERR: Stacking error\r\n");

    if (cfsr & 0x0100) fault_print("  IBUSERR: Instruction bus error\r\n");
    if (cfsr & 0x0200) fault_print("  PRECISERR: Precise data bus error\r\n");
    if (cfsr & 0x0400) fault_print("  IMPRECISERR: Imprecise data bus error\r\n");
    if (cfsr & 0x0800) fault_print("  UNSTKERR: Unstacking bus error\r\n");
    if (cfsr & 0x1000) fault_print("  STKERR: Stacking bus error\r\n");

    if (cfsr & 0x010000) fault_print("  UNDEFINSTR: Undefined instruction\r\n");
    if (cfsr & 0x020000) fault_print("  INVSTATE: Invalid state\r\n");
    if (cfsr & 0x040000) fault_print("  INVPC: Invalid PC\r\n");
    if (cfsr & 0x080000) fault_print("  NOCP: No coprocessor\r\n");
    if (cfsr & 0x01000000) fault_print("  UNALIGNED: Unaligned access\r\n");
    if (cfsr & 0x02000000) fault_print("  DIVBYZERO: Divide by zero\r\n");

    if (hfsr & 0x40000000) fault_print("  FORCED: Escalated from configurable fault\r\n");
    if (hfsr & 0x02) fault_print("  VECTTBL: Vector table hard fault\r\n");

    fault_print("\r\n*** HALTED ***\r\n");

    /* Halt */
    while (1) {
        __asm volatile("BKPT #0");
    }
}
