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

# Detect build environment: - NuttX: NUTTX_APPS_DIR variable is defined by NuttX
# CMake system - Bare-metal: standalone build with FPBINJECT_ROOT defined
if(NUTTX_APPS_DIR)
  if(CONFIG_FPBINJECT)
    nuttx_add_application(
      NAME
      fl
      STACKSIZE
      ${CONFIG_FPBINJECT_STACKSIZE}
      PRIORITY
      ${CONFIG_FPBINJECT_PRIORITY}
      MODULE
      ${CONFIG_FPBINJECT}
      SRCS
      App/func_loader/fl_port_nuttx.c
      App/func_loader/fl.c
      App/func_loader/fl_log.c
      App/func_loader/fl_file.c
      App/func_loader/fl_file_posix.c
      App/func_loader/fl_stream.c
      App/func_loader/argparse/argparse.c
      Source/fpb_inject.c
      Source/fpb_trampoline.c
      Source/fpb_debugmon_nuttx.c
      INCLUDE_DIRECTORIES
      ${CMAKE_CURRENT_LIST_DIR}/App/func_loader
      ${CMAKE_CURRENT_LIST_DIR}/App/func_loader/argparse
      ${CMAKE_CURRENT_LIST_DIR}/Source
      DEFINITIONS
      FL_NUTTX_BUF_SIZE=${CONFIG_FPBINJECT_BUF_SIZE}
      FL_NUTTX_LINE_SIZE=${CONFIG_FPBINJECT_LINE_SIZE}
      FL_USE_FILE=1
      FL_FILE_USE_POSIX=1)
  endif()
else()
  cmake_minimum_required(VERSION 3.16)

  # Standalone Bare-metal Build Mode (STM32F103)
  if(NOT DEFINED FPBINJECT_ROOT)
    set(FPBINJECT_ROOT ${CMAKE_CURRENT_LIST_DIR})
  endif()
  include(${FPBINJECT_ROOT}/cmake/stm32f103.cmake)
endif()
