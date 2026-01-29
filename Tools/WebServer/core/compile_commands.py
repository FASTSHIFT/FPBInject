#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Compile commands parsing for FPBInject Web Server.

Provides functions for parsing compile_commands.json and .d dependency files.
"""

import json
import logging
import os
import shlex
import subprocess
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def parse_dep_file_for_compile_command(
    source_file: str,
    build_output_dir: str = None,
) -> Optional[str]:
    """
    Parse .d dependency file to extract the original compile command.

    vendor/bes build system stores compile commands in .d files with format:
    cmd_<path>/<file>.o := <full compile command>
    """
    if not source_file:
        return None

    source_file = os.path.normpath(source_file)
    source_basename = os.path.basename(source_file)
    source_name_no_ext = os.path.splitext(source_basename)[0]

    search_dirs = []
    if build_output_dir:
        search_dirs.append(build_output_dir)

    # Search in common build output locations
    workspace_root = os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            )
        )
    )

    out_dir = os.path.join(workspace_root, "out")
    if os.path.isdir(out_dir):
        search_dirs.append(out_dir)

    dep_file_pattern = f".{source_name_no_ext}.o.d"

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue

        try:
            result = subprocess.run(
                ["find", search_dir, "-name", dep_file_pattern, "-type", "f"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                dep_files = result.stdout.strip().split("\n")
                for dep_file_path in dep_files:
                    if not dep_file_path:
                        continue
                    logger.info(f"Found potential .d file: {dep_file_path}")

                    try:
                        with open(dep_file_path, "r") as df:
                            content = df.read()

                        if source_file in content or source_basename in content:
                            for line in content.split("\n"):
                                if line.startswith("cmd_") and ":=" in line:
                                    cmd_start = line.find(":=")
                                    if cmd_start != -1:
                                        compile_cmd = line[cmd_start + 2 :].strip()
                                        logger.info(
                                            f"Found compile command in .d file: {dep_file_path}"
                                        )
                                        return compile_cmd
                    except Exception as e:
                        logger.debug(f"Error reading .d file {dep_file_path}: {e}")
                        continue
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout searching for .d files in {search_dir}")
            continue
        except Exception as e:
            logger.debug(f"Error searching for .d files: {e}")
            # Fallback to os.walk
            for root, dirs, files in os.walk(search_dir):
                for f in files:
                    if f == dep_file_pattern:
                        dep_file_path = os.path.join(root, f)
                        logger.info(f"Found potential .d file: {dep_file_path}")

                        try:
                            with open(dep_file_path, "r") as df:
                                content = df.read()

                            if source_file in content or source_basename in content:
                                for line in content.split("\n"):
                                    if line.startswith("cmd_") and ":=" in line:
                                        cmd_start = line.find(":=")
                                        if cmd_start != -1:
                                            compile_cmd = line[cmd_start + 2 :].strip()
                                            logger.info(
                                                f"Found compile command in .d file: {dep_file_path}"
                                            )
                                            return compile_cmd
                        except Exception as e2:
                            logger.debug(f"Error reading .d file {dep_file_path}: {e2}")
                            continue

    return None


def parse_compile_commands(
    compile_commands_path: str,
    source_file: str = None,
    verbose: bool = False,
) -> Optional[Dict]:
    """
    Parse standard CMake compile_commands.json to extract compiler flags.
    """
    if not os.path.exists(compile_commands_path):
        logger.error(f"compile_commands.json not found: {compile_commands_path}")
        return None

    try:
        with open(compile_commands_path, "r") as f:
            commands = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in compile_commands.json: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading compile_commands.json: {e}")
        return None

    if not commands:
        logger.error("compile_commands.json is empty")
        return None

    if not isinstance(commands, list):
        logger.error(
            f"Invalid compile_commands.json format: expected array, got {type(commands).__name__}. "
            "Please use standard CMake compile_commands.json (set CMAKE_EXPORT_COMPILE_COMMANDS=ON)"
        )
        return None

    selected_entry = None

    # First pass: try to match the exact source file
    if source_file:
        source_file_normalized = os.path.normpath(source_file)
        logger.info(
            f"Looking for source file in compile_commands: {source_file_normalized}"
        )
        for entry in commands:
            if not isinstance(entry, dict):
                continue
            file_path = entry.get("file", "")
            if os.path.normpath(file_path) == source_file_normalized:
                selected_entry = entry
                logger.info(f"Found exact match in compile_commands.json: {file_path}")
                break

    # Second pass: try to find a file in the same directory or parent directories
    if not selected_entry and source_file:
        source_dir = os.path.dirname(os.path.normpath(source_file))
        search_dirs = [source_dir]
        parent = source_dir
        for _ in range(3):
            parent = os.path.dirname(parent)
            if parent:
                search_dirs.append(parent)

        for search_dir in search_dirs:
            if not search_dir:
                continue
            for entry in commands:
                if not isinstance(entry, dict):
                    continue
                file_path = entry.get("file", "")
                if not file_path.endswith(".c"):
                    continue
                file_dir = os.path.dirname(os.path.normpath(file_path))
                if file_dir.startswith(search_dir) or search_dir.startswith(file_dir):
                    selected_entry = entry
                    logger.info(
                        f"Found related file in compile_commands.json: {file_path} "
                        f"(same directory tree as {source_file})"
                    )
                    break
            if selected_entry:
                break

    # Third pass: try to find compile command from .d dependency file
    dep_file_command = None
    if not selected_entry and source_file:
        build_output_dir = os.path.dirname(compile_commands_path)
        dep_file_command = parse_dep_file_for_compile_command(
            source_file, build_output_dir
        )
        if dep_file_command:
            logger.info(f"Found compile command from .d file for: {source_file}")

    # Fourth pass: fallback to any C file
    if not selected_entry and not dep_file_command:
        for entry in commands:
            if not isinstance(entry, dict):
                continue
            file_path = entry.get("file", "")
            if file_path.endswith(".c") and "__ASSEMBLY__" not in entry.get(
                "command", ""
            ):
                selected_entry = entry
                logger.warning(
                    f"Using fallback compile command from: {file_path} "
                    "(source file not found in compile_commands.json)"
                )
                break

    if not selected_entry and not dep_file_command:
        logger.error("No suitable C file entry found in compile_commands.json")
        return None

    if dep_file_command:
        command_str = dep_file_command
    else:
        command_str = selected_entry.get("command", "")
    if not command_str:
        logger.error("No command found in compile_commands.json entry")
        return None

    try:
        tokens = shlex.split(command_str)
    except Exception as e:
        logger.error(f"Error parsing command in compile_commands.json: {e}")
        return None

    compiler = tokens[0] if tokens else "arm-none-eabi-gcc"
    includes = []
    defines = []
    cflags = []

    i = 1
    while i < len(tokens):
        token = tokens[i]

        if token == "-I" and i + 1 < len(tokens):
            includes.append(tokens[i + 1])
            i += 2
            continue
        elif token.startswith("-I"):
            includes.append(token[2:])
            i += 1
            continue

        if token == "-isystem" and i + 1 < len(tokens):
            includes.append(tokens[i + 1])
            i += 2
            continue

        if token == "-U" and i + 1 < len(tokens):
            undef_value = tokens[i + 1]
            cflags.extend(["-U", undef_value])
            i += 2
            continue
        elif token.startswith("-U"):
            cflags.append(token)
            i += 1
            continue

        if token == "-D" and i + 1 < len(tokens):
            define_value = tokens[i + 1]
            defines.append(define_value)
            i += 2
            continue
        elif token.startswith("-D"):
            define_value = token[2:]
            defines.append(define_value)
            i += 1
            continue

        if token == "-o" and i + 1 < len(tokens):
            i += 2
            continue

        if token.endswith((".c", ".cpp", ".S", ".s", ".o")):
            i += 1
            continue

        if token == "--param" and i + 1 < len(tokens):
            i += 2
            continue

        if token.startswith("-Wa,"):
            i += 1
            continue

        if any(
            token.startswith(p)
            for p in ["-mthumb", "-mcpu", "-mtune", "-march", "-mfpu", "-mfloat-abi"]
        ):
            cflags.append(token)
        elif token in [
            "-ffunction-sections",
            "-fdata-sections",
            "-fno-common",
            "-nostdlib",
        ]:
            cflags.append(token)

        i += 1

    if "-Os" not in cflags:
        cflags.append("-Os")

    # Add source file directory and parent directories as include paths
    if source_file and os.path.exists(source_file):
        source_dir = os.path.dirname(os.path.abspath(source_file))
        for _ in range(4):
            if source_dir and os.path.isdir(source_dir):
                if source_dir not in includes:
                    includes.append(source_dir)
                    logger.info(f"Added source directory to includes: {source_dir}")
                source_dir = os.path.dirname(source_dir)
            else:
                break

    includes = list(dict.fromkeys(includes))
    defines = list(dict.fromkeys(defines))
    cflags = list(dict.fromkeys(cflags))

    compiler_dir = os.path.dirname(compiler)
    compiler_name = os.path.basename(compiler)
    objcopy_name = compiler_name.replace("gcc", "objcopy").replace("g++", "objcopy")
    objcopy = os.path.join(compiler_dir, objcopy_name) if compiler_dir else objcopy_name

    return {
        "compiler": compiler,
        "objcopy": objcopy,
        "includes": includes,
        "defines": defines,
        "cflags": cflags,
        "ldflags": [],
        "raw_command": dep_file_command,
    }
