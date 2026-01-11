cmake_minimum_required(VERSION 3.16)

# Project name
project(FPBInject C CXX ASM)

# Output directory
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

# STM32F103C8T6 device definition (Medium Density, 64KB Flash, 20KB RAM)
set(STM32_DEVICE "STM32F10X_MD" CACHE STRING "STM32 Device type")
set(HSE_VALUE "8000000" CACHE STRING "HSE crystal frequency")

# Application selection:
# 1 = APP_BLINK (LED blink demo)
# 2 = APP_TEST (FPB test)
# 3 = APP_FUNC_LOADER (Function loader)
set(APP_SELECT "1" CACHE STRING "Application to build (1=blink, 2=test, 3=func_loader)")

# Compile definitions
add_compile_definitions(
    ${STM32_DEVICE}
    USE_STDPERIPH_DRIVER
    HSE_VALUE=${HSE_VALUE}
    APP_SELECT=${APP_SELECT}
)

# Source directories
set(PROJECT_DIR ${CMAKE_SOURCE_DIR}/Project)
set(PLATFORM_DIR ${PROJECT_DIR}/Platform/STM32F10x)
set(ARDUINO_DIR ${PROJECT_DIR}/ArduinoAPI)
set(SOURCE_DIR ${CMAKE_SOURCE_DIR}/Source)
set(APP_DIR ${CMAKE_SOURCE_DIR}/App)

# Linker script (STM32F103C8T6: 64KB Flash, 20KB RAM)
set(LINKER_SCRIPT ${PLATFORM_DIR}/Startup/STM32F103C8_FLASH.ld)

# Collect source files
# Application (exclude Keil-specific rt_sys.cpp)
file(GLOB APP_MAIN_SOURCES
    ${PROJECT_DIR}/Application/*.c
    ${PROJECT_DIR}/Application/*.cpp
)
list(FILTER APP_MAIN_SOURCES EXCLUDE REGEX ".*rt_sys\\.cpp$")

# App modules
file(GLOB APP_BLINK_SOURCES
    ${APP_DIR}/blink/*.c
    ${APP_DIR}/blink/*.cpp
)

file(GLOB APP_TEST_SOURCES
    ${APP_DIR}/test/*.c
    ${APP_DIR}/test/*.cpp
)

file(GLOB APP_FUNC_LOADER_SOURCES
    ${APP_DIR}/func_loader/*.c
    ${APP_DIR}/func_loader/*.cpp
    ${APP_DIR}/func_loader/argparse/*.c
)

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

# StdPeriph Driver
file(GLOB STDPERIPH_SOURCES
    ${PLATFORM_DIR}/STM32F10x_StdPeriph_Driver/Src/*.c
)

# Startup file (generic, compatible with all STM32F10x series)
set(STARTUP_SOURCE ${PLATFORM_DIR}/Startup/startup_stm32f10x.s)

# FPB injection source
file(GLOB FPB_SOURCES
    ${SOURCE_DIR}/*.c
    ${SOURCE_DIR}/*.cpp
)

# All source files
set(ALL_SOURCES
    ${APP_MAIN_SOURCES}
    ${APP_BLINK_SOURCES}
    ${APP_TEST_SOURCES}
    ${APP_FUNC_LOADER_SOURCES}
    ${ARDUINO_SOURCES}
    ${PLATFORM_CORE_SOURCES}
    ${CMSIS_DEVICE_SOURCES}
    ${STDPERIPH_SOURCES}
    ${FPB_SOURCES}
    ${STARTUP_SOURCE}
)

# Include directories
set(INCLUDE_DIRS
    ${PROJECT_DIR}/Application
    ${APP_DIR}/blink
    ${APP_DIR}/test
    ${APP_DIR}/func_loader
    ${APP_DIR}/func_loader/argparse
    ${ARDUINO_DIR}
    ${ARDUINO_DIR}/avr
    ${PLATFORM_DIR}/Config
    ${PLATFORM_DIR}/Core
    ${PLATFORM_DIR}/CMSIS/Include
    ${PLATFORM_DIR}/CMSIS/Device
    ${PLATFORM_DIR}/STM32F10x_StdPeriph_Driver/Inc
    ${SOURCE_DIR}
)

# Create executable
add_executable(${PROJECT_NAME} ${ALL_SOURCES})

# Set output file suffix to .elf
set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".elf")

# Set include directories
target_include_directories(${PROJECT_NAME} PRIVATE ${INCLUDE_DIRS})

# Set link options
target_link_options(${PROJECT_NAME} PRIVATE
    -T${LINKER_SCRIPT}
    -Wl,-Map=${CMAKE_BINARY_DIR}/${PROJECT_NAME}.map,--cref
)

# Generate HEX and BIN files
add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O ihex ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.elf ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.hex
    COMMAND ${CMAKE_OBJCOPY} -O binary ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.elf ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.bin
    COMMAND ${CMAKE_SIZE} ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.elf
    COMMENT "Generating HEX and BIN files..."
)

# Print build info
message(STATUS "========================================")
message(STATUS "FPBInject - Cortex-M FPB Inject Tool")
message(STATUS "========================================")
message(STATUS "Device: ${STM32_DEVICE}")
message(STATUS "HSE: ${HSE_VALUE} Hz")
message(STATUS "App Select: ${APP_SELECT}")
message(STATUS "Linker Script: ${LINKER_SCRIPT}")
message(STATUS "Build Type: ${CMAKE_BUILD_TYPE}")
message(STATUS "========================================")

