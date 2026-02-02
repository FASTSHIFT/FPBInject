# FPBInject NuttX Platform Build Test Uses mock NuttX API headers for
# compilation testing with ARM cross-compiler

cmake_minimum_required(VERSION 3.16)

# Must set toolchain before project()
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

# Find ARM toolchain - prefer environment variable, then prebuilts
if(DEFINED ENV{ARM_TOOLCHAIN_PATH})
  set(TOOLCHAIN_PREFIX "$ENV{ARM_TOOLCHAIN_PATH}/arm-none-eabi-")
else()
  set(TOOLCHAIN_PREFIX "arm-none-eabi-")
endif()

set(CMAKE_C_COMPILER ${TOOLCHAIN_PREFIX}gcc)
set(CMAKE_CXX_COMPILER ${TOOLCHAIN_PREFIX}g++)
set(CMAKE_ASM_COMPILER ${TOOLCHAIN_PREFIX}gcc)
set(CMAKE_AR ${TOOLCHAIN_PREFIX}ar)
set(CMAKE_OBJCOPY ${TOOLCHAIN_PREFIX}objcopy)
set(CMAKE_OBJDUMP ${TOOLCHAIN_PREFIX}objdump)
set(CMAKE_SIZE ${TOOLCHAIN_PREFIX}size)

# Disable compiler checks for cross-compilation
set(CMAKE_C_COMPILER_WORKS 1)
set(CMAKE_CXX_COMPILER_WORKS 1)

project(FPBInject_NuttX_Test C ASM)

set(CMAKE_C_STANDARD 11)

# ARM Cortex-M4 flags
set(CPU_FLAGS "-mcpu=cortex-m4 -mthumb -mfloat-abi=soft")
set(CMAKE_C_FLAGS
    "${CMAKE_C_FLAGS} ${CPU_FLAGS} -ffunction-sections -fdata-sections")
set(CMAKE_ASM_FLAGS "${CMAKE_ASM_FLAGS} ${CPU_FLAGS}")

# Define NuttX platform
add_definitions(-D__NUTTX__)

# Define mock mode to disable ARM-specific inline assembly
add_definitions(-DFPB_MOCK_BUILD)

# Mock NuttX headers path
set(NUTTX_MOCK_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

# Include directories
include_directories(
  ${NUTTX_MOCK_DIR}
  ${CMAKE_CURRENT_SOURCE_DIR}/../../Source
  ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader
  ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/argparse
  ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/umm_malloc/src)

# Source files for NuttX build test
set(FPB_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/../../Source/fpb_inject.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../Source/fpb_debugmon.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../Source/fpb_debugmon_nuttx.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../Source/fpb_trampoline.c)

set(FL_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/func_loader.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/func_loader_stream.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/func_loader_port_nuttx.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/argparse/argparse.c)

# UMM malloc sources
set(UMM_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/umm_malloc/src/umm_malloc.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/umm_malloc/src/umm_info.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/umm_malloc/src/umm_integrity.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/umm_malloc/src/umm_poison.c
)

# Options (mirrors main CMakeLists.txt)
option(FPB_NO_TRAMPOLINE "Disable trampoline" OFF)
option(FPB_TRAMPOLINE_NO_ASM "Use C trampoline instead of ASM" ON) # Use C for
                                                                   # host
option(FPB_NO_DEBUGMON "Disable DebugMonitor" OFF)
set(FL_ALLOC_MODE
    "STATIC"
    CACHE STRING "Allocation mode: STATIC, LIBC, UMM")
set(FL_NUTTX_BUF_SIZE
    "1024"
    CACHE STRING "NuttX buffer size (>0=static, 0=dynamic)")

# File transfer options
option(FL_USE_FILE "Enable file transfer feature" OFF)
set(FL_FILE_BACKEND
    "POSIX"
    CACHE STRING "File backend: POSIX, LIBC")

# Configure definitions
if(FPB_NO_TRAMPOLINE)
  add_definitions(-DFPB_NO_TRAMPOLINE)
endif()

if(FPB_TRAMPOLINE_NO_ASM)
  add_definitions(-DFPB_TRAMPOLINE_NO_ASM)
endif()

if(FPB_NO_DEBUGMON)
  add_definitions(-DFPB_NO_DEBUGMON)
endif()

# Allocation mode
if(FL_ALLOC_MODE STREQUAL "STATIC")
  add_definitions(-DFL_ALLOC_MODE=0)
elseif(FL_ALLOC_MODE STREQUAL "LIBC")
  add_definitions(-DFL_ALLOC_MODE=1)
elseif(FL_ALLOC_MODE STREQUAL "UMM")
  add_definitions(-DFL_ALLOC_MODE=2)
  list(APPEND FL_SOURCES ${UMM_SOURCES})
endif()

# NuttX buffer size
add_definitions(-DFL_NUTTX_BUF_SIZE=${FL_NUTTX_BUF_SIZE})

# File transfer feature
if(FL_USE_FILE)
  add_definitions(-DFL_USE_FILE)
  if(FL_FILE_BACKEND STREQUAL "POSIX")
    add_definitions(-DFL_FILE_USE_POSIX)
    list(APPEND FL_SOURCES
         ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/func_loader_file.c
         ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/func_loader_file_posix.c)
  elseif(FL_FILE_BACKEND STREQUAL "LIBC")
    add_definitions(-DFL_FILE_USE_LIBC)
    list(APPEND FL_SOURCES
         ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/func_loader_file.c
         ${CMAKE_CURRENT_SOURCE_DIR}/../../App/func_loader/func_loader_file_libc.c)
  endif()
endif()

# Create static library (just to verify compilation)
add_library(fpbinject_nuttx STATIC ${FPB_SOURCES} ${FL_SOURCES})

# Suppress some warnings for mock code
target_compile_options(
  fpbinject_nuttx
  PRIVATE -Wall -Wextra -Wno-unused-parameter -Wno-unused-function
          -Wno-int-to-pointer-cast -Wno-pointer-to-int-cast)

message(STATUS "FPBInject NuttX Build Test")
message(STATUS "  FPB_NO_TRAMPOLINE: ${FPB_NO_TRAMPOLINE}")
message(STATUS "  FPB_TRAMPOLINE_NO_ASM: ${FPB_TRAMPOLINE_NO_ASM}")
message(STATUS "  FPB_NO_DEBUGMON: ${FPB_NO_DEBUGMON}")
message(STATUS "  FL_ALLOC_MODE: ${FL_ALLOC_MODE}")
message(STATUS "  FL_NUTTX_BUF_SIZE: ${FL_NUTTX_BUF_SIZE}")
message(STATUS "  FL_USE_FILE: ${FL_USE_FILE}")
message(STATUS "  FL_FILE_BACKEND: ${FL_FILE_BACKEND}")
