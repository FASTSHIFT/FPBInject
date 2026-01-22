# MIT License
#
# Copyright (c) 2026 VIFEX
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

cmake_minimum_required(VERSION 3.16)

# Enable standard CMake compile_commands.json generation (must be before
# project())
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Project name
project(FPBInject C CXX ASM)

# Output directory
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

# STM32F103C8T6 device definition (Medium Density, 64KB Flash, 20KB RAM)
set(STM32_DEVICE
    "STM32F10X_MD"
    CACHE STRING "STM32 Device type")
set(HSE_VALUE
    "8000000"
    CACHE STRING "HSE crystal frequency")

# Application selection: 1 = APP_BLINK (LED blink demo) 2 = APP_TEST (FPB test)
# 3 = APP_FUNC_LOADER (Function loader)
set(APP_SELECT
    "1"
    CACHE STRING "Application to build (1=blink, 2=test, 3=func_loader)")

# FPB Trampoline options
option(FPB_NO_TRAMPOLINE
       "Disable trampoline (for cores that can REMAP to RAM directly)" OFF)
option(FPB_TRAMPOLINE_NO_ASM
       "Use C instead of assembly for trampoline (no argument preservation)"
       OFF)

# FPB DebugMonitor option (for ARMv8-M where REMAP is removed)
option(FPB_NO_DEBUGMON "Disable DebugMonitor-based redirection" OFF)

# Function loader allocation mode: STATIC = Static buffer allocation (default)
# LIBC   = Use standard libc malloc/free UMM    = Use umm_malloc (embedded
# allocator)
set(FL_ALLOC_MODE
    "STATIC"
    CACHE STRING "Function loader memory allocation mode (STATIC/LIBC/UMM)")
set_property(CACHE FL_ALLOC_MODE PROPERTY STRINGS "STATIC" "LIBC" "UMM")

# Compile definitions
add_compile_definitions(
  ${STM32_DEVICE} USE_STDPERIPH_DRIVER HSE_VALUE=${HSE_VALUE}
  APP_SELECT=${APP_SELECT} ARDUINO=111)

# Add FPB trampoline options to compile definitions
if(FPB_NO_TRAMPOLINE)
  add_compile_definitions(FPB_NO_TRAMPOLINE)
endif()

if(FPB_TRAMPOLINE_NO_ASM)
  add_compile_definitions(FPB_TRAMPOLINE_NO_ASM)
endif()

# Add DebugMonitor option to compile definitions
if(FPB_NO_DEBUGMON)
  add_compile_definitions(FPB_NO_DEBUGMON)
endif()

# Add allocation mode definition
if(FL_ALLOC_MODE STREQUAL "LIBC")
  add_compile_definitions(FL_ALLOC_LIBC)
elseif(FL_ALLOC_MODE STREQUAL "UMM")
  add_compile_definitions(FL_ALLOC_UMM)
else()
  add_compile_definitions(FL_ALLOC_STATIC)
endif()

# FPBInject root directory (set by parent CMakeLists.txt, fallback for
# standalone use)
if(NOT DEFINED FPBINJECT_ROOT)
  set(FPBINJECT_ROOT ${CMAKE_CURRENT_LIST_DIR}/..)
  get_filename_component(FPBINJECT_ROOT "${FPBINJECT_ROOT}" ABSOLUTE)
endif()

# Source directories
set(PROJECT_DIR ${FPBINJECT_ROOT}/Project)
set(PLATFORM_DIR ${PROJECT_DIR}/Platform/STM32F10x)
set(ARDUINO_DIR ${PROJECT_DIR}/ArduinoAPI)
set(SOURCE_DIR ${FPBINJECT_ROOT}/Source)
set(APP_DIR ${FPBINJECT_ROOT}/App)

# Linker script (STM32F103C8T6: 64KB Flash, 20KB RAM)
set(LINKER_SCRIPT ${PLATFORM_DIR}/Startup/STM32F103C8_FLASH.ld)

