############################################################################
# FPBInject/Makefile
#
# SPDX-License-Identifier: MIT
#
############################################################################

# Resolve the real directory of this Makefile BEFORE any includes
# (MAKEFILE_LIST changes after include)

FPBINJECT_DIR := $(patsubst %/,%,$(dir $(realpath $(lastword $(MAKEFILE_LIST)))))

include $(APPDIR)/Make.defs

# FPBInject built-in application info

PROGNAME  = fl
PRIORITY  = $(CONFIG_FPBINJECT_PRIORITY)
STACKSIZE = $(CONFIG_FPBINJECT_STACKSIZE)
MODULE    = $(CONFIG_FPBINJECT)

# Source files (use notdir — VPATH resolves actual paths)
MAINSRC = fl_port_nuttx.c
CSRCS += $(filter-out fl_port_nuttx.c, $(notdir $(wildcard $(FPBINJECT_DIR)/App/func_loader/*.c)))
CSRCS += $(notdir $(wildcard $(FPBINJECT_DIR)/App/func_loader/argparse/*.c))
CSRCS += $(notdir $(wildcard $(FPBINJECT_DIR)/Source/*.c))

VPATH += :$(FPBINJECT_DIR)/App/func_loader
VPATH += :$(FPBINJECT_DIR)/App/func_loader/argparse
VPATH += :$(FPBINJECT_DIR)/Source

DEPPATH += --dep-path $(FPBINJECT_DIR)/App/func_loader
DEPPATH += --dep-path $(FPBINJECT_DIR)/App/func_loader/argparse
DEPPATH += --dep-path $(FPBINJECT_DIR)/Source

# Definitions
CFLAGS += -DFL_NUTTX_BUF_SIZE=$(CONFIG_FPBINJECT_BUF_SIZE) \
          -DFL_NUTTX_LINE_SIZE=$(CONFIG_FPBINJECT_LINE_SIZE) \
          -DFL_USE_FILE=1 \
          -DFL_FILE_USE_POSIX=1

# FPB feature switches (mapped from Kconfig)
ifdef CONFIG_FPBINJECT_NO_FPB
CFLAGS += -DFL_NO_FPB
endif

ifdef CONFIG_FPBINJECT_NO_TRAMPOLINE
CFLAGS += -DFPB_NO_TRAMPOLINE
endif

ifdef CONFIG_FPBINJECT_NO_DEBUGMON
CFLAGS += -DFPB_NO_DEBUGMON
endif

CFLAGS += ${INCDIR_PREFIX}$(FPBINJECT_DIR)/App/func_loader \
          ${INCDIR_PREFIX}$(FPBINJECT_DIR)/App/func_loader/argparse \
          ${INCDIR_PREFIX}$(FPBINJECT_DIR)/Source

include $(APPDIR)/Application.mk
