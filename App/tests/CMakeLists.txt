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
option(ASAN "Enable AddressSanitizer" ON)

if(COVERAGE)
  set(CMAKE_C_FLAGS
      "${CMAKE_C_FLAGS} -g -O0 --coverage -fprofile-arcs -ftest-coverage")
  set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} --coverage")
endif()

# AddressSanitizer for memory error detection
if(ASAN)
  set(CMAKE_C_FLAGS
      "${CMAKE_C_FLAGS} -fsanitize=address -fno-omit-frame-pointer -g")
  set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -fsanitize=address")
endif()

# Warning flags - treat warnings as errors
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -Werror")

# Enable POSIX features for getpid, access, rmdir, etc.
add_definitions(-D_DEFAULT_SOURCE)

# Define host-based testing (no real hardware)
add_definitions(-DFPB_HOST_TESTING=1)
add_definitions(-DFL_USE_FILE=1)
add_definitions(-DFL_FILE_USE_LIBC=1)

# Note: FPB_HOST_TESTING enables mock registers and disables ARM assembly in
# fpb_inject.c, fpb_debugmon.c, and fpb_trampoline.c FPB_HOST_TESTING_NUTTX is
# defined only for test_runner_nuttx target

# Project directories
set(SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../Source)
set(APP_DIR ${CMAKE_CURRENT_SOURCE_DIR}/..)
set(FUNC_LOADER_DIR ${APP_DIR}/func_loader)
set(NUTTX_MOCK_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../Tools/nuttx_mock)

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR} ${SRC_DIR} ${FUNC_LOADER_DIR}
                    ${FUNC_LOADER_DIR}/argparse ${NUTTX_MOCK_DIR})

# ============================================================================
# Source Under Test (SUT) - Real production code
# ============================================================================
set(SUT_SOURCES_COMMON
    # FPB core
    ${SRC_DIR}/fpb_inject.c
    # FPB trampoline (uses mock addresses when FPB_HOST_TESTING is defined)
    ${SRC_DIR}/fpb_trampoline.c
    # Function loader core
    ${FUNC_LOADER_DIR}/fl.c
    ${FUNC_LOADER_DIR}/fl_stream.c
    ${FUNC_LOADER_DIR}/fl_log.c
    ${FUNC_LOADER_DIR}/fl_allocator.c
    # File transfer (libc backend for host)
    ${FUNC_LOADER_DIR}/fl_file.c
    ${FUNC_LOADER_DIR}/fl_file_libc.c
    # Argparse library
    ${FUNC_LOADER_DIR}/argparse/argparse.c)

# FatFS test sources (uses mock FatFS)
set(SUT_SOURCES_FATFS
    # FPB core
    ${SRC_DIR}/fpb_inject.c
    ${SRC_DIR}/fpb_trampoline.c
    # Function loader core
    ${FUNC_LOADER_DIR}/fl.c
    ${FUNC_LOADER_DIR}/fl_stream.c
    ${FUNC_LOADER_DIR}/fl_log.c
    ${FUNC_LOADER_DIR}/fl_allocator.c
    # File transfer (generic + FatFS backend)
    ${FUNC_LOADER_DIR}/fl_file.c
    ${FUNC_LOADER_DIR}/fl_file_fatfs.c
    # Argparse library
    ${FUNC_LOADER_DIR}/argparse/argparse.c)

# Main test runner uses standard debugmon
set(SUT_SOURCES_MAIN
    ${SUT_SOURCES_COMMON}
    # FPB debugmon (uses mock registers when FPB_HOST_TESTING is defined)
    ${SRC_DIR}/fpb_debugmon.c)

# NuttX test runner uses NuttX-specific debugmon
set(SUT_SOURCES_NUTTX
    ${SUT_SOURCES_COMMON}
    # FPB debugmon NuttX (uses nuttx_mock when FPB_HOST_TESTING_NUTTX is
    # defined)
    ${SRC_DIR}/fpb_debugmon_nuttx.c)

# ============================================================================
# Mock/Test Framework Sources
# ============================================================================
set(MOCK_SOURCES fpb_mock_regs.c mock_hardware.c)

set(MOCK_SOURCES_NUTTX fpb_mock_regs.c mock_hardware.c
                       ${NUTTX_MOCK_DIR}/nuttx_mock.c)

set(MOCK_SOURCES_FATFS fpb_mock_regs.c mock_hardware.c mock_fatfs.c)

set(TEST_FRAMEWORK_SOURCES test_framework.c)

# ============================================================================
# Test Sources
# ============================================================================
set(TEST_SOURCES_MAIN
    test_main.c
    test_func_allocator.c
    test_func_loader.c
    test_func_loader_stream.c
    test_func_loader_file.c
    test_fpb_inject.c
    test_fpb_debugmon.c
    test_fpb_trampoline.c)

set(TEST_SOURCES_NUTTX test_fpb_debugmon_nuttx.c)

set(TEST_SOURCES_FATFS test_main_fatfs.c test_func_loader_file_fatfs.c)

# ============================================================================
# Main test executable (standard debugmon)
# ============================================================================
add_executable(test_runner ${SUT_SOURCES_MAIN} ${MOCK_SOURCES}
                           ${TEST_FRAMEWORK_SOURCES} ${TEST_SOURCES_MAIN})
target_link_libraries(test_runner m)

# ============================================================================
# NuttX test executable (NuttX-specific debugmon)
# ============================================================================
add_executable(
  test_runner_nuttx ${SUT_SOURCES_NUTTX} ${MOCK_SOURCES_NUTTX}
                    ${TEST_FRAMEWORK_SOURCES} ${TEST_SOURCES_NUTTX})
target_compile_definitions(test_runner_nuttx PRIVATE FPB_HOST_TESTING_NUTTX=1)
target_link_libraries(test_runner_nuttx m)

# ============================================================================
# FatFS test executable
# ============================================================================
add_executable(
  test_runner_fatfs
  ${SUT_SOURCES_FATFS} ${MOCK_SOURCES_FATFS} ${TEST_FRAMEWORK_SOURCES}
  ${TEST_SOURCES_FATFS} ${SRC_DIR}/fpb_debugmon.c)
target_compile_definitions(test_runner_fatfs PRIVATE FL_USE_FILE=1
                                                     FL_FILE_USE_FATFS=1)
target_link_libraries(test_runner_fatfs m)

# Custom target for running all tests
add_custom_target(
  run_tests
  COMMAND ${CMAKE_COMMAND} -E echo "=== Running main tests ==="
  COMMAND ./test_runner
  COMMAND ${CMAKE_COMMAND} -E echo ""
  COMMAND ${CMAKE_COMMAND} -E echo "=== Running NuttX debugmon tests ==="
  COMMAND ./test_runner_nuttx
  COMMAND ${CMAKE_COMMAND} -E echo ""
  COMMAND ${CMAKE_COMMAND} -E echo "=== Running FatFS tests ==="
  COMMAND ./test_runner_fatfs
  DEPENDS test_runner test_runner_nuttx test_runner_fatfs
  WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
  COMMENT "Running all unit tests...")

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
message(STATUS "  AddressSanitizer enabled: ${ASAN}")
message(STATUS "  C Compiler: ${CMAKE_C_COMPILER}")
message(STATUS "  C Flags: ${CMAKE_C_FLAGS}")
message(STATUS "  Source under test:")
foreach(src ${SUT_SOURCES})
  message(STATUS "    - ${src}")
endforeach()
