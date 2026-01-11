# ARM Cortex-M Toolchain File for STM32F103
# For use with arm-none-eabi-gcc

set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

# Toolchain paths
set(TOOLCHAIN_PREFIX arm-none-eabi-)
find_program(CMAKE_C_COMPILER ${TOOLCHAIN_PREFIX}gcc)
find_program(CMAKE_CXX_COMPILER ${TOOLCHAIN_PREFIX}g++)
find_program(CMAKE_ASM_COMPILER ${TOOLCHAIN_PREFIX}gcc)
find_program(CMAKE_OBJCOPY ${TOOLCHAIN_PREFIX}objcopy)
find_program(CMAKE_OBJDUMP ${TOOLCHAIN_PREFIX}objdump)
find_program(CMAKE_SIZE ${TOOLCHAIN_PREFIX}size)
find_program(CMAKE_AR ${TOOLCHAIN_PREFIX}ar)

# CPU/FPU flags for Cortex-M3
set(CPU_FLAGS "-mcpu=cortex-m3 -mthumb")

# Common compile flags
set(COMMON_FLAGS "${CPU_FLAGS} -ffunction-sections -fdata-sections -fno-common -fno-exceptions")
set(COMMON_FLAGS "${COMMON_FLAGS} -Wall -Wextra -Wno-unused-parameter")

# C specific flags
set(CMAKE_C_FLAGS "${COMMON_FLAGS} -std=gnu11" CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS_DEBUG "-Og -g3 -DDEBUG" CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS_RELEASE "-Os -DNDEBUG" CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS_MINSIZEREL "-Os -DNDEBUG" CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS_RELWITHDEBINFO "-Os -g -DNDEBUG" CACHE STRING "" FORCE)

# C++ specific flags
set(CMAKE_CXX_FLAGS "${COMMON_FLAGS} -std=gnu++14 -fno-rtti -fno-threadsafe-statics" CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS_DEBUG "-Og -g3 -DDEBUG" CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS_RELEASE "-Os -DNDEBUG" CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS_MINSIZEREL "-Os -DNDEBUG" CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS_RELWITHDEBINFO "-Os -g -DNDEBUG" CACHE STRING "" FORCE)

# ASM flags
set(CMAKE_ASM_FLAGS "${CPU_FLAGS} -x assembler-with-cpp" CACHE STRING "" FORCE)

# Linker flags
set(CMAKE_EXE_LINKER_FLAGS "${CPU_FLAGS} -specs=nano.specs -specs=nosys.specs -Wl,--gc-sections -lc -lm -lnosys" CACHE STRING "" FORCE)

# Prevent CMake from testing the compilers
set(CMAKE_C_COMPILER_WORKS 1)
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_ASM_COMPILER_WORKS 1)

# Search paths
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

# Try to find the toolchain
if(NOT CMAKE_C_COMPILER)
    message(FATAL_ERROR "arm-none-eabi-gcc not found! Please install the ARM toolchain.")
endif()
