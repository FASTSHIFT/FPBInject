#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Compile commands parsing for FPBInject Web Server.

Provides functions for parsing compile_commands.json and .d dependency files
with robust error handling and cross-platform path support.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from core.safe_parser import (
    safe_shlex_split,
    parse_dep_file_command,
    path_matches_suffix,
    cached_parse,
)

logger = logging.getLogger(__name__)


def parse_dep_file_for_compile_command(
    source_file: str,
    build_output_dir: str = None,
) -> Optional[str]:
    """
    Parse .d dependency file to extract the original compile command.

    vendor/bes build system stores compile commands in .d files with format:
    cmd_<path>/<file>.o := <full compile command>

    Also supports other common formats via safe_parser.parse_dep_file_command.

    Args:
        source_file: Path to source file
        build_output_dir: Build output directory to search

    Returns:
        Compile command string or None
    """
    if not source_file:
        return None

    source_path = Path(source_file).resolve()
    source_basename = source_path.name
    source_name_no_ext = source_path.stem

    search_dirs: List[Path] = []
    if build_output_dir:
        search_dirs.append(Path(build_output_dir))

    # Search in common build output locations
    workspace_root = Path(__file__).parent.parent.parent.parent.parent.parent
    out_dir = workspace_root / "out"
    if out_dir.is_dir():
        search_dirs.append(out_dir)

    dep_file_pattern = f".{source_name_no_ext}.o.d"

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue

        try:
            # Use find command for efficiency
            result = subprocess.run(
                ["find", str(search_dir), "-name", dep_file_pattern, "-type", "f"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                dep_files = result.stdout.strip().split("\n")
                for dep_file_path in dep_files:
                    if not dep_file_path:
                        continue

                    compile_cmd = _try_parse_dep_file(
                        dep_file_path, str(source_path), source_basename
                    )
                    if compile_cmd:
                        return compile_cmd

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout searching for .d files in {search_dir}")
            continue
        except FileNotFoundError:
            # 'find' command not available (Windows), use os.walk fallback
            compile_cmd = _search_dep_files_walk(
                search_dir, dep_file_pattern, str(source_path), source_basename
            )
            if compile_cmd:
                return compile_cmd
        except Exception as e:
            logger.debug(f"Error searching for .d files: {e}")
            # Fallback to os.walk
            compile_cmd = _search_dep_files_walk(
                search_dir, dep_file_pattern, str(source_path), source_basename
            )
            if compile_cmd:
                return compile_cmd

    return None


def _try_parse_dep_file(
    dep_file_path: str, source_file: str, source_basename: str
) -> Optional[str]:
    """
    Try to parse a single .d file for compile command.

    Args:
        dep_file_path: Path to .d file
        source_file: Full source file path
        source_basename: Source file basename

    Returns:
        Compile command or None
    """
    try:
        content = Path(dep_file_path).read_text(errors="replace")

        # Check if this .d file is for our source
        if source_file not in content and source_basename not in content:
            return None

        logger.info(f"Found potential .d file: {dep_file_path}")

        # Try the new parser first (supports multiple formats)
        compile_cmd = parse_dep_file_command(content, source_file)
        if compile_cmd:
            logger.info(f"Found compile command in .d file: {dep_file_path}")
            return compile_cmd

        # Fallback: legacy parsing for cmd_... := format
        for line in content.split("\n"):
            if line.startswith("cmd_") and ":=" in line:
                cmd_start = line.find(":=")
                if cmd_start != -1:
                    compile_cmd = line[cmd_start + 2 :].strip()
                    logger.info(f"Found compile command in .d file: {dep_file_path}")
                    return compile_cmd

    except Exception as e:
        logger.debug(f"Error reading .d file {dep_file_path}: {e}")

    return None


def _search_dep_files_walk(
    search_dir: Path, dep_file_pattern: str, source_file: str, source_basename: str
) -> Optional[str]:
    """
    Search for .d files using os.walk (cross-platform fallback).

    Args:
        search_dir: Directory to search
        dep_file_pattern: Pattern to match .d files
        source_file: Full source file path
        source_basename: Source file basename

    Returns:
        Compile command or None
    """
    try:
        for root, dirs, files in os.walk(search_dir):
            # Skip common non-build directories
            dirs[:] = [
                d
                for d in dirs
                if d not in {".git", "__pycache__", "node_modules", ".svn", ".hg"}
            ]

            for f in files:
                if f == dep_file_pattern:
                    dep_file_path = os.path.join(root, f)
                    compile_cmd = _try_parse_dep_file(
                        dep_file_path, source_file, source_basename
                    )
                    if compile_cmd:
                        return compile_cmd
    except Exception as e:
        logger.debug(f"Error in os.walk search: {e}")

    return None


@cached_parse(maxsize=64)
def parse_compile_commands(
    compile_commands_path: str,
    source_file: str = None,
    verbose: bool = False,
) -> Optional[Dict]:
    """
    Parse standard CMake compile_commands.json to extract compiler flags.

    Features:
    - Supports both "command" (string) and "arguments" (array) formats
    - Robust path matching with suffix comparison
    - Fallback to .d file parsing
    - Safe command parsing with fallback on shlex errors
    - LRU caching for repeated calls

    Args:
        compile_commands_path: Path to compile_commands.json
        source_file: Optional source file to match
        verbose: Enable verbose logging

    Returns:
        Dictionary with compiler configuration or None
    """
    cc_path = Path(compile_commands_path)

    try:
        if not cc_path.exists():
            logger.error(f"compile_commands.json not found: {compile_commands_path}")
            return None
    except (PermissionError, OSError) as e:
        logger.error(f"Cannot access compile_commands.json: {e}")
        return None

    try:
        commands = json.loads(cc_path.read_text())
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in compile_commands.json: {e}")
        return None
    except (PermissionError, OSError) as e:
        logger.error(f"Cannot read compile_commands.json: {e}")
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
    source_file_normalized = None

    # First pass: try to match the exact source file
    if source_file:
        source_file_normalized = str(Path(source_file).resolve())
        source_file_basename = Path(source_file).name
        logger.info(
            f"Looking for source file in compile_commands: {source_file_normalized}"
        )

        for entry in commands:
            if not isinstance(entry, dict):
                continue
            file_path = entry.get("file", "")
            file_path_normalized = str(Path(file_path).resolve()) if file_path else ""

            # Try exact match first
            if file_path_normalized == source_file_normalized:
                selected_entry = entry
                logger.info(f"Found exact match in compile_commands.json: {file_path}")
                break

            # Try matching by path suffix
            if file_path.endswith(source_file_basename):
                if path_matches_suffix(
                    source_file_normalized, file_path_normalized, min_depth=3
                ):
                    selected_entry = entry
                    logger.info(
                        f"Found path suffix match in compile_commands.json: {file_path}"
                    )
                    break

    # Second pass: try to find a file in the same directory tree
    if not selected_entry and source_file:
        source_dir = Path(source_file).parent.resolve()
        search_dirs = [source_dir]

        # Add parent directories
        parent = source_dir
        for _ in range(3):
            parent = parent.parent
            if parent and parent.is_dir():
                search_dirs.append(parent)

        for search_dir in search_dirs:
            for entry in commands:
                if not isinstance(entry, dict):
                    continue
                file_path = entry.get("file", "")
                if not file_path.endswith(".c"):
                    continue

                file_dir = Path(file_path).parent.resolve()
                search_dir_str = str(search_dir)
                file_dir_str = str(file_dir)

                if file_dir_str.startswith(search_dir_str) or search_dir_str.startswith(
                    file_dir_str
                ):
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
        build_output_dir = str(cc_path.parent)
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

    # Parse the command
    if dep_file_command:
        tokens = safe_shlex_split(dep_file_command, fallback=True)
        if not tokens:
            logger.error("Failed to parse command from .d file")
            return None
    else:
        tokens = _extract_tokens_from_entry(selected_entry)
        if not tokens:
            return None

    # Extract compiler configuration from tokens
    return _parse_tokens(tokens, source_file, dep_file_command)


def _extract_tokens_from_entry(entry: Dict) -> Optional[List[str]]:
    """
    Extract command tokens from compile_commands.json entry.

    Supports both "command" (string) and "arguments" (array) formats.

    Args:
        entry: compile_commands.json entry

    Returns:
        List of tokens or None
    """
    # Support both "command" (string) and "arguments" (array) formats
    command_str = entry.get("command", "")
    arguments = entry.get("arguments", [])

    if arguments:
        # Bear or newer CMake uses "arguments" array
        if isinstance(arguments, list):
            logger.info("Using 'arguments' field from compile_commands.json")
            return arguments
        else:
            logger.error(
                "Invalid 'arguments' field in compile_commands.json: expected array"
            )
            return None
    elif command_str:
        # Older CMake uses "command" string
        tokens = safe_shlex_split(command_str, fallback=True)
        if tokens:
            logger.info("Using 'command' field from compile_commands.json")
            return tokens
        else:
            logger.error("Failed to parse command in compile_commands.json")
            return None
    else:
        logger.error("No command or arguments found in compile_commands.json entry")
        return None


def _parse_tokens(
    tokens: List[str], source_file: str = None, raw_command: str = None
) -> Dict:
    """
    Parse compiler tokens into configuration dictionary.

    Args:
        tokens: List of command tokens
        source_file: Optional source file path
        raw_command: Raw command string (if from .d file)

    Returns:
        Configuration dictionary
    """
    compiler = tokens[0] if tokens else "arm-none-eabi-gcc"
    includes: List[str] = []
    defines: List[str] = []
    cflags: List[str] = []

    i = 1
    while i < len(tokens):
        token = tokens[i]

        # Include paths
        if token == "-I" and i + 1 < len(tokens):
            includes.append(tokens[i + 1])
            i += 2
            continue
        elif token.startswith("-I"):
            includes.append(token[2:])
            i += 1
            continue

        # System include paths
        if token == "-isystem" and i + 1 < len(tokens):
            includes.append(tokens[i + 1])
            i += 2
            continue

        # Undefine macros
        if token == "-U" and i + 1 < len(tokens):
            cflags.extend(["-U", tokens[i + 1]])
            i += 2
            continue
        elif token.startswith("-U"):
            cflags.append(token)
            i += 1
            continue

        # Define macros
        if token == "-D" and i + 1 < len(tokens):
            defines.append(tokens[i + 1])
            i += 2
            continue
        elif token.startswith("-D"):
            defines.append(token[2:])
            i += 1
            continue

        # Skip output file
        if token == "-o" and i + 1 < len(tokens):
            i += 2
            continue

        # Skip source/object files
        if token.endswith((".c", ".cpp", ".S", ".s", ".o")):
            i += 1
            continue

        # Skip --param
        if token == "--param" and i + 1 < len(tokens):
            i += 2
            continue

        # Skip assembler flags
        if token.startswith("-Wa,"):
            i += 1
            continue

        # Architecture flags
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

    # Ensure -Os is present
    if "-Os" not in cflags:
        cflags.append("-Os")

    # Add source file directory and parent directories as include paths
    if source_file:
        source_path = Path(source_file)
        if source_path.exists():
            source_dir = source_path.parent.resolve()
            for _ in range(4):
                if source_dir.is_dir():
                    source_dir_str = str(source_dir)
                    if source_dir_str not in includes:
                        includes.append(source_dir_str)
                        logger.info(
                            f"Added source directory to includes: {source_dir_str}"
                        )
                    source_dir = source_dir.parent
                else:
                    break

    # Remove duplicates while preserving order
    includes = list(dict.fromkeys(includes))
    defines = list(dict.fromkeys(defines))
    cflags = list(dict.fromkeys(cflags))

    # Derive objcopy path from compiler
    compiler_path = Path(compiler)
    compiler_name = compiler_path.name
    objcopy_name = compiler_name.replace("gcc", "objcopy").replace("g++", "objcopy")
    objcopy = (
        str(compiler_path.parent / objcopy_name)
        if compiler_path.parent.name
        else objcopy_name
    )

    return {
        "compiler": compiler,
        "objcopy": objcopy,
        "includes": includes,
        "defines": defines,
        "cflags": cflags,
        "ldflags": [],
        "raw_command": raw_command,
    }
