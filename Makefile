############################################################################
# FPBInject/Makefile
#
# SPDX-License-Identifier: MIT
#
############################################################################

include $(APPDIR)/Make.defs

# FPBInject built-in application info

PROGNAME  = fl
PRIORITY  = $(CONFIG_FPBINJECT_PRIORITY)
STACKSIZE = $(CONFIG_FPBINJECT_STACKSIZE)
MODULE    = $(CONFIG_FPBINJECT)

# Source files
MAINSRC = App/func_loader/fl_port_nuttx.c
CSRCS += $(filter-out ${MAINSRC}, $(wildcard App/func_loader/*.c))
CSRCS += $(wildcard App/func_loader/argparse/*.c)
CSRCS += $(wildcard Source/*.c)

# Definitions
CFLAGS += -DFL_NUTTX_BUF_SIZE=$(CONFIG_FPBINJECT_BUF_SIZE) \
          -DFL_NUTTX_LINE_SIZE=$(CONFIG_FPBINJECT_LINE_SIZE) \
          -DFL_USE_FILE=1 \
          -DFL_FILE_USE_POSIX=1

CFLAGS += ${INCDIR_PREFIX}$(APPDIR)/examples/FPBInject/App/func_loader \
          ${INCDIR_PREFIX}$(APPDIR)/examples/FPBInject/Source

include $(APPDIR)/Application.mk
