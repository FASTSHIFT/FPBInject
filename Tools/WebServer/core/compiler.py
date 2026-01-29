#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Patch compiler for FPBInject Web Server.

Provides functions for parsing compile commands and compiling injection code.
"""

import json
import logging
import os
import re
import shlex
import subprocess
import tempfile
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def get_tool_path(tool_name: str, toolchain_path: Optional[str] = None) -> str:
    """Get full path for a toolchain tool."""
    if toolchain_path:
        full_path = os.path.join(toolchain_path, tool_name)
        if os.path.exists(full_path):
            return full_path
    return tool_name


def get_subprocess_env(toolchain_path: Optional[str] = None) -> dict:
    """Get environment dict with toolchain path prepended to PATH."""
    env = os.environ.copy()
    if toolchain_path and os.path.isdir(toolchain_path):
        current_path = env.get("PATH", "")
        env["PATH"] = f"{toolchain_path}:{current_path}"
    return env


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


def compile_inject(
    source_content: str,
    base_addr: int,
    elf_path: str = None,
    compile_commands_path: str = None,
    verbose: bool = False,
    source_ext: str = None,
    original_source_file: str = None,
    toolchain_path: Optional[str] = None,
) -> Tuple[Optional[bytes], Optional[Dict[str, int]], str]:
    """
    Compile injection code from source content to binary.

    Args:
        source_content: Source code content to compile
        base_addr: Base address for injection code
        elf_path: Path to main ELF for symbol resolution
        compile_commands_path: Path to compile_commands.json
        verbose: Enable verbose output
        source_ext: Source file extension (.c or .cpp), auto-detect if None
        original_source_file: Path to original source file for matching compile flags
        toolchain_path: Path to toolchain binaries

    Returns:
        Tuple of (binary_data, symbols, error_message)
    """
    logger.info(
        f"compile_inject called with original_source_file={original_source_file}"
    )
    config = None
    if compile_commands_path:
        config = parse_compile_commands(
            compile_commands_path,
            source_file=original_source_file,
            verbose=verbose,
        )

    if not config:
        return (
            None,
            None,
            "No compile configuration found. Please provide compile_commands.json path.",
        )

    compiler = config.get("compiler", "arm-none-eabi-gcc")
    objcopy = config.get("objcopy", "arm-none-eabi-objcopy")
    raw_command = config.get("raw_command")  # Raw command from .d file

    if not os.path.isabs(compiler):
        compiler = get_tool_path(compiler, toolchain_path)
    if not os.path.isabs(objcopy):
        objcopy = get_tool_path(objcopy, toolchain_path)

    includes = config.get("includes", [])
    defines = config.get("defines", [])
    cflags = config.get("cflags", [])

    with tempfile.TemporaryDirectory() as tmpdir:
        # Determine file extension: use provided or default to .c
        ext = source_ext if source_ext else ".c"
        if not ext.startswith("."):
            ext = "." + ext

        # Write source to file
        source_file = os.path.join(tmpdir, f"inject{ext}")
        with open(source_file, "w") as f:
            f.write(source_content)

        obj_file = os.path.join(tmpdir, "inject.o")
        elf_file = os.path.join(tmpdir, "inject.elf")
        bin_file = os.path.join(tmpdir, "inject.bin")

        # Use raw command from .d file if available (direct passthrough)
        if raw_command:
            import shlex

            # Parse the raw command and replace input/output files
            raw_tokens = shlex.split(raw_command)
            cmd = []
            i = 0
            while i < len(raw_tokens):
                token = raw_tokens[i]
                # Skip dependency generation flags
                if token in ["-MD", "-MP"]:
                    i += 1
                    continue
                elif token in ["-MF", "-MT", "-MQ"] and i + 1 < len(raw_tokens):
                    i += 2  # Skip flag and its argument
                    continue
                elif token == "-o" and i + 1 < len(raw_tokens):
                    # Replace output file
                    cmd.extend(["-o", obj_file])
                    i += 2
                elif token == "-c":
                    cmd.append(token)
                    i += 1
                elif token.endswith((".c", ".cpp", ".S", ".s")):
                    # Skip original source file (we'll add ours at the end)
                    i += 1
                else:
                    cmd.append(token)
                    i += 1
            # Add our source file and -Wno-error
            cmd.extend(["-Wno-error", source_file])
            logger.info(f"Using raw command from .d file (passthrough)")
        else:
            # Build command from parsed components
            cmd = (
                [compiler]
                + cflags
                + [
                    "-c",
                    "-ffunction-sections",
                    "-fdata-sections",
                    "-Wno-error",  # Don't treat warnings as errors (vendor code may have warnings)
                ]
            )

            for inc in includes:
                if os.path.isdir(inc):
                    cmd.extend(["-I", inc])

            for d in defines:
                cmd.extend(["-D", d])

            cmd.extend(["-o", obj_file, source_file])

        if verbose:
            logger.info(f"Compile: {' '.join(cmd)}")

        # Use environment with toolchain path in PATH for ccache to find compiler
        env = get_subprocess_env(toolchain_path)
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            return None, None, f"Compile error:\n{result.stderr}"

        # Create linker script
        ld_content = f"""
