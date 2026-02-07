# MIT License Copyright (c) 2026 VIFEX
#
# CMakeLists.txt for FPBInject Firmware Unit Tests Host-based mock testing with
# gcov/lcov coverage support
#
# This test framework compiles the REAL source code (func_loader.c,
# fpb_inject.c, etc.) with mock hardware implementations, allowing coverage
# measurement of actual production code.

cmake_minimum_required(VERSION 3.10)
project(fpbinject_tests C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Compiler options for coverage
option(COVERAGE "Enable coverage reporting" ON)

if(COVERAGE)
  set(CMAKE_C_FLAGS
      "${CMAKE_C_FLAGS} -g -O0 --coverage -fprofile-arcs -ftest-coverage")
  set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} --coverage")
endif()

# Warning flags - treat warnings as errors
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -Werror")

# Define host-based testing (no real hardware)
add_definitions(-DHOST_TESTING=1)
add_definitions(-DFL_USE_FILE=1)
add_definitions(-DFL_FILE_USE_LIBC=1)

# Disable trampoline and debugmon for host testing (require ARM assembly)
add_definitions(-DFPB_NO_TRAMPOLINE=1)
add_definitions(-DFPB_NO_DEBUGMON=1)

# Project directories
set(SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../Source)
set(APP_DIR ${CMAKE_CURRENT_SOURCE_DIR}/..)
set(FUNC_LOADER_DIR ${APP_DIR}/func_loader)

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR} ${SRC_DIR} ${FUNC_LOADER_DIR}
                    ${FUNC_LOADER_DIR}/argparse)

# ============================================================================
# Source Under Test (SUT) - Real production code
# ============================================================================
set(SUT_SOURCES
    # FPB core
    ${SRC_DIR}/fpb_inject.c
    # Function loader core
    ${FUNC_LOADER_DIR}/func_loader.c
    ${FUNC_LOADER_DIR}/func_loader_stream.c
    ${FUNC_LOADER_DIR}/func_loader_log.c
    ${FUNC_LOADER_DIR}/func_allocator.c
    # File transfer (libc backend for host)
    ${FUNC_LOADER_DIR}/func_loader_file.c
    ${FUNC_LOADER_DIR}/func_loader_file_libc.c
    # Argparse library
    ${FUNC_LOADER_DIR}/argparse/argparse.c)

# ============================================================================
# Mock/Test Framework Sources
# ============================================================================
set(MOCK_SOURCES fpb_mock_regs.c mock_hardware.c)

set(TEST_FRAMEWORK_SOURCES test_framework.c)

# ============================================================================
# Test Sources
# ============================================================================
set(TEST_SOURCES
    test_main.c test_func_allocator.c test_func_loader.c
    test_func_loader_stream.c test_func_loader_file.c test_fpb_inject.c)

# Create test executable
add_executable(test_runner ${SUT_SOURCES} ${MOCK_SOURCES}
                           ${TEST_FRAMEWORK_SOURCES} ${TEST_SOURCES})

# Link math library if needed
target_link_libraries(test_runner m)

# Custom target for running tests
add_custom_target(
  run_tests
  COMMAND ./test_runner
  DEPENDS test_runner
  WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
  COMMENT "Running unit tests...")

# Custom target for coverage report
if(COVERAGE)
  find_program(LCOV lcov)
  find_program(GENHTML genhtml)

  if(LCOV AND GENHTML)
    add_custom_target(
      coverage
      COMMAND ${CMAKE_COMMAND} -E make_directory coverage
      COMMAND ${LCOV} --capture --directory . --output-file
              coverage/coverage.info --ignore-errors mismatch
      COMMAND
        ${LCOV} --remove coverage/coverage.info '/usr/*' '*/test_*' '*/mock_*'
        '*/fpb_mock_*' '*/argparse/*' --output-file coverage/coverage.info
        --ignore-errors mismatch
      COMMAND ${GENHTML} coverage/coverage.info --output-directory coverage/html
      COMMAND ${CMAKE_COMMAND} -E echo
              "Coverage report generated in coverage/html/index.html"
      DEPENDS run_tests
      WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
      COMMENT "Generating coverage report...")

    # Clean coverage data
    add_custom_target(
      coverage_clean
      COMMAND ${CMAKE_COMMAND} -E remove_directory coverage
      COMMAND find . -name "*.gcda" -delete
      COMMAND find . -name "*.gcno" -delete
      WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
      COMMENT "Cleaning coverage data...")
  else()
    message(
      WARNING "lcov/genhtml not found - coverage report target not available")
  endif()
endif()

# Print configuration
message(STATUS "FPBInject Tests Configuration:")
message(STATUS "  Coverage enabled: ${COVERAGE}")
message(STATUS "  C Compiler: ${CMAKE_C_COMPILER}")
message(STATUS "  C Flags: ${CMAKE_C_FLAGS}")
message(STATUS "  Source under test:")
foreach(src ${SUT_SOURCES})
  message(STATUS "    - ${src}")
endforeach()
