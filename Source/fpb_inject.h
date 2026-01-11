/**
 * @file   fpb_inject.h
 * @brief  Cortex-M3/M4 Flash Patch and Breakpoint (FPB) 单元驱动
 * 
 * FPB是ARM Cortex-M处理器中的调试组件，可以用于:
 * 1. 设置硬件断点
 * 2. 重映射Flash中的指令到SRAM (代码注入)
 * 
 * 本模块实现了运行时代码注入功能，可以在不修改Flash的情况下
 * 替换指定地址的指令，实现热补丁功能。
 * 
 * 硬件特性 (STM32F103 - Cortex-M3):
 * - 6个指令比较器 (FP_COMP0 - FP_COMP5) 可用于代码重映射
 * - 2个字面量比较器 (FP_COMP6 - FP_COMP7) 用于数据重映射
 * - 支持Thumb指令重映射
 * 
 * @author  FPBInject Project
 * @version 1.0
 */

#ifndef __FPB_INJECT_H
#define __FPB_INJECT_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

/*===========================================================================
 * FPB 寄存器定义
 *===========================================================================*/

/* FPB 基地址 (Cortex-M3/M4) */
#define FPB_BASE            0xE0002000UL

/* FPB 控制寄存器 */
#define FPB_CTRL            (*(volatile uint32_t *)(FPB_BASE + 0x000))

/* FPB 重映射寄存器 */
#define FPB_REMAP           (*(volatile uint32_t *)(FPB_BASE + 0x004))

/* FPB 比较器寄存器 (0-7) */
#define FPB_COMP(n)         (*(volatile uint32_t *)(FPB_BASE + 0x008 + ((n) * 4)))

/* FPB 比较器数组 */
#define FPB_COMP0           (*(volatile uint32_t *)(FPB_BASE + 0x008))
#define FPB_COMP1           (*(volatile uint32_t *)(FPB_BASE + 0x00C))
#define FPB_COMP2           (*(volatile uint32_t *)(FPB_BASE + 0x010))
#define FPB_COMP3           (*(volatile uint32_t *)(FPB_BASE + 0x014))
#define FPB_COMP4           (*(volatile uint32_t *)(FPB_BASE + 0x018))
#define FPB_COMP5           (*(volatile uint32_t *)(FPB_BASE + 0x01C))
#define FPB_COMP6           (*(volatile uint32_t *)(FPB_BASE + 0x020))
#define FPB_COMP7           (*(volatile uint32_t *)(FPB_BASE + 0x024))

/*===========================================================================
 * FPB 控制寄存器位定义
 *===========================================================================*/

/* CTRL 寄存器位 */
#define FPB_CTRL_ENABLE     (1UL << 0)   /* FPB 使能位 */
#define FPB_CTRL_KEY        (1UL << 1)   /* 写使能密钥 */

/* CTRL 寄存器中的比较器数量字段 */
#define FPB_CTRL_NUM_CODE_MASK  (0xFUL << 4)   /* 代码比较器数量 */
#define FPB_CTRL_NUM_LIT_MASK   (0xFUL << 8)   /* 字面量比较器数量 */
#define FPB_CTRL_NUM_CODE_SHIFT 4
#define FPB_CTRL_NUM_LIT_SHIFT  8

/*===========================================================================
 * FPB 比较器寄存器位定义
 *===========================================================================*/

/* COMP 寄存器位 */
#define FPB_COMP_ENABLE     (1UL << 0)   /* 比较器使能位 */
#define FPB_COMP_ADDR_MASK  0x1FFFFFFCUL /* 地址掩码 (bit[28:2]) */
#define FPB_COMP_REPLACE_MASK (3UL << 30)/* 替换字段掩码 */

/* 替换模式 */
#define FPB_REPLACE_REMAP   (0UL << 30)  /* 重映射到remap地址 */
#define FPB_REPLACE_LOWER   (1UL << 30)  /* 替换低半字 */
#define FPB_REPLACE_UPPER   (2UL << 30)  /* 替换高半字 */
#define FPB_REPLACE_BOTH    (3UL << 30)  /* 替换整个字 */

/*===========================================================================
 * FPB 配置常量
 *===========================================================================*/

/* 最大代码比较器数量 (STM32F103 Cortex-M3) */
#define FPB_MAX_CODE_COMP   6

/* 最大字面量比较器数量 */
#define FPB_MAX_LIT_COMP    2

/* 总比较器数量 */
#define FPB_MAX_COMP        (FPB_MAX_CODE_COMP + FPB_MAX_LIT_COMP)

