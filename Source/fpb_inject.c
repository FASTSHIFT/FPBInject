/**
 * @file   fpb_inject.c
 * @brief  Cortex-M3/M4 Flash Patch and Breakpoint (FPB) 单元驱动实现
 * 
 * 本文件实现了FPB运行时代码注入功能。
 * 
 * FPB工作原理:
 * 1. FPB硬件监控CPU的指令取指地址
 * 2. 当地址匹配比较器设置的地址时，FPB进行拦截
 * 3. FPB可以返回替换指令或从重映射区域获取指令
 * 
 * 代码注入实现方式:
 * - 方式1: 使用REMAP功能，将原始指令重映射到SRAM中的跳转指令
 * - 方式2: 直接替换指令为跳转指令
 * 
 * 本实现采用方式2，因为:
 * - 不需要额外的SRAM空间
 * - 配置更简单直接
 * - 适合Cortex-M3的FPB_REV1版本
 * 
 * @author  FPBInject Project
 * @version 1.0
 */

#include "fpb_inject.h"
#include <string.h>

/*===========================================================================
 * 私有变量
 *===========================================================================*/

/* FPB全局状态 */
static FPB_State_t fpb_state = {0};

/* 
 * 重映射表 - 存放跳转指令
 * 必须放在SRAM中，且地址必须是32字节对齐
 * 每个条目存放一条BL/B指令用于跳转到补丁函数
 */
__attribute__((aligned(32), section(".data")))
static uint32_t fpb_remap_table[FPB_REMAP_TABLE_SIZE * 2];

/*===========================================================================
 * 私有函数
 *===========================================================================*/

/**
 * @brief 生成Thumb-2 BL指令 (长跳转)
 * @param target_addr 目标地址
 * @return 32位BL指令编码
 */
__attribute__((unused))
static uint32_t generate_bl_instruction(uint32_t from_addr, uint32_t target_addr)
{
    /*
     * Thumb-2 BL指令格式:
     * 
     * 第一个半字 (高位): 11110 S imm10
     * 第二个半字 (低位): 11 J1 1 J2 imm11
     * 
     * 偏移计算:
     * offset = SignExtend(S:I1:I2:imm10:imm11:'0', 25)
     * I1 = NOT(J1 XOR S)
     * I2 = NOT(J2 XOR S)
     * 
     * 范围: ±16MB
     */
    
    int32_t offset = (int32_t)(target_addr - from_addr - 4);
    
    /* 提取各字段 */
    uint32_t s = (offset < 0) ? 1 : 0;
    uint32_t imm10 = (offset >> 12) & 0x3FF;
    uint32_t imm11 = (offset >> 1) & 0x7FF;
    
    /* J1, J2 计算 */
    uint32_t i1 = ((offset >> 23) & 1) ^ s ^ 1;
    uint32_t i2 = ((offset >> 22) & 1) ^ s ^ 1;
    uint32_t j1 = i1;
    uint32_t j2 = i2;
    
    /* 构造指令 */
    uint16_t hw1 = 0xF000 | (s << 10) | imm10;
    uint16_t hw2 = 0xD000 | (j1 << 13) | (j2 << 11) | imm11;
    
    /* 返回小端格式 (第一个半字在低16位) */
    return ((uint32_t)hw2 << 16) | hw1;
}

/**
 * @brief 生成Thumb B.W指令 (无条件分支)
 * @param from_addr 源地址
 * @param target_addr 目标地址
 * @return 32位B.W指令编码
 */
static uint32_t generate_b_w_instruction(uint32_t from_addr, uint32_t target_addr)
{
    /*
     * Thumb-2 B.W指令格式:
     * 
     * 第一个半字: 11110 S imm10
     * 第二个半字: 10 J1 0 J2 imm11
     * 
     * 与BL类似，但第二个半字的bit12为0
     */
    
    int32_t offset = (int32_t)(target_addr - from_addr - 4);
    
    uint32_t s = (offset < 0) ? 1 : 0;
    uint32_t imm10 = (offset >> 12) & 0x3FF;
    uint32_t imm11 = (offset >> 1) & 0x7FF;
    
    uint32_t i1 = ((offset >> 23) & 1) ^ s ^ 1;
    uint32_t i2 = ((offset >> 22) & 1) ^ s ^ 1;
    uint32_t j1 = i1;
    uint32_t j2 = i2;
    
    uint16_t hw1 = 0xF000 | (s << 10) | imm10;
    uint16_t hw2 = 0x9000 | (j1 << 13) | (j2 << 11) | imm11;  /* bit12=0 for B.W */
    
    return ((uint32_t)hw2 << 16) | hw1;
}

/**
 * @brief 数据同步屏障
 */
static inline void dsb(void)
{
    __asm volatile ("dsb" ::: "memory");
}

/**
 * @brief 指令同步屏障
 */
static inline void isb(void)
{
    __asm volatile ("isb" ::: "memory");
}

