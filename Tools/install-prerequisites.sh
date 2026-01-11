#!/bin/sh
# FPBInject - 安装编译依赖
# 适用于 Ubuntu/Debian 系统

set -e

SCRIPT_PATH=$(readlink -f "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")

echo "========================================"
echo "  FPBInject - 安装编译环境"
echo "========================================"

sudo apt update
cat "$SCRIPT_DIR/prerequisites-apt.txt" | xargs sudo apt install -y

echo ""
echo "========================================"
echo "  安装完成!"
echo "========================================"
echo ""
echo "编译命令:"
echo "  cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug \\"
echo "        -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-gcc.cmake"
echo "  cmake --build build"
echo ""
echo "烧写命令:"
echo "  openocd -f interface/stlink.cfg -f target/stm32f1x.cfg \\"
echo "          -c \"program build/FPBInject.elf verify reset exit\""