ENTRY(inject_entry)
SECTIONS
{{
    . = 0x{base_addr:08X};
    .text : {{
        KEEP(*(.text.inject*))
        *(.text .text.*)
    }}
    .rodata : {{ *(.rodata .rodata.*) }}
    .data : {{ *(.data .data.*) }}
    .bss : {{ *(.bss .bss.* COMMON) }}
}}
"""
        ld_file = os.path.join(tmpdir, "inject.ld")
        with open(ld_file, "w") as f:
            f.write(ld_content)

        # Link with --gc-sections to remove unused code
        link_cmd = (
            [compiler] + cflags[:2] + ["-nostartfiles", "-nostdlib", f"-T{ld_file}"]
        )
        link_cmd.append("-Wl,--gc-sections")

        # Find inject_* function names from source to keep them with -u
        inject_func_pattern = re.compile(r"\binject_(\w+)\s*\(")
        inject_funcs = inject_func_pattern.findall(source_content)
        for func in set(inject_funcs):
            link_cmd.append(f"-Wl,-u,inject_{func}")

        if elf_path and os.path.exists(elf_path):
            link_cmd.append(f"-Wl,--just-symbols={elf_path}")

        link_cmd.extend(["-o", elf_file, obj_file])

        if verbose:
            logger.info(f"Link: {' '.join(link_cmd)}")

        result = subprocess.run(link_cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            return None, None, f"Link error:\n{result.stderr}"

        # Extract binary
        result = subprocess.run(
            [objcopy, "-O", "binary", elf_file, bin_file],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            return None, None, f"Objcopy error:\n{result.stderr}"

        # Read binary
        with open(bin_file, "rb") as f:
            data = f.read()

        # Fix Thumb bit in veneer addresses
        # When using --just-symbols, the linker generates veneers for long calls
        # but doesn't set the Thumb bit (bit 0) for Thumb functions.
        # Veneer pattern: LDR PC, [PC, #0] followed by 4-byte address
        # Machine code: F8 5F F0 00 (ldr.w pc, [pc]) followed by address
        data = fix_veneer_thumb_bits(data, base_addr, elf_path, toolchain_path, verbose)

        # Get symbols - use --defined-only to exclude symbols from --just-symbols
        # and filter by address range to only include symbols in our inject code
        nm_cmd = objcopy.replace("objcopy", "nm")
        result = subprocess.run(
            [nm_cmd, "-C", "--defined-only", elf_file],
            capture_output=True,
            text=True,
            env=env,
        )

        symbols = {}
        all_symbols_debug = []  # For debugging: collect all parsed symbols
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    addr = int(parts[0], 16)
                    sym_type = parts[1]  # T=text global, t=text local, etc.
                    # For demangled names (nm -C), the name may contain spaces
                    # e.g., "inject_foo(int, char*)" becomes multiple parts
                    # Join all parts after the type to get the full name
                    full_name = " ".join(parts[2:])
                    # Extract just the function name (before the first '(' if present)
                    if "(" in full_name:
                        name = full_name.split("(")[0]
                    else:
                        name = full_name
                    all_symbols_debug.append(f"{parts[0]} {sym_type} {name}")
                    # Only include text section symbols (T or t) that are in our base_addr range
                    # This filters out symbols imported via --just-symbols
                    if sym_type.upper() == "T" and addr >= base_addr:
                        symbols[name] = addr
                        logger.debug(
                            f"Including symbol: {name} @ 0x{addr:08X} (type={sym_type})"
                        )
                    else:
                        logger.debug(
                            f"Excluding symbol: {name} @ 0x{addr:08X} (type={sym_type}, base_addr=0x{base_addr:08X})"
                        )
                except (ValueError, IndexError):
                    # Address field is not a valid hex number or malformed line
                    logger.debug(f"Skipping malformed nm line: {line}")
                    pass

        # Log inject_* symbols for debugging
        inject_syms = {k: v for k, v in symbols.items() if "inject" in k.lower()}
        if inject_syms:
            logger.info(f"Found inject symbols: {inject_syms}")
        else:
            logger.warning(
                f"No inject_* symbols found in compiled ELF. Total symbols: {len(symbols)}"
            )
            # Log all symbols for debugging (use warning level to ensure visibility)
            logger.warning(f"All defined text symbols: {list(symbols.keys())}")
            # Also log raw nm output for debugging
            logger.warning(f"Raw nm output:\n{result.stdout[:2000]}")
            # Log source content first 500 chars to check if inject_ functions exist
            logger.warning(
                f"Source content preview (first 1000 chars):\n{source_content[:1000]}"
            )
            # Check if source contains inject_ pattern
            inject_pattern = re.findall(r"\binject_\w+", source_content)
            if inject_pattern:
                logger.warning(
                    f"Found inject_ patterns in source: {inject_pattern[:10]}"
                )
            else:
                logger.warning("No inject_ patterns found in source code!")

        return data, symbols, ""


def fix_veneer_thumb_bits(
    data: bytes,
    base_addr: int,
    elf_path: str,
    toolchain_path: Optional[str] = None,
    verbose: bool = False,
) -> bytes:
    """
    Fix Thumb bit in linker-generated veneer addresses.

    When using --just-symbols, GCC linker generates long call veneers like:
        ldr.w pc, [pc, #0]   ; F8 5F F0 00
        .word <address>      ; Target address (missing Thumb bit)

    For Thumb functions, the target address must have bit 0 set.
    """
    if not elf_path or len(data) < 8:
        return data

    # Build a set of Thumb function addresses from the ELF
    thumb_funcs = set()
    try:
        readelf_cmd = get_tool_path("arm-none-eabi-readelf", toolchain_path)
        result = subprocess.run(
            [readelf_cmd, "-s", elf_path],
            capture_output=True,
            text=True,
            env=get_subprocess_env(toolchain_path),
        )
        for line in result.stdout.split("\n"):
            parts = line.split()
            if len(parts) >= 8 and parts[3] == "FUNC":
                try:
                    addr = int(parts[1], 16)
                    if addr & 1:
                        thumb_funcs.add(addr & ~1)
                except ValueError:
                    pass
    except Exception as e:
        logger.warning(f"Failed to read ELF symbols for Thumb fix: {e}")
        return data

    if not thumb_funcs:
        return data

    data = bytearray(data)

    # Pattern: F8 5F F0 00 = ldr.w pc, [pc, #0] (little-endian: 5F F8 00 F0)
    veneer_pattern = bytes([0x5F, 0xF8, 0x00, 0xF0])
    fixed_count = 0

    i = 0
    while i < len(data) - 8:
        if data[i : i + 4] == veneer_pattern:
            addr_offset = i + 4
            target_addr = int.from_bytes(data[addr_offset : addr_offset + 4], "little")

            if (target_addr & 1) == 0 and target_addr in thumb_funcs:
                fixed_addr = target_addr | 1
                data[addr_offset : addr_offset + 4] = fixed_addr.to_bytes(4, "little")
                fixed_count += 1
                if verbose:
                    veneer_addr = base_addr + i
                    logger.info(
                        f"Fixed veneer Thumb bit at 0x{veneer_addr:08X}: "
                        f"0x{target_addr:08X} -> 0x{fixed_addr:08X}"
                    )
            i += 8
        else:
            i += 2

    if fixed_count > 0:
        logger.info(f"Fixed {fixed_count} veneer Thumb bit(s)")

    return bytes(data)