/*===========================================================================
 * 公共函数实现
 *===========================================================================*/

int FPB_Init(void)
{
    /* 清空状态 */
    memset(&fpb_state, 0, sizeof(fpb_state));
    memset(fpb_remap_table, 0, sizeof(fpb_remap_table));
    
    /* 读取FPB配置 */
    uint32_t ctrl = FPB_CTRL;
    
    /* 提取比较器数量 */
    fpb_state.num_code_comp = (ctrl & FPB_CTRL_NUM_CODE_MASK) >> FPB_CTRL_NUM_CODE_SHIFT;
    fpb_state.num_lit_comp = (ctrl & FPB_CTRL_NUM_LIT_MASK) >> FPB_CTRL_NUM_LIT_SHIFT;
    
    /* 验证FPB存在 */
    if (fpb_state.num_code_comp == 0)
    {
        /* FPB不存在或不可用 */
        return -1;
    }
    
    /* 限制为最大支持数量 */
    if (fpb_state.num_code_comp > FPB_MAX_CODE_COMP)
    {
        fpb_state.num_code_comp = FPB_MAX_CODE_COMP;
    }
    
    /* 禁用所有比较器 */
    for (uint8_t i = 0; i < FPB_MAX_COMP; i++)
    {
        FPB_COMP(i) = 0;
    }
    
    /* 设置重映射表地址 (如果需要使用REMAP模式) */
    /* FPB_REMAP = ((uint32_t)fpb_remap_table) & 0x1FFFFFE0; */
    
    /* 使能FPB单元 */
    FPB_CTRL = FPB_CTRL_KEY | FPB_CTRL_ENABLE;
    
    /* 内存屏障 */
    dsb();
    isb();
    
    fpb_state.initialized = true;
    
    return 0;
}

void FPB_DeInit(void)
{
    /* 禁用所有比较器 */
    for (uint8_t i = 0; i < FPB_MAX_COMP; i++)
    {
        FPB_COMP(i) = 0;
    }
    
    /* 禁用FPB单元 */
    FPB_CTRL = FPB_CTRL_KEY;
    
    /* 清空状态 */
    memset(&fpb_state, 0, sizeof(fpb_state));
    
    dsb();
    isb();
}

int FPB_SetPatch(uint8_t comp_id, uint32_t original_addr, uint32_t patch_addr)
{
    /* 参数检查 */
    if (!fpb_state.initialized)
    {
        return -1;
    }
    
    if (comp_id >= fpb_state.num_code_comp)
    {
        return -1;
    }
    
    /* 地址必须在Code区域 (0x00000000 - 0x1FFFFFFF) */
    if (original_addr >= 0x20000000UL)
    {
        return -1;
    }
    
    /* 地址必须2字节对齐 (Thumb指令) */
    original_addr &= ~1UL;  /* 清除Thumb位 */
    patch_addr &= ~1UL;
    
    /* 
     * 方式1: 使用指令替换模式
     * 直接在比较器中设置跳转指令
     * 
     * FPB_REV1 (Cortex-M3) 的工作方式:
     * - 当CPU取指地址匹配COMP[28:2]时
     * - FPB返回REMAP表中对应位置的指令
     * 
     * 方式2: 使用REMAP + 跳转指令
     * 将跳转指令存入REMAP表，FPB返回该指令
     */
    
    /* 计算REMAP表中的位置 */
    uint32_t remap_index = comp_id * 2;
    
    /* 生成跳转指令 (B.W to patch_addr) */
    /* 注意: 跳转指令执行时PC指向原始地址+4 */
    uint32_t jump_instr = generate_b_w_instruction(original_addr, patch_addr);
    
    /* 存入REMAP表 */
    fpb_remap_table[remap_index] = jump_instr;
    fpb_remap_table[remap_index + 1] = 0; /* 保留 */
    
    /* 设置REMAP表地址 */
    FPB_REMAP = ((uint32_t)fpb_remap_table) & 0x1FFFFFE0UL;
    
    /* 配置比较器 */
    /* 
     * COMP寄存器格式:
     * [31:30] REPLACE - 替换模式: 00=使用REMAP
     * [28:2]  COMP    - 比较地址
     * [0]     ENABLE  - 使能位
     */
    uint32_t comp_val = (original_addr & FPB_COMP_ADDR_MASK) | 
                        FPB_REPLACE_REMAP |  /* 使用REMAP模式 */
                        FPB_COMP_ENABLE;
    
    FPB_COMP(comp_id) = comp_val;
    
    /* 更新状态 */
    fpb_state.comp[comp_id].original_addr = original_addr;
    fpb_state.comp[comp_id].patch_addr = patch_addr;
    fpb_state.comp[comp_id].enabled = true;
    
    /* 内存屏障 - 确保FPB配置生效 */
    dsb();
    isb();
    
    return 0;
}