# Collect source files Application (exclude Keil-specific rt_sys.cpp)
file(GLOB APP_MAIN_SOURCES ${PROJECT_DIR}/Application/*.c
     ${PROJECT_DIR}/Application/*.cpp)
list(FILTER APP_MAIN_SOURCES EXCLUDE REGEX ".*rt_sys\\.cpp$")

# App modules
file(GLOB APP_BLINK_SOURCES ${APP_DIR}/blink/*.c ${APP_DIR}/blink/*.cpp)

file(GLOB APP_TEST_SOURCES ${APP_DIR}/test/*.c ${APP_DIR}/test/*.cpp)

file(GLOB APP_FUNC_LOADER_SOURCES ${APP_DIR}/func_loader/*.c
     ${APP_DIR}/func_loader/*.cpp ${APP_DIR}/func_loader/argparse/*.c)

# Add UMM_MALLOC sources only when needed
if(FL_ALLOC_MODE STREQUAL "UMM")
  list(APPEND APP_FUNC_LOADER_SOURCES
       ${APP_DIR}/func_loader/umm_malloc/src/umm_malloc.c
       ${APP_DIR}/func_loader/umm_malloc/src/umm_info.c)
endif()

# Arduino API
file(GLOB ARDUINO_SOURCES ${ARDUINO_DIR}/*.c ${ARDUINO_DIR}/*.cpp)

# Platform Core
file(GLOB PLATFORM_CORE_SOURCES ${PLATFORM_DIR}/Core/*.c
     ${PLATFORM_DIR}/Core/*.cpp)

# CMSIS Device (system_stm32f10x.c)
file(GLOB CMSIS_DEVICE_SOURCES ${PLATFORM_DIR}/CMSIS/Device/*.c)

# StdPeriph Driver
file(GLOB STDPERIPH_SOURCES ${PLATFORM_DIR}/STM32F10x_StdPeriph_Driver/Src/*.c)

# Startup file (generic, compatible with all STM32F10x series)
set(STARTUP_SOURCE ${PLATFORM_DIR}/Startup/startup_stm32f10x.s)

# FPB injection source
file(GLOB FPB_SOURCES ${SOURCE_DIR}/*.c ${SOURCE_DIR}/*.cpp)

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
    ${STARTUP_SOURCE})

# Include directories
set(INCLUDE_DIRS
    ${PROJECT_DIR}/Application
    ${APP_DIR}/blink
    ${APP_DIR}/test
    ${APP_DIR}/func_loader
    ${APP_DIR}/func_loader/argparse
    ${APP_DIR}/func_loader/umm_malloc/src
    ${ARDUINO_DIR}
    ${ARDUINO_DIR}/avr
    ${PLATFORM_DIR}/Config
    ${PLATFORM_DIR}/Core
    ${PLATFORM_DIR}/CMSIS/Include
    ${PLATFORM_DIR}/CMSIS/Device
    ${PLATFORM_DIR}/STM32F10x_StdPeriph_Driver/Inc
    ${SOURCE_DIR})

# Create executable
add_executable(${PROJECT_NAME} ${ALL_SOURCES})

# Set output file suffix to .elf
set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".elf")

# Set include directories
target_include_directories(${PROJECT_NAME} PRIVATE ${INCLUDE_DIRS})

# Set link options
target_link_options(${PROJECT_NAME} PRIVATE -T${LINKER_SCRIPT}
                    -Wl,-Map=${CMAKE_BINARY_DIR}/${PROJECT_NAME}.map,--cref)

# Generate HEX and BIN files
add_custom_command(
  TARGET ${PROJECT_NAME}
  POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O ihex ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.elf
          ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.hex
  COMMAND ${CMAKE_OBJCOPY} -O binary ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.elf
          ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.bin
  COMMAND ${CMAKE_SIZE} ${CMAKE_BINARY_DIR}/${PROJECT_NAME}.elf
  COMMENT "Generating HEX and BIN files...")

# Print build info
message(STATUS "========================================")
message(STATUS "FPBInject - Cortex-M FPB Inject Tool")
message(STATUS "========================================")
message(STATUS "Device: ${STM32_DEVICE}")
message(STATUS "HSE: ${HSE_VALUE} Hz")
message(STATUS "App Select: ${APP_SELECT}")
message(STATUS "FPB_NO_TRAMPOLINE: ${FPB_NO_TRAMPOLINE}")
message(STATUS "FPB_TRAMPOLINE_NO_ASM: ${FPB_TRAMPOLINE_NO_ASM}")
message(STATUS "FPB_NO_DEBUGMON: ${FPB_NO_DEBUGMON}")
message(STATUS "FL_ALLOC_MODE: ${FL_ALLOC_MODE}")
message(STATUS "Linker Script: ${LINKER_SCRIPT}")
message(STATUS "Build Type: ${CMAKE_BUILD_TYPE}")
message(STATUS "========================================")

# =============================================================================
# Generate inject compile configuration for fpb_loader.py
# =============================================================================

# Convert include dirs to JSON array
set(INJECT_INCLUDES "")
foreach(dir ${INCLUDE_DIRS})
  if(INJECT_INCLUDES)
    set(INJECT_INCLUDES "${INJECT_INCLUDES},\n    \"${dir}\"")
  else()
    set(INJECT_INCLUDES "\"${dir}\"")
  endif()
endforeach()

# Generate our custom inject_config.json with additional info (objcopy,
# main_elf, etc.) The standard compile_commands.json is generated automatically
# by CMake
file(
  WRITE ${CMAKE_BINARY_DIR}/inject_config.json
  "{
  \"compiler\": \"${CMAKE_C_COMPILER}\",
  \"objcopy\": \"${CMAKE_OBJCOPY}\",
  \"cpu\": \"cortex-m3\",
  \"fpu\": \"\",
  \"includes\": [
    ${INJECT_INCLUDES}
  ],
  \"defines\": [
    \"${STM32_DEVICE}\",
    \"USE_STDPERIPH_DRIVER\",
    \"HSE_VALUE=${HSE_VALUE}\"
  ],
  \"cflags\": [\"-mcpu=cortex-m3\", \"-mthumb\", \"-Os\", \"-ffunction-sections\", \"-fdata-sections\", \"-fno-exceptions\"],
  \"ldflags\": [\"-nostartfiles\", \"-nostdlib\", \"-Wl,--gc-sections\"],
  \"main_elf\": \"${CMAKE_BINARY_DIR}/${PROJECT_NAME}.elf\"
}
")

message(STATUS "Generated: ${CMAKE_BINARY_DIR}/inject_config.json")
message(STATUS "CMake will generate: ${CMAKE_BINARY_DIR}/compile_commands.json")
