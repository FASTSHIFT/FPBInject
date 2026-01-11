# FPBInject - Cortex-M FPB代码运行时注入工具

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-STM32F103-blue.svg)](https://www.st.com/en/microcontrollers-microprocessors/stm32f103.html)

FPB-Based Embedded Runtime Code Injection Tool & Implementation

## 项目简介

FPBInject是一个基于ARM Cortex-M3/M4 Flash Patch and Breakpoint (FPB) 单元的运行时代码注入工具。它允许在不修改Flash内容的情况下，在运行时动态替换函数实现，实现热补丁功能。

### 主要特性

- ✅ **运行时代码注入** - 无需擦写Flash即可修改程序行为
- ✅ **硬件级实现** - 利用Cortex-M FPB硬件单元，零软件开销
- ✅ **支持多个补丁** - STM32F103支持6个同时活跃的代码补丁
- ✅ **透明重定向** - 对被补丁函数的调用者完全透明
- ✅ **可逆操作** - 可随时禁用补丁恢复原始功能

## 硬件要求

- **MCU**: STM32F103C8T6 (Blue Pill) 或其他Cortex-M3/M4设备
- **调试器**: ST-Link V2
- **其他**: USB线缆, PC13 LED (板载)

## 软件依赖

- ARM GNU Toolchain (`arm-none-eabi-gcc`)
- CMake (>= 3.16)
- Ninja Build
- OpenOCD 或 ST-Link Tools
- Python 3.x (环境搭建脚本)

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/FPBInject.git
cd FPBInject
```

### 2. 一键搭建环境

```bash
python3 Tools/setup_env.py
```

这将:
- 安装必要的工具链
- 创建VS Code配置文件
- 编译项目

### 3. 手动编译

```bash
# 配置CMake
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug \
      -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-gcc.cmake

# 编译
cmake --build build
```

### 4. 烧写固件

使用OpenOCD:
```bash
openocd -f interface/stlink.cfg -f target/stm32f1x.cfg \
        -c "program build/FPBInject.elf verify reset exit"
```

或使用st-flash:
```bash
st-flash --reset write build/FPBInject.bin 0x08000000
```

## FPB工作原理

### 什么是FPB?

Flash Patch and Breakpoint (FPB) 是ARM Cortex-M处理器中的调试组件，原本设计用于:
1. 设置硬件断点
2. 修补Flash中的bug (无需重新编程)

### FPB结构 (STM32F103)

```
┌─────────────────────────────────────────────────────────────┐
│                    FPB Unit (Cortex-M3)                     │
├─────────────────────────────────────────────────────────────┤
│  FP_CTRL (0xE0002000)  - 控制寄存器                         │
│  FP_REMAP (0xE0002004) - 重映射表基地址                     │
│  FP_COMP0-5 (0xE0002008-0x1C) - 代码比较器 (6个)           │
│  FP_COMP6-7 (0xE0002020-0x24) - 字面量比较器 (2个)         │
└─────────────────────────────────────────────────────────────┘
```

### 代码注入流程

```
1. CPU取指请求          2. FPB地址匹配           3. 返回跳转指令
┌─────────┐           ┌─────────────┐          ┌─────────────┐
│  CPU    │──────────>│    FPB      │─────────>│ REMAP Table │
│  fetch  │ addr=0x1000│  Comparator │ match!   │ B.W 0x2000  │
│ 0x1000  │           │  [0x1000]   │          │             │
└─────────┘           └─────────────┘          └─────────────┘
                                                     │
                      ┌──────────────────────────────┘
                      ▼
              4. 执行补丁函数
              ┌─────────────┐
              │ patch_func  │
              │ @ 0x2000    │
              └─────────────┘
```

## API使用

### 基本使用

```c
#include "fpb_inject.h"

// 原始函数
void original_func(void) {
    // 原始实现
}

// 补丁函数
void patched_func(void) {
    // 新实现
}

int main(void) {
    // 初始化FPB
    FPB_Init();
    
    // 设置补丁: 将original_func重定向到patched_func
    FPB_SetPatch(0, (uint32_t)original_func, (uint32_t)patched_func);
    
    // 调用original_func实际会执行patched_func
    original_func();  // 实际执行patched_func!
    
    // 禁用补丁
    FPB_ClearPatch(0);
    
    // 现在调用original_func执行原始代码
    original_func();  // 执行原始代码
    
    return 0;
}
```

### API参考

| 函数 | 描述 |
|------|------|
| `FPB_Init()` | 初始化FPB单元 |
| `FPB_DeInit()` | 反初始化FPB |
| `FPB_SetPatch(id, orig, patch)` | 设置代码补丁 |
| `FPB_ClearPatch(id)` | 清除补丁 |
| `FPB_EnableComp(id, enable)` | 使能/禁用比较器 |
| `FPB_GetState()` | 获取FPB状态 |
| `FPB_IsSupported()` | 检查FPB支持 |

## Demo说明

本项目包含一个LED闪烁Demo，演示FPB注入功能:

1. **初始状态**: LED以500ms周期闪烁
2. **注入后**: LED以100ms周期快速闪烁
3. **循环演示**: 自动在原始/补丁函数间切换

```
时间轴:
0s─────5s─────10s────15s────20s────25s────30s
   正常500ms    ───>  FPB注入, 100ms  ─>  恢复500ms
```

## 项目结构

```
FPBInject/
├── CMakeLists.txt          # CMake构建配置
├── README.md               # 项目说明
├── cmake/
│   └── arm-none-eabi-gcc.cmake  # 工具链文件
├── Project/
│   ├── Application/
│   │   └── main.cpp        # 主程序 (LED闪烁Demo)
│   ├── ArduinoAPI/         # Arduino兼容API
│   └── Platform/
│       └── STM32F10x/      # STM32F10x平台支持
├── Source/
│   ├── fpb_inject.c        # FPB驱动实现
│   ├── fpb_inject.h        # FPB驱动头文件
│   ├── fpb_test.c          # FPB测试模块
│   └── fpb_test.h          # FPB测试头文件
└── Tools/
    └── setup_env.py        # 环境搭建脚本
```

## 注意事项

1. **地址限制**: FPB只能patch Code区域 (0x00000000 - 0x1FFFFFFF)
2. **比较器数量**: STM32F103只有6个代码比较器
3. **Thumb指令**: 仅支持Thumb/Thumb-2指令集
4. **调试模式**: 某些调试器可能使用FPB设置断点，注意冲突

## 应用场景

- **热补丁**: 修复现场部署设备的bug
- **功能切换**: 运行时启用/禁用功能
- **A/B测试**: 在不同实现间切换
- **安全研究**: 动态分析和hook技术
- **调试辅助**: 临时修改程序行为

## License

MIT License - 详见 [LICENSE](LICENSE) 文件

## 参考资料

- [ARM Cortex-M3 Technical Reference Manual](https://developer.arm.com/documentation/ddi0337)
- [ARM Debug Interface Architecture Specification](https://developer.arm.com/documentation/ihi0031)
- [STM32F103 Reference Manual](https://www.st.com/resource/en/reference_manual/rm0008.pdf)