int FPB_ClearPatch(uint8_t comp_id)
{
    if (!fpb_state.initialized)
    {
        return -1;
    }
    
    if (comp_id >= fpb_state.num_code_comp)
    {
        return -1;
    }
    
    /* 禁用比较器 */
    FPB_COMP(comp_id) = 0;
    
    /* 清空REMAP表条目 */
    uint32_t remap_index = comp_id * 2;
    fpb_remap_table[remap_index] = 0;
    fpb_remap_table[remap_index + 1] = 0;
    
    /* 更新状态 */
    fpb_state.comp[comp_id].original_addr = 0;
    fpb_state.comp[comp_id].patch_addr = 0;
    fpb_state.comp[comp_id].enabled = false;
    
    dsb();
    isb();
    
    return 0;
}

int FPB_EnableComp(uint8_t comp_id, bool enable)
{
    if (!fpb_state.initialized || comp_id >= fpb_state.num_code_comp)
    {
        return -1;
    }
    
    uint32_t comp_val = FPB_COMP(comp_id);
    
    if (enable)
    {
        comp_val |= FPB_COMP_ENABLE;
    }
    else
    {
        comp_val &= ~FPB_COMP_ENABLE;
    }
    
    FPB_COMP(comp_id) = comp_val;
    fpb_state.comp[comp_id].enabled = enable;
    
    dsb();
    isb();
    
    return 0;
}

const FPB_State_t* FPB_GetState(void)
{
    return &fpb_state;
}

bool FPB_IsSupported(void)
{
    /* 尝试读取FPB_CTRL */
    uint32_t ctrl = FPB_CTRL;
    uint8_t num_code = (ctrl & FPB_CTRL_NUM_CODE_MASK) >> FPB_CTRL_NUM_CODE_SHIFT;
    
    return (num_code > 0);
}

uint8_t FPB_GetNumCodeComp(void)
{
    return fpb_state.num_code_comp;
}

int FPB_SetInstructionPatch(uint8_t comp_id, uint32_t addr, 
                            uint16_t new_instruction, bool is_upper)
{
    if (!fpb_state.initialized || comp_id >= fpb_state.num_code_comp)
    {
        return -1;
    }
    
    /* 地址必须在Code区域且4字节对齐 */
    addr &= ~3UL;
    
    if (addr >= 0x20000000UL)
    {
        return -1;
    }
    
    /*
     * 使用指令替换模式:
     * - REPLACE = 01: 替换低半字
     * - REPLACE = 10: 替换高半字
     * - 新指令存入REMAP表
     */
    
    uint32_t remap_index = comp_id * 2;
    uint32_t replace_mode;
    
    if (is_upper)
    {
        replace_mode = FPB_REPLACE_UPPER;
        fpb_remap_table[remap_index] = (uint32_t)new_instruction << 16;
    }
    else
    {
        replace_mode = FPB_REPLACE_LOWER;
        fpb_remap_table[remap_index] = new_instruction;
    }
    
    /* 设置REMAP表地址 */
    FPB_REMAP = ((uint32_t)fpb_remap_table) & 0x1FFFFFE0UL;
    
    /* 配置比较器 */
    uint32_t comp_val = (addr & FPB_COMP_ADDR_MASK) | 
                        replace_mode |
                        FPB_COMP_ENABLE;
    
    FPB_COMP(comp_id) = comp_val;
    
    fpb_state.comp[comp_id].original_addr = addr;
    fpb_state.comp[comp_id].patch_addr = new_instruction;
    fpb_state.comp[comp_id].enabled = true;
    
    dsb();
    isb();
    
    return 0;
}

uint8_t FPB_GenerateThumbJump(uint32_t from_addr, uint32_t to_addr, 
                              uint8_t* instruction)
{
    int32_t offset = (int32_t)(to_addr - from_addr - 4);
    
    /* 检查是否可以使用短跳转 B.N (±2KB) */
    if (offset >= -2048 && offset <= 2046)
    {
        /* B.N 指令: 11100 imm11 */
        uint16_t imm11 = (offset >> 1) & 0x7FF;
        uint16_t instr = 0xE000 | imm11;
        
        instruction[0] = instr & 0xFF;
        instruction[1] = (instr >> 8) & 0xFF;
        
        return 2;
    }
    else
    {
        /* B.W 指令 (±16MB) */
        uint32_t instr = generate_b_w_instruction(from_addr, to_addr);
        
        /* 小端存储 */
        instruction[0] = instr & 0xFF;
        instruction[1] = (instr >> 8) & 0xFF;
        instruction[2] = (instr >> 16) & 0xFF;
        instruction[3] = (instr >> 24) & 0xFF;
        
        return 4;
    }
}

void FPB_PrintInfo(void)
{
    /* 此函数可以通过串口打印FPB信息 */
    /* 实现取决于可用的打印接口 */
    
#ifdef SERIAL_1_ENABLE
    /* 需要包含HardwareSerial.h */
#endif
}
