#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
ELF file utilities for FPBInject Web Server.

Provides functions for extracting symbols, disassembly, and decompilation from ELF files.
"""

import logging
import os
import re
import subprocess
from typing import Dict, Optional, Tuple

from utils.toolchain import get_tool_path, get_subprocess_env

logger = logging.getLogger(__name__)


def get_elf_build_time(elf_path: str) -> Optional[str]:
    """Get build time from ELF file.

    Searches for __DATE__ and __TIME__ strings embedded in the binary.

    Returns:
        Build time string in format "Mon DD YYYY HH:MM:SS" or None if not found
    """
    if not elf_path or not os.path.exists(elf_path):
        return None

    try:
        result = subprocess.run(
            ["strings", "-a", elf_path], capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            return None

        date_pattern = (
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{4}"
        )
        time_pattern = r"\d{2}:\d{2}:\d{2}"

        lines = result.stdout.split("\n")

        # Strategy 1: Look for "FPBInject" marker and find date/time nearby
        for i, line in enumerate(lines):
            if "FPBInject" in line and "v1.0" in line:
                window_start = max(0, i - 3)
                window_end = min(len(lines), i + 10)
                window_text = "\n".join(lines[window_start:window_end])

                date_match = re.search(date_pattern, window_text)
                time_match = re.search(time_pattern, window_text)

                if date_match and time_match:
                    return f"{date_match.group(0)} {time_match.group(0)}"

        # Strategy 2: Look for consecutive date and time strings
        for i, line in enumerate(lines):
            date_match = re.match(f"^({date_pattern})$", line.strip())
            if date_match and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                time_match = re.match(f"^({time_pattern})$", next_line)
                if time_match:
                    return f"{date_match.group(1)} {time_match.group(1)}"

        return None
    except Exception as e:
        logger.debug(f"Error getting ELF build time: {e}")
        return None


def get_symbols(elf_path: str, toolchain_path: Optional[str] = None) -> Dict[str, int]:
    """Extract symbols from ELF file.

    Returns a dictionary with both mangled and demangled names pointing to addresses.
    """
    symbols = {}
    try:
        nm_tool = get_tool_path("arm-none-eabi-nm", toolchain_path)
        env = get_subprocess_env(toolchain_path)

        # First get mangled names (without -C)
        result = subprocess.run(
            [nm_tool, elf_path],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                try:
                    addr = int(parts[0], 16)
                    name = parts[2]
                    symbols[name] = addr
                except ValueError:
                    pass

        # Also get demangled names (-C) for easier lookup
        result = subprocess.run(
            [nm_tool, "-C", elf_path],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                try:
                    addr = int(parts[0], 16)
                    full_name = " ".join(parts[2:])
                    if "(" in full_name:
                        short_name = full_name.split("(")[0]
                        symbols[short_name] = addr
                    symbols[full_name] = addr
                except ValueError:
                    pass
    except Exception as e:
        logger.error(f"Error reading symbols: {e}")
    return symbols


def disassemble_function(
    elf_path: str, func_name: str, toolchain_path: Optional[str] = None
) -> Tuple[bool, str]:
    """Disassemble a specific function from ELF file."""
    try:
        objdump_tool = get_tool_path("arm-none-eabi-objdump", toolchain_path)
        env = get_subprocess_env(toolchain_path)

        # Use objdump to disassemble only the specified function
        result = subprocess.run(
            [objdump_tool, "-d", "-C", f"--disassemble={func_name}", elf_path],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        output = result.stdout

        # If no output, try without demangling
        if not output or f"<{func_name}>" not in output:
            result = subprocess.run(
                [objdump_tool, "-d", f"--disassemble={func_name}", elf_path],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            output = result.stdout

        if not output.strip():
            return False, f"Function '{func_name}' not found in ELF"

        # Clean up the output - extract just the function disassembly
        lines = output.splitlines()
        in_function = False
        disasm_lines = []
        empty_line_count = 0

        for line in lines:
            if f"<{func_name}" in line and ">:" in line:
                stripped = line.strip()
                if stripped and stripped[0].isalnum():
                    in_function = True
                    disasm_lines.append(line)
                    empty_line_count = 0
                    continue

            if in_function:
                if not line.strip():
                    empty_line_count += 1
                    if empty_line_count >= 2:
                        break
                    continue

                empty_line_count = 0

                stripped = line.strip()
                if (
                    stripped
                    and stripped[0].isalnum()
                    and ":" in stripped
                    and "<" in stripped
                    and ">:" in stripped
                ):
                    break
                else:
                    disasm_lines.append(line)

        if not disasm_lines:
            return False, f"Could not extract disassembly for '{func_name}'"

        filtered_lines = []
        for line in disasm_lines:
            if line.strip().startswith("Disassembly of section"):
                break
            filtered_lines.append(line)

        return True, "\n".join(filtered_lines)

    except subprocess.TimeoutExpired:
        return False, "Disassembly timed out"
    except FileNotFoundError:
        return False, "objdump tool not found - check toolchain path"
    except Exception as e:
        logger.error(f"Error disassembling function: {e}")
        return False, str(e)


def decompile_function(elf_path: str, func_name: str) -> Tuple[bool, str]:
    """Decompile a specific function from ELF file using angr."""
    try:
        import angr
        from angr.analyses.decompiler.structured_codegen import (
            DummyStructuredCodeGenerator,
        )
    except ImportError:
        return False, "ANGR_NOT_INSTALLED"

    import logging as angr_logging

    for name in ["angr", "cle", "pyvex", "angr.analyses.calling_convention"]:
        angr_logging.getLogger(name).setLevel(angr_logging.CRITICAL)

    try:
        proj = angr.Project(elf_path, auto_load_libs=False)

        func_symbol = proj.loader.find_symbol(func_name)
        if not func_symbol:
            func_symbol = proj.loader.find_symbol(f"_{func_name}")

        if not func_symbol:
            return False, f"Function '{func_name}' not found in ELF"

        cfg = proj.analyses.CFGFast(normalize=True, data_references=True)

        func_addr = func_symbol.rebased_addr
        func = cfg.kb.functions.get(func_addr)

        if not func:
            for f in cfg.kb.functions.values():
                if f.name == func_name or f.name == f"_{func_name}":
                    func = f
                    break

        if not func:
            return False, f"Could not analyze function '{func_name}'"

        try:
            dec = proj.analyses.Decompiler(func, cfg=cfg)

            if dec.codegen is None or isinstance(
                dec.codegen, DummyStructuredCodeGenerator
            ):
                return False, f"Could not decompile '{func_name}' - analysis failed"

            decompiled = dec.codegen.text

            if not decompiled or not decompiled.strip():
                return False, f"Decompilation produced empty output for '{func_name}'"

            header = f"// Decompiled from: {os.path.basename(elf_path)}\n"
            header += f"// Function: {func_name} @ 0x{func_addr:08x}\n"
            header += "// Note: This is machine-generated pseudocode\n\n"

            return True, header + decompiled

        except Exception as e:
            logger.error(f"Decompilation analysis failed: {e}")
            return False, f"Decompilation failed: {str(e)}"

    except Exception as e:
        logger.error(f"Error decompiling function: {e}")
        return False, str(e)


def get_signature(
    elf_path: str, func_name: str, toolchain_path: Optional[str] = None
) -> Optional[str]:
    """Get function signature from ELF file using DWARF debug info."""
    try:
        nm_tool = get_tool_path("arm-none-eabi-nm", toolchain_path)
        env = get_subprocess_env(toolchain_path)

        result = subprocess.run(
            [nm_tool, "-C", elf_path],
            capture_output=True,
            text=True,
            env=env,
        )

        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                name = " ".join(parts[2:])
                if func_name in name:
                    if "(" in name:
                        return name
                    return name

        readelf_tool = get_tool_path("arm-none-eabi-readelf", toolchain_path)
        result = subprocess.run(
            [readelf_tool, "--debug-dump=info", elf_path],
            capture_output=True,
            text=True,
            env=env,
        )

        in_function = False
        for line in result.stdout.splitlines():
            if "DW_AT_name" in line and func_name in line:
                in_function = True
            elif in_function and "DW_AT_type" in line:
                return f"{func_name}()"

        return func_name

    except Exception as e:
        logger.debug(f"Could not get signature for {func_name}: {e}")
        return func_name
