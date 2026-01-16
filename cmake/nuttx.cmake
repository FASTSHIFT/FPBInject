# ##############################################################################
# apps/FPBInject/cmake/nuttx.cmake
#
# MIT License
# Copyright (c) 2026 VIFEX
#
# NuttX platform CMake configuration for FPBInject
#
# ##############################################################################

if(CONFIG_FPBINJECT)

  # Source files
  set(SRCS
    App/func_loader/func_loader_port_nuttx.c
    App/func_loader/func_loader.c
    App/func_loader/func_loader_stream.c
    App/func_loader/argparse/argparse.c
    Source/fpb_inject.c
    Source/fpb_trampoline.c
    Source/fpb_debugmon.c
  )

  # Include directories
  set(INCDIR
    ${FPBINJECT_ROOT}/App/func_loader
    ${FPBINJECT_ROOT}/App/func_loader/argparse
    ${FPBINJECT_ROOT}/Source
  )

  nuttx_add_application(
    NAME ${CONFIG_FPBINJECT_PROGNAME}
    STACKSIZE ${CONFIG_FPBINJECT_STACKSIZE}
    PRIORITY ${CONFIG_FPBINJECT_PRIORITY}
    MODULE ${CONFIG_FPBINJECT}
    SRCS ${SRCS}
    INCLUDE_DIRECTORIES ${INCDIR}
    DEFINITIONS
      __NUTTX__
      FL_NUTTX_BUF_SIZE=${CONFIG_FPBINJECT_BUF_SIZE}
      FL_NUTTX_LINE_SIZE=${CONFIG_FPBINJECT_LINE_SIZE}
  )

endif()
