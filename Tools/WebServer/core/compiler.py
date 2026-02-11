#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Patch compiler for FPBInject Web Server.

Provides functions for compiling injection code.
"""

import logging
import os
import re
import subprocess
import tempfile
from typing import Dict, Optional, Tuple

from utils.toolchain import get_tool_path, get_subprocess_env
from core.compile_commands import parse_compile_commands
from core.compile_commands import parse_dep_file_for_compile_command  # noqa: F401

logger = logging.getLogger(__name__)


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
            logger.info("Using raw command from .d file (passthrough)")
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
        # Note: We include .bss in the binary by adding a marker section after it.
        # This ensures that static/global variables with zero initialization
        # are properly zeroed in the uploaded binary.
        ld_content = f"""
SECTIONS
{{
    . = 0x{base_addr:08X};
    .text : {{
        KEEP(*(.fpb.text))     /* FPB inject functions */
        *(.text .text.*)
    }}
    .rodata : {{ *(.rodata .rodata.*) }}
    .data : {{ *(.data .data.*) }}
    .bss : {{
        __bss_start__ = .;
        *(.bss .bss.* COMMON)
        . = ALIGN(4);
        __bss_end__ = .;
    }}
    /* Force objcopy to include BSS section (with zeros) in the binary */
    .fpb_end : {{
        BYTE(0x00)
    }}
}}
"""
        ld_file = os.path.join(tmpdir, "inject.ld")
        with open(ld_file, "w") as f:
            f.write(ld_content)

        # Link with --gc-sections to remove unused code
        # Use --allow-multiple-definition to let patch functions override firmware symbols
        link_cmd = (
            [compiler] + cflags[:2] + ["-nostartfiles", "-nostdlib", f"-T{ld_file}"]
        )
        link_cmd.append("-Wl,--gc-sections")
        link_cmd.append("-Wl,--allow-multiple-definition")

        # Find FPB_INJECT marked functions from source to keep them with -u
        # Pattern: /* FPB_INJECT */ followed by optional __attribute__ and function definition
        # Use .*? with DOTALL to handle __attribute__((...)) with nested parentheses
        fpb_marker_pattern = re.compile(
            r"/\*\s*FPB_INJECT\s*\*/\s*\n"
            r"(?:__attribute__\s*\(\(.*?\)\)\s*\n?)?"
            r"(?:extern\s+\"C\"\s+)?"
            r"(?:static\s+|inline\s+|const\s+|volatile\s+)*"
            r"(?:void|int|char|unsigned|signed|long|short|float|double|"
            r"uint\d+_t|int\d+_t|size_t|ssize_t|bool|_Bool|"
            r"\w+\s*\*?)\s+"
            r"(\w+)\s*\(",
            re.MULTILINE | re.IGNORECASE | re.DOTALL,
        )
        fpb_funcs = fpb_marker_pattern.findall(source_content)
        for func in set(fpb_funcs):
            if func not in ("if", "while", "for", "switch", "return"):
                link_cmd.append(f"-Wl,-u,{func}")

        # IMPORTANT: obj_file MUST come BEFORE --just-symbols!
        # With --allow-multiple-definition, the linker uses the FIRST definition.
        # If --just-symbols comes first, the firmware's symbol address will be used
        # instead of our patch function definition.
        link_cmd.extend(["-o", elf_file, obj_file])

        if elf_path and os.path.exists(elf_path):
            link_cmd.append(f"-Wl,--just-symbols={elf_path}")

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
                    # e.g., "foo(int, char*)" becomes multiple parts
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

        # Log FPB inject symbols for debugging
        fpb_syms = {k: v for k, v in symbols.items() if k in fpb_funcs}
        if fpb_syms:
            logger.info(f"Found FPB inject symbols: {fpb_syms}")
        elif fpb_funcs:
            logger.warning(
                f"Expected FPB inject functions {fpb_funcs} not found in compiled ELF. Total symbols: {len(symbols)}"
            )
            # Log all symbols for debugging (use warning level to ensure visibility)
            logger.warning(f"All defined text symbols: {list(symbols.keys())}")
            # Also log raw nm output for debugging
            logger.warning(f"Raw nm output:\n{result.stdout[:2000]}")
            # Log source content first 1000 chars
            logger.warning(
                f"Source content preview (first 1000 chars):\n{source_content[:1000]}"
            )
        else:
            logger.warning("No FPB_INJECT markers found in source code!")

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
