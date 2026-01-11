cmake_minimum_required(VERSION 3.16)

# 项目名称
project(FPBInject C CXX ASM)

# 设置输出目录
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

# STM32F103C8T6 型号定义 (Medium Density, 64KB Flash, 20KB RAM)
set(STM32_DEVICE "STM32F10X_MD" CACHE STRING "STM32 Device type")
set(HSE_VALUE "8000000" CACHE STRING "HSE crystal frequency")

# 编译定义
add_compile_definitions(
    ${STM32_DEVICE}
    USE_STDPERIPH_DRIVER
    HSE_VALUE=${HSE_VALUE}
)

# 源文件目录
set(PROJECT_DIR ${CMAKE_SOURCE_DIR}/Project)
set(PLATFORM_DIR ${PROJECT_DIR}/Platform/STM32F10x)
set(ARDUINO_DIR ${PROJECT_DIR}/ArduinoAPI)
set(SOURCE_DIR ${CMAKE_SOURCE_DIR}/Source)

# 链接脚本 (STM32F103C8T6: 64KB Flash, 20KB RAM)
set(LINKER_SCRIPT ${PLATFORM_DIR}/Startup/STM32F103C8_FLASH.ld)

# 收集源文件
# Application (排除 Keil 特有的 rt_sys.cpp)
file(GLOB APP_SOURCES
    ${PROJECT_DIR}/Application/*.c
    ${PROJECT_DIR}/Application/*.cpp
)
list(FILTER APP_SOURCES EXCLUDE REGEX ".*rt_sys\\.cpp$")

# Arduino API
file(GLOB ARDUINO_SOURCES
    ${ARDUINO_DIR}/*.c
    ${ARDUINO_DIR}/*.cpp
)

# Platform Core
file(GLOB PLATFORM_CORE_SOURCES
    ${PLATFORM_DIR}/Core/*.c
    ${PLATFORM_DIR}/Core/*.cpp
)

# CMSIS Device (system_stm32f10x.c)
file(GLOB CMSIS_DEVICE_SOURCES
    ${PLATFORM_DIR}/CMSIS/Device/*.c
)

# StdPeriph Driver (新路径)
file(GLOB STDPERIPH_SOURCES
    ${PLATFORM_DIR}/STM32F10x_StdPeriph_Driver/Src/*.c
)

# Startup 文件 (通用启动文件，兼容所有STM32F10x系列)
set(STARTUP_SOURCE ${PLATFORM_DIR}/Startup/startup_stm32f10x.s)

# FPB 注入源码
file(GLOB FPB_SOURCES
    ${SOURCE_DIR}/*.c
    ${SOURCE_DIR}/*.cpp
)

# 所有源文件
set(ALL_SOURCES
    ${APP_SOURCES}
    ${ARDUINO_SOURCES}
    ${PLATFORM_CORE_SOURCES}
    ${CMSIS_DEVICE_SOURCES}
    ${STDPERIPH_SOURCES}
    ${FPB_SOURCES}
    ${STARTUP_SOURCE}
)

# 包含目录 (新路径)
set(INCLUDE_DIRS
    ${PROJECT_DIR}/Application
    ${ARDUINO_DIR}
    ${ARDUINO_DIR}/avr
    ${PLATFORM_DIR}/Config
    ${PLATFORM_DIR}/Core
    ${PLATFORM_DIR}/CMSIS/Include
    ${PLATFORM_DIR}/CMSIS/Device
    ${PLATFORM_DIR}/STM32F10x_StdPeriph_Driver/Inc
    ${SOURCE_DIR}
)

# 创建可执行文件
add_executable(${PROJECT_NAME} ${ALL_SOURCES})

# 设置输出文件后缀为 .elf
set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".elf")

# 设置包含目录
target_include_directories(${PROJECT_NAME} PRIVATE ${INCLUDE_DIRS})

# 设置链接选项
target_link_options(${PROJECT_NAME} PRIVATE
    -T${LINKER_SCRIPT}
    -Wl,-Map=${CMAKE_BINARY_DIR}/${PROJECT_NAME}.map,--cref
)

# 生成 HEX 和 BIN 文件
add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O ihex ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.elf ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.hex
    COMMAND ${CMAKE_OBJCOPY} -O binary ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.elf ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.bin
    COMMAND ${CMAKE_SIZE} ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.elf
    COMMENT "Generating HEX and BIN files..."
)

# 打印编译信息
message(STATUS "========================================")
message(STATUS "FPBInject - Cortex-M FPB Inject Tool")
message(STATUS "========================================")
message(STATUS "Device: ${STM32_DEVICE}")
message(STATUS "HSE: ${HSE_VALUE} Hz")
message(STATUS "Linker Script: ${LINKER_SCRIPT}")
message(STATUS "Build Type: ${CMAKE_BUILD_TYPE}")
message(STATUS "========================================")
