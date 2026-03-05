# FPBInject Library Integration Module Usage: include this file from your
# project's CMakeLists.txt
#
# Provides: FPBINJECT_SOURCES     - Source files to compile FPBINJECT_INCLUDES -
# Include directories FPBINJECT_DEFINITIONS - Compile definitions
#
# Options (set before including): FL_USE_EXTERNAL_ARGPARSE - Use external
# argparse library FL_MAX_SLOTS             - Max function loader slots
# (default: 6) FL_ALLOC_MODE            - STATIC (default) or LIBC
# FL_FILE_BACKEND          - FATFS, POSIX, LIBC, or NONE (default: NONE)
# FL_FATFS_USE_MALLOC      - Use malloc for FatFS (default: OFF)

# Resolve FPBInject root directory
get_filename_component(FPBINJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)

# Validate
if(NOT EXISTS "${FPBINJECT_ROOT}/Source/fpb_inject.c")
  message(FATAL_ERROR "FPBInject: Source not found at ${FPBINJECT_ROOT}")
endif()

# ==============================================================================
# Core FPB driver sources (always included)
# ==============================================================================
set(FPBINJECT_SOURCES
    ${FPBINJECT_ROOT}/Source/fpb_inject.c
    ${FPBINJECT_ROOT}/Source/fpb_trampoline.c
    ${FPBINJECT_ROOT}/Source/fpb_debugmon.c)

# ==============================================================================
# Function loader sources (auto-detect via glob)
# ==============================================================================
file(GLOB _FL_SOURCES ${FPBINJECT_ROOT}/App/func_loader/*.c)

# Exclude platform-specific ports (user should add the one they need)
list(FILTER _FL_SOURCES EXCLUDE REGEX ".*fl_port_.*")

# Select file backend
if(NOT DEFINED FL_FILE_BACKEND)
  set(FL_FILE_BACKEND "NONE")
endif()

if(FL_FILE_BACKEND STREQUAL "FATFS")
  # Keep fl_file.c and fl_file_fatfs.c
  list(FILTER _FL_SOURCES EXCLUDE REGEX ".*fl_file_libc\\.c$")
  list(FILTER _FL_SOURCES EXCLUDE REGEX ".*fl_file_posix\\.c$")
elseif(FL_FILE_BACKEND STREQUAL "POSIX")
  list(FILTER _FL_SOURCES EXCLUDE REGEX ".*fl_file_fatfs\\.c$")
  list(FILTER _FL_SOURCES EXCLUDE REGEX ".*fl_file_libc\\.c$")
elseif(FL_FILE_BACKEND STREQUAL "LIBC")
  list(FILTER _FL_SOURCES EXCLUDE REGEX ".*fl_file_fatfs\\.c$")
  list(FILTER _FL_SOURCES EXCLUDE REGEX ".*fl_file_posix\\.c$")
else()
  # No file support
  list(FILTER _FL_SOURCES EXCLUDE REGEX ".*fl_file.*")
endif()

list(APPEND FPBINJECT_SOURCES ${_FL_SOURCES})

# Argparse
if(NOT FL_USE_EXTERNAL_ARGPARSE)
  file(GLOB _ARGPARSE_SOURCES ${FPBINJECT_ROOT}/App/func_loader/argparse/*.c)
  list(APPEND FPBINJECT_SOURCES ${_ARGPARSE_SOURCES})
endif()

# ==============================================================================
# Include directories
# ==============================================================================
set(FPBINJECT_INCLUDES
    ${FPBINJECT_ROOT}/Source ${FPBINJECT_ROOT}/App/func_loader
    ${FPBINJECT_ROOT}/App/func_loader/argparse)

# ==============================================================================
# Compile definitions
# ==============================================================================
set(FPBINJECT_DEFINITIONS "")

# Allocation mode
if(FL_ALLOC_MODE STREQUAL "LIBC")
  list(APPEND FPBINJECT_DEFINITIONS FL_ALLOC_LIBC)
else()
  list(APPEND FPBINJECT_DEFINITIONS FL_ALLOC_STATIC)
endif()

# File backend
if(NOT FL_FILE_BACKEND STREQUAL "NONE")
  list(APPEND FPBINJECT_DEFINITIONS FL_USE_FILE=1)
  if(FL_FILE_BACKEND STREQUAL "FATFS")
    list(APPEND FPBINJECT_DEFINITIONS FL_FILE_USE_FATFS=1)
    if(FL_FATFS_USE_MALLOC)
      list(APPEND FPBINJECT_DEFINITIONS FL_FATFS_USE_MALLOC=1)
    endif()
  elseif(FL_FILE_BACKEND STREQUAL "POSIX")
    list(APPEND FPBINJECT_DEFINITIONS FL_FILE_USE_POSIX=1)
  elseif(FL_FILE_BACKEND STREQUAL "LIBC")
    list(APPEND FPBINJECT_DEFINITIONS FL_FILE_USE_LIBC=1)
  endif()
endif()

message(
  STATUS
    "FPBInject: Enabled (${FL_FILE_BACKEND} file backend, ${FL_ALLOC_MODE} alloc)"
)
