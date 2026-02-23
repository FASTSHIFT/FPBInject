#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Patch compiler for FPBInject Web Server.

Provides functions for compiling injection code with robust
command construction and cross-platform support.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from utils.toolchain import get_tool_path, get_subprocess_env
from core.compile_commands import parse_compile_commands
from core.compile_commands import parse_dep_file_for_compile_command  # noqa: F401
from core.safe_parser import (
    safe_shlex_split,
    FPBMarkerParser,
)
from core.linker_script import LinkerScriptGenerator, LinkerScriptConfig

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
    linker_config: Dict = None,
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
        linker_config: Optional linker script configuration

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
    raw_command = config.get("raw_command")

    # Resolve tool paths
    if not os.path.isabs(compiler):
        compiler = get_tool_path(compiler, toolchain_path)
    if not os.path.isabs(objcopy):
        objcopy = get_tool_path(objcopy, toolchain_path)

    includes = config.get("includes", [])
    defines = config.get("defines", [])
    cflags = config.get("cflags", [])

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Determine file extension
        ext = source_ext if source_ext else ".c"
        if not ext.startswith("."):
            ext = "." + ext

        # Write source to file
        source_file = tmpdir_path / f"inject{ext}"
        source_file.write_text(source_content)

        obj_file = tmpdir_path / "inject.o"
        elf_file = tmpdir_path / "inject.elf"
        bin_file = tmpdir_path / "inject.bin"

        # Build compile command
        if raw_command:
            cmd = _build_command_from_raw(raw_command, str(obj_file), str(source_file))
            logger.info("Using raw command from .d file (passthrough)")
        else:
            cmd = _build_compile_command(
                compiler, cflags, includes, defines, str(obj_file), str(source_file)
            )

        if verbose:
            logger.info(f"Compile: {' '.join(cmd)}")

        # Execute compilation
        env = get_subprocess_env(toolchain_path)
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            return None, None, f"Compile error:\n{result.stderr}"

        # Generate linker script using template system
        ld_file = tmpdir_path / "inject.ld"
        _generate_linker_script(base_addr, str(ld_file), linker_config)

        # Find FPB_INJECT marked functions using robust parser
        fpb_funcs = FPBMarkerParser.extract_function_names(source_content)

        # Build link command
        link_cmd = _build_link_command(
            compiler,
            cflags,
            str(ld_file),
            str(elf_file),
            str(obj_file),
            elf_path,
            fpb_funcs,
        )

        if verbose:
            logger.info(f"Link: {' '.join(link_cmd)}")

        result = subprocess.run(link_cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            return None, None, f"Link error:\n{result.stderr}"

        # Extract binary
        result = subprocess.run(
            [objcopy, "-O", "binary", str(elf_file), str(bin_file)],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            return None, None, f"Objcopy error:\n{result.stderr}"

        # Read binary
        data = bin_file.read_bytes()

        # Fix Thumb bit in veneer addresses
        data = fix_veneer_thumb_bits(data, base_addr, elf_path, toolchain_path, verbose)

        # Get symbols
        symbols = _extract_symbols(
            objcopy, str(elf_file), base_addr, fpb_funcs, source_content, env
        )

        return data, symbols, ""


def _build_command_from_raw(
    raw_command: str, obj_file: str, source_file: str
) -> List[str]:
    """
    Build compile command from raw .d file command.

    Args:
        raw_command: Raw command string from .d file
        obj_file: Output object file path
        source_file: Input source file path

    Returns:
        Command as list of arguments
    """
    raw_tokens = safe_shlex_split(raw_command, fallback=True)
    cmd = []
    i = 0

    while i < len(raw_tokens):
        token = raw_tokens[i]

        # Skip dependency generation flags
        if token in ["-MD", "-MP"]:
            i += 1
            continue
        elif token in ["-MF", "-MT", "-MQ"] and i + 1 < len(raw_tokens):
            i += 2
            continue
        elif token == "-o" and i + 1 < len(raw_tokens):
            # Replace output file with our path (properly quoted)
            cmd.extend(["-o", obj_file])
            i += 2
        elif token == "-c":
            cmd.append(token)
            i += 1
        elif token.endswith((".c", ".cpp", ".S", ".s")):
            # Skip original source file
            i += 1
        else:
            cmd.append(token)
            i += 1

    # Add our source file and -Wno-error
    cmd.extend(["-Wno-error", source_file])
    return cmd


def _build_compile_command(
    compiler: str,
    cflags: List[str],
    includes: List[str],
    defines: List[str],
    obj_file: str,
    source_file: str,
) -> List[str]:
    """
    Build compile command from parsed components.

    All paths are properly handled for cross-platform compatibility.

    Args:
        compiler: Compiler path
        cflags: Compiler flags
        includes: Include directories
        defines: Preprocessor definitions
        obj_file: Output object file
        source_file: Input source file

    Returns:
        Command as list of arguments
    """
    cmd = (
        [compiler]
        + cflags
        + [
            "-c",
            "-ffunction-sections",
            "-fdata-sections",
            "-Wno-error",
        ]
    )

    # Add include paths (only existing directories)
    for inc in includes:
        inc_path = Path(inc)
        if inc_path.is_dir():
            cmd.extend(["-I", str(inc_path)])

    # Add defines
    for d in defines:
        cmd.extend(["-D", d])

    cmd.extend(["-o", obj_file, source_file])
    return cmd


def _generate_linker_script(
    base_addr: int, output_path: str, config: Dict = None
) -> None:
    """
    Generate linker script using template system.

    Args:
        base_addr: Base address for injection code
        output_path: Output file path
        config: Optional configuration dictionary
    """
    if config:
        ld_config = LinkerScriptConfig.from_dict(config)
    else:
        ld_config = LinkerScriptConfig()

    generator = LinkerScriptGenerator(config=ld_config)
    generator.save_to_file(base_addr, output_path)


def _build_link_command(
    compiler: str,
    cflags: List[str],
    ld_file: str,
    elf_file: str,
    obj_file: str,
    main_elf_path: str,
    fpb_funcs: List[str],
) -> List[str]:
    """
    Build link command.

    Args:
        compiler: Compiler path
        cflags: Compiler flags (first 2 used for arch)
        ld_file: Linker script path
        elf_file: Output ELF file
        obj_file: Input object file
        main_elf_path: Main ELF for symbol resolution
        fpb_funcs: FPB inject function names

    Returns:
        Link command as list of arguments
    """
    # Use first 2 cflags (typically arch flags like -mcpu, -mthumb)
    link_cmd = (
        [compiler]
        + cflags[:2]
        + [
            "-nostartfiles",
            "-nostdlib",
            f"-T{ld_file}",
            "-Wl,--gc-sections",
            "-Wl,--allow-multiple-definition",
        ]
    )

    # Add -u flags for FPB inject functions to prevent garbage collection
    for func in set(fpb_funcs):
        if func not in ("if", "while", "for", "switch", "return"):
            link_cmd.append(f"-Wl,-u,{func}")

    # IMPORTANT: obj_file MUST come BEFORE --just-symbols!
    # With --allow-multiple-definition, the linker uses the FIRST definition.
    link_cmd.extend(["-o", elf_file, obj_file])

    if main_elf_path and os.path.exists(main_elf_path):
        link_cmd.append(f"-Wl,--just-symbols={main_elf_path}")

    return link_cmd


def _extract_symbols(
    objcopy: str,
    elf_file: str,
    base_addr: int,
    fpb_funcs: List[str],
    source_content: str,
    env: Dict,
) -> Dict[str, int]:
    """
    Extract symbols from compiled ELF.

    Args:
        objcopy: objcopy tool path
        elf_file: ELF file path
        base_addr: Base address for filtering
        fpb_funcs: Expected FPB function names
        source_content: Source content for debugging
        env: Subprocess environment

    Returns:
        Dictionary of symbol name to address
    """
    nm_cmd = objcopy.replace("objcopy", "nm")
    result = subprocess.run(
        [nm_cmd, "-C", "--defined-only", elf_file],
        capture_output=True,
        text=True,
        env=env,
    )

    symbols = {}
    for line in result.stdout.strip().split("\n"):
        parts = line.split()
        if len(parts) >= 3:
            try:
                addr = int(parts[0], 16)
                sym_type = parts[1]

                # Handle demangled names with spaces
                full_name = " ".join(parts[2:])
                name = full_name.split("(")[0] if "(" in full_name else full_name

                # Only include text section symbols in our address range
                if sym_type.upper() == "T" and addr >= base_addr:
                    symbols[name] = addr
                    logger.debug(f"Including symbol: {name} @ 0x{addr:08X}")
            except (ValueError, IndexError):
                pass

    # Log FPB inject symbols for debugging
    fpb_syms = {k: v for k, v in symbols.items() if k in fpb_funcs}
    if fpb_syms:
        logger.info(f"Found FPB inject symbols: {fpb_syms}")
    elif fpb_funcs:
        logger.warning(
            f"Expected FPB inject functions {fpb_funcs} not found in compiled ELF. "
            f"Total symbols: {len(symbols)}"
        )
        logger.warning(f"All defined text symbols: {list(symbols.keys())}")
    else:
        logger.warning("No FPB_INJECT markers found in source code!")

    return symbols


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

    Args:
        data: Binary data
        base_addr: Base address
        elf_path: Path to main ELF
        toolchain_path: Toolchain path
        verbose: Enable verbose logging

    Returns:
        Fixed binary data
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
