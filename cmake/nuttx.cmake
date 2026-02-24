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

# NuttX Build Configuration for FPBInject

if(CONFIG_FPBINJECT)
  # Collect func_loader sources
  file(GLOB FL_SOURCES ${CMAKE_CURRENT_LIST_DIR}/../App/func_loader/*.c
       ${CMAKE_CURRENT_LIST_DIR}/../App/func_loader/argparse/*.c)
  # Exclude main source file
  list(FILTER FL_SOURCES EXCLUDE REGEX ".*fl_port_nuttx\\.c$")

  # Collect FPB sources
  file(GLOB FPB_SOURCES ${CMAKE_CURRENT_LIST_DIR}/../Source/*.c)

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
    ${FL_SOURCES}
    ${FPB_SOURCES}
    INCLUDE_DIRECTORIES
    ${CMAKE_CURRENT_LIST_DIR}/../App/func_loader
    ${CMAKE_CURRENT_LIST_DIR}/../App/func_loader/argparse
    ${CMAKE_CURRENT_LIST_DIR}/../Source
    DEFINITIONS
    FL_NUTTX_BUF_SIZE=${CONFIG_FPBINJECT_BUF_SIZE}
    FL_NUTTX_LINE_SIZE=${CONFIG_FPBINJECT_LINE_SIZE}
    FL_USE_FILE=1
    FL_FILE_USE_POSIX=1)
endif()
