# ARM Cortex-M3 GCC Toolchain File
# For STM32F103 (Cortex-M3)

set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

# 查找工具链
find_program(ARM_CC arm-none-eabi-gcc)
find_program(ARM_CXX arm-none-eabi-g++)
find_program(ARM_OBJCOPY arm-none-eabi-objcopy)
find_program(ARM_OBJDUMP arm-none-eabi-objdump)
find_program(ARM_SIZE arm-none-eabi-size)

if(NOT ARM_CC)
    message(FATAL_ERROR "
=======================================================
  arm-none-eabi-gcc not found!
  
  Please install ARM toolchain:
  
  Ubuntu/Debian:
    sudo apt-get install gcc-arm-none-eabi
    
  Arch Linux:
    sudo pacman -S arm-none-eabi-gcc
    
  macOS:
    brew install arm-none-eabi-gcc
    
  Or run: python3 Tools/setup_env.py --install
=======================================================")
endif()

set(CMAKE_C_COMPILER ${ARM_CC})
set(CMAKE_CXX_COMPILER ${ARM_CXX})
set(CMAKE_ASM_COMPILER ${ARM_CC})
set(CMAKE_OBJCOPY ${ARM_OBJCOPY})
set(CMAKE_OBJDUMP ${ARM_OBJDUMP})
set(CMAKE_SIZE ${ARM_SIZE})

# 设置编译器标志
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

# CPU 和 FPU 设置 (Cortex-M3 没有FPU)
set(CPU_FLAGS "-mcpu=cortex-m3 -mthumb")

# 公共编译标志
set(COMMON_FLAGS "${CPU_FLAGS}")
set(COMMON_FLAGS "${COMMON_FLAGS} -ffunction-sections -fdata-sections")
set(COMMON_FLAGS "${COMMON_FLAGS} -fno-common -fmessage-length=0")
set(COMMON_FLAGS "${COMMON_FLAGS} -Wall -Wextra")

# C 编译标志
set(CMAKE_C_FLAGS "${COMMON_FLAGS} -std=c11" CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS_DEBUG "-O0 -g3 -DDEBUG" CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS_RELEASE "-O2 -DNDEBUG" CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS_MINSIZEREL "-Os -DNDEBUG" CACHE STRING "" FORCE)

# C++ 编译标志
set(CMAKE_CXX_FLAGS "${COMMON_FLAGS} -std=c++17 -fno-rtti -fno-exceptions" CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS_DEBUG "-O0 -g3 -DDEBUG" CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS_RELEASE "-O2 -DNDEBUG" CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS_MINSIZEREL "-Os -DNDEBUG" CACHE STRING "" FORCE)

# 汇编编译标志
set(CMAKE_ASM_FLAGS "${COMMON_FLAGS} -x assembler-with-cpp" CACHE STRING "" FORCE)

# 链接标志
set(CMAKE_EXE_LINKER_FLAGS "${CPU_FLAGS} -specs=nano.specs -specs=nosys.specs" CACHE STRING "" FORCE)
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -Wl,--gc-sections -Wl,--print-memory-usage")

# 搜索路径设置
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
