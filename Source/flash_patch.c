/**
 * @file   flash_patch.c
 * @brief  Flash programming for runtime code patching
 *
 * Uses STM32 Standard Peripheral Library for Flash operations.
 */

#include "flash_patch.h"
#include "stm32f10x.h"
#include "stm32f10x_flash.h"
#include <string.h>

/* STM32F103 Flash parameters */
#define FLASH_PAGE_SIZE 1024 /* 1KB pages for Medium Density */
#define FLASH_BASE_ADDR 0x08000000
#define FLASH_END_ADDR 0x08010000 /* 64KB for STM32F103C8 */

/* Page backup buffer */
static uint8_t s_page_backup[FLASH_PAGE_SIZE] __attribute__((aligned(4)));

/**
 * @brief  Patch a function in Flash to jump to a new address
 *
 * Uses an 8-byte trampoline:
 *   LDR PC, [PC, #0]   ; 0xF000F8DF (Thumb-2, loads from PC+4)
 *   DCD target_addr    ; absolute address (with Thumb bit)
 *
 * This allows jumping anywhere in the 32-bit address space.
 *
 * @param  original_addr: Address of the original function (in Flash)
 * @param  target_addr: Address to jump to (can be in RAM, must have Thumb bit set)
 * @return 0 on success, negative on error
 */
int flash_patch_function(uint32_t original_addr, uint32_t target_addr) {
    /* Validate addresses */
    if (original_addr < FLASH_BASE_ADDR || original_addr >= FLASH_END_ADDR) {
        return -1; /* Not in Flash */
    }

    /* Align to half-word (clear Thumb bit for address calculation) */
    original_addr &= ~1UL;

    /* Ensure target has Thumb bit set for BX/LDR PC */
    target_addr |= 1;

    /* Calculate page base and offset */
    uint32_t page_base = original_addr & ~(FLASH_PAGE_SIZE - 1);
    uint32_t offset_in_page = original_addr - page_base;

    /* Check if we have enough space (8 bytes for LDR PC + address) */
    if (offset_in_page + 8 > FLASH_PAGE_SIZE) {
        return -3; /* Not enough space in page */
    }

    /* Backup the entire page */
    memcpy(s_page_backup, (void*)page_base, FLASH_PAGE_SIZE);

    /*
     * Generate 8-byte trampoline:
     * LDR PC, [PC, #0]  - Thumb-2 encoding: 0xF8DF, 0xF000
     *                   - This loads PC from address (PC + 4 + 0) = current + 4
     * DCD target_addr   - The absolute target address
     */
    uint16_t ldr_pc_hw1 = 0xF8DF; /* LDR.W Rt, [PC, #imm12] with Rt=PC(15) */
    uint16_t ldr_pc_hw2 = 0xF000; /* imm12=0, Rt=15 (PC) */

    /* Write LDR PC, [PC, #0] */
    s_page_backup[offset_in_page + 0] = (ldr_pc_hw1 >> 0) & 0xFF;
    s_page_backup[offset_in_page + 1] = (ldr_pc_hw1 >> 8) & 0xFF;
    s_page_backup[offset_in_page + 2] = (ldr_pc_hw2 >> 0) & 0xFF;
    s_page_backup[offset_in_page + 3] = (ldr_pc_hw2 >> 8) & 0xFF;

    /* Write target address (little-endian) */
    s_page_backup[offset_in_page + 4] = (target_addr >> 0) & 0xFF;
    s_page_backup[offset_in_page + 5] = (target_addr >> 8) & 0xFF;
    s_page_backup[offset_in_page + 6] = (target_addr >> 16) & 0xFF;
    s_page_backup[offset_in_page + 7] = (target_addr >> 24) & 0xFF;

    /* Disable interrupts during Flash operations */
    uint32_t primask;
    __asm volatile("MRS %0, PRIMASK\n CPSID I" : "=r"(primask));

    /* Unlock Flash */
    FLASH_Unlock();

    /* Erase the page */
    FLASH_Status status = FLASH_ErasePage(page_base);
    if (status != FLASH_COMPLETE) {
        FLASH_Lock();
        __asm volatile("MSR PRIMASK, %0" ::"r"(primask));
        return -2; /* Erase failed */
    }

    /* Write back the modified page (half-word at a time) */
    uint16_t* src = (uint16_t*)s_page_backup;
    uint32_t addr = page_base;

    for (int i = 0; i < FLASH_PAGE_SIZE / 2; i++) {
        status = FLASH_ProgramHalfWord(addr, src[i]);
        if (status != FLASH_COMPLETE) {
            FLASH_Lock();
            __asm volatile("MSR PRIMASK, %0" ::"r"(primask));
            return -3; /* Program failed */
        }
        addr += 2;
    }

    /* Lock Flash */
    FLASH_Lock();

    /* Restore interrupts */
    __asm volatile("MSR PRIMASK, %0" ::"r"(primask));

    /* Clear instruction cache / pipeline */
    __asm volatile("DSB");
    __asm volatile("ISB");

    return 0;
}

/**
 * @brief  Get the original instruction at an address (for restoration)
 * @param  addr: Address to read
 * @return 32-bit value at the address
 */
uint32_t flash_read_instruction(uint32_t addr) {
    addr &= ~1UL;
    return *(volatile uint32_t*)addr;
}