/* 重映射表大小 (每个比较器需要一个重映射条目) */
#define FPB_REMAP_TABLE_SIZE    FPB_MAX_CODE_COMP

/*===========================================================================
 * FPB 状态结构
 *===========================================================================*/

/**
 * @brief FPB比较器状态
 */
typedef struct {
    uint32_t original_addr;     /* 原始指令地址 */
    uint32_t patch_addr;        /* 补丁函数地址 */
    bool     enabled;           /* 是否启用 */
} FPB_CompState_t;

/**
 * @brief FPB全局状态
 */
typedef struct {
    bool initialized;                           /* 是否已初始化 */
    uint8_t num_code_comp;                      /* 可用代码比较器数量 */
    uint8_t num_lit_comp;                       /* 可用字面量比较器数量 */
    FPB_CompState_t comp[FPB_MAX_CODE_COMP];   /* 比较器状态 */
} FPB_State_t;

/*===========================================================================
 * FPB API 函数
 *===========================================================================*/

/**
 * @brief  初始化FPB单元
 * @retval 0: 成功, -1: 失败
 * @note   必须在使用其他FPB函数之前调用
 */
int FPB_Init(void);

/**
 * @brief  反初始化FPB单元
 * @note   禁用所有比较器和FPB功能
 */
void FPB_DeInit(void);

/**
 * @brief  设置代码补丁
 * @param  comp_id: 比较器ID (0 ~ FPB_MAX_CODE_COMP-1)
 * @param  original_addr: 原始函数地址 (必须在Code区域: 0x00000000 - 0x1FFFFFFF)
 * @param  patch_addr: 补丁函数地址
 * @retval 0: 成功, -1: 参数错误, -2: 比较器不可用
 * 
 * @note   补丁原理:
 *         当CPU尝试从original_addr取指时，FPB硬件会拦截该请求，
 *         并返回一条跳转指令，跳转到patch_addr执行新代码。
 */
int FPB_SetPatch(uint8_t comp_id, uint32_t original_addr, uint32_t patch_addr);

/**
 * @brief  清除代码补丁
 * @param  comp_id: 比较器ID
 * @retval 0: 成功, -1: 参数错误
 */
int FPB_ClearPatch(uint8_t comp_id);

/**
 * @brief  使能/禁用指定比较器
 * @param  comp_id: 比较器ID
 * @param  enable: true-使能, false-禁用
 * @retval 0: 成功, -1: 参数错误
 */
int FPB_EnableComp(uint8_t comp_id, bool enable);

/**
 * @brief  获取FPB状态信息
 * @return 指向FPB状态结构的指针
 */
const FPB_State_t* FPB_GetState(void);

/**
 * @brief  检查FPB是否支持
 * @retval true: 支持, false: 不支持
 */
bool FPB_IsSupported(void);

/**
 * @brief  获取可用的代码比较器数量
 * @return 可用比较器数量
 */
uint8_t FPB_GetNumCodeComp(void);

/**
 * @brief  打印FPB调试信息
 * @note   通过串口输出当前FPB配置信息
 */
void FPB_PrintInfo(void);

/*===========================================================================
 * 高级FPB功能 - 指令级补丁
 *===========================================================================*/

/**
 * @brief  设置指令级补丁 (替换单条Thumb指令)
 * @param  comp_id: 比较器ID
 * @param  addr: 指令地址 (2字节对齐)
 * @param  new_instruction: 新的Thumb指令 (16位)
 * @param  is_upper: true-替换高半字, false-替换低半字
 * @retval 0: 成功, -1: 失败
 * 
 * @note   此功能使用FPB的指令替换模式，可以直接替换Flash中的单条指令
 *         而不需要跳转到新函数。适用于简单的指令修改场景。
 */
int FPB_SetInstructionPatch(uint8_t comp_id, uint32_t addr, 
                            uint16_t new_instruction, bool is_upper);

/**
 * @brief  生成Thumb跳转指令
 * @param  from_addr: 跳转源地址
 * @param  to_addr: 跳转目标地址
 * @param  instruction: 输出的指令缓冲区 (至少4字节)
 * @return 指令长度 (2或4字节)
 * 
 * @note   根据跳转距离自动选择合适的跳转指令:
 *         - 短距离: B.N (16位)
 *         - 长距离: B.W (32位)
 */
uint8_t FPB_GenerateThumbJump(uint32_t from_addr, uint32_t to_addr, 
                              uint8_t* instruction);

#ifdef __cplusplus
}
#endif

#endif /* __FPB_INJECT_H */
