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
            if "FPBInject" in line and re.search(r"v\d+\.\d+", line):
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


# Global cache for Ghidra project to avoid re-analyzing the same ELF file
_ghidra_project_cache = {
    "elf_path": None,
    "elf_mtime": None,
    "project_dir": None,
    "project_name": "fpb_decompile",
}


def _get_cached_ghidra_project(
    elf_path: str, ghidra_path: str
) -> Tuple[str, str, bool]:
    """Get or create a cached Ghidra project for the ELF file.

    Returns:
        Tuple of (project_dir, project_name, is_new_project)
    """
    import tempfile
    import shutil

    cache = _ghidra_project_cache
    elf_mtime = os.path.getmtime(elf_path)

    # Check if we can reuse the cached project
    if (
        cache["elf_path"] == elf_path
        and cache["elf_mtime"] == elf_mtime
        and cache["project_dir"]
        and os.path.exists(cache["project_dir"])
    ):
        return cache["project_dir"], cache["project_name"], False

    # Clean up old project if exists
    if cache["project_dir"] and os.path.exists(cache["project_dir"]):
        try:
            shutil.rmtree(cache["project_dir"], ignore_errors=True)
        except Exception:
            pass

    # Create new project directory
    project_dir = tempfile.mkdtemp(prefix="ghidra_project_")
    cache["elf_path"] = elf_path
    cache["elf_mtime"] = elf_mtime
    cache["project_dir"] = project_dir

    return project_dir, cache["project_name"], True


def clear_ghidra_cache():
    """Clear the Ghidra project cache."""
    import shutil

    cache = _ghidra_project_cache
    if cache["project_dir"] and os.path.exists(cache["project_dir"]):
        try:
            shutil.rmtree(cache["project_dir"], ignore_errors=True)
        except Exception:
            pass
    cache["elf_path"] = None
    cache["elf_mtime"] = None
    cache["project_dir"] = None


def decompile_function(
    elf_path: str, func_name: str, ghidra_path: str = None
) -> Tuple[bool, str]:
    """Decompile a specific function from ELF file using Ghidra.

    Uses a cached Ghidra project to avoid re-analyzing the same ELF file,
    which significantly speeds up subsequent decompilation requests.

    Args:
        elf_path: Path to the ELF file
        func_name: Name of the function to decompile
        ghidra_path: Path to Ghidra installation directory (containing analyzeHeadless)

    Returns:
        Tuple of (success, decompiled_code_or_error_message)
    """
    import tempfile
    import shutil

    # Find analyzeHeadless script
    analyze_headless = None
    if ghidra_path:
        # Check common locations within Ghidra installation
        candidates = [
            os.path.join(ghidra_path, "support", "analyzeHeadless"),
            os.path.join(ghidra_path, "analyzeHeadless"),
            os.path.join(ghidra_path, "support", "analyzeHeadless.bat"),
            os.path.join(ghidra_path, "analyzeHeadless.bat"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                analyze_headless = candidate
                break

    if not analyze_headless:
        # Try to find in PATH
        analyze_headless = shutil.which("analyzeHeadless")

    if not analyze_headless:
        return False, "GHIDRA_NOT_CONFIGURED"

    if not os.path.exists(elf_path):
        return False, f"ELF file not found: {elf_path}"

    # Get or create cached project
    project_dir, project_name, is_new_project = _get_cached_ghidra_project(
        elf_path, ghidra_path
    )

    # Create temporary directory for script output
    temp_dir = tempfile.mkdtemp(prefix="ghidra_decompile_")
    output_file = os.path.join(temp_dir, "decompiled.c")

    # Create a simple Ghidra script to decompile the function
    script_content = f"""
# Ghidra decompile script for FPBInject
# @category FPBInject
# @runtime Jython

from ghidra.app.decompiler import DecompInterface, DecompileOptions
from ghidra.util.task import ConsoleTaskMonitor
from ghidra.program.model.symbol import SourceType

func_name = "{func_name}"
output_path = "{output_file}"

# Initialize decompiler with options to use debug info
decomp = DecompInterface()
options = DecompileOptions()
# Enable using parameter names from debug info (DWARF)
options.setEliminateUnreachable(True)
decomp.setOptions(options)
decomp.openProgram(currentProgram)

# Find the function by symbol name first (faster)
func = None
symbol_table = currentProgram.getSymbolTable()
func_manager = currentProgram.getFunctionManager()

# Try to find symbol directly (much faster than iterating all functions)
symbols = symbol_table.getSymbols(func_name)
for sym in symbols:
    if sym.getSymbolType().toString() == "Function":
        func = func_manager.getFunctionAt(sym.getAddress())
        if func:
            break

# Try with underscore prefix (common in C)
if func is None:
    symbols = symbol_table.getSymbols("_" + func_name)
    for sym in symbols:
        if sym.getSymbolType().toString() == "Function":
            func = func_manager.getFunctionAt(sym.getAddress())
            if func:
                break

# Fallback: iterate functions (slower, but handles edge cases)
if func is None:
    for f in func_manager.getFunctions(True):
        name = f.getName()
        if name == func_name or name == "_" + func_name:
            func = f
            break

# Last resort: partial match
if func is None:
    for f in func_manager.getFunctions(True):
        if func_name in f.getName():
            func = f
            break

if func is None:
    with open(output_path, "w") as f:
        f.write("ERROR: Function '{{}}' not found".format(func_name))
else:
    # Try to apply parameter names from debug info before decompiling
    try:
        params = func.getParameters()
        high_func = None

        # First decompile to get high function for parameter mapping
        monitor = ConsoleTaskMonitor()
        results = decomp.decompileFunction(func, 60, monitor)

        if results.decompileCompleted():
            high_func = results.getHighFunction()

            if high_func:
                # Get local symbol map which contains parameter info from debug
                local_symbols = high_func.getLocalSymbolMap()
                if local_symbols:
                    # Map debug parameter names to decompiler parameters
                    for i, param in enumerate(params):
                        param_name = param.getName()
                        # If parameter has a real name (not param_N), it's from debug info
                        if param_name and not param_name.startswith("param_"):
                            # Parameter already has debug name, good
                            pass
                        else:
                            # Try to find corresponding high variable
                            for sym in local_symbols.getSymbols():
                                if sym.isParameter():
                                    slot = sym.getStorage().getFirstVarnode()
                                    if slot and i < len(params):
                                        # Check if this is the i-th parameter
                                        debug_name = sym.getName()
                                        if debug_name and not debug_name.startswith("param_"):
                                            try:
                                                param.setName(debug_name, SourceType.IMPORTED)
                                            except:
                                                pass

                # Re-decompile with updated parameter names
                results = decomp.decompileFunction(func, 60, monitor)
    except Exception as e:
        # If parameter name extraction fails, continue with default names
        pass

    # Get final decompiled code
    if results and results.decompileCompleted():
        decompiled = results.getDecompiledFunction()
        if decompiled:
            c_code = decompiled.getC()
            with open(output_path, "w") as f:
                f.write(c_code)
        else:
            with open(output_path, "w") as f:
                f.write("ERROR: Decompilation produced no output")
    else:
        with open(output_path, "w") as f:
            f.write("ERROR: Decompilation failed - {{}}".format(results.getErrorMessage() if results else "unknown error"))

decomp.dispose()
"""

    script_file = os.path.join(temp_dir, "decompile_func.py")
    with open(script_file, "w") as f:
        f.write(script_content)

    try:
        if is_new_project:
            # First time: import ELF and run analysis, then run script
            # Use -postScript so script runs after analysis
            cmd = [
                analyze_headless,
                project_dir,
                project_name,
                "-import",
                elf_path,
                "-postScript",
                script_file,
                "-scriptPath",
                temp_dir,
            ]
            timeout = 180  # 3 minutes for initial analysis
        else:
            # Subsequent calls: just process the existing project with script
            cmd = [
                analyze_headless,
                project_dir,
                project_name,
                "-process",
                os.path.basename(elf_path),
                "-noanalysis",
                "-postScript",
                script_file,
                "-scriptPath",
                temp_dir,
            ]
            timeout = 30  # 30 seconds for cached project

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Check if output file was created
        if os.path.exists(output_file):
            with open(output_file, "r") as f:
                content = f.read()

            if content.startswith("ERROR:"):
                error_msg = content[6:].strip()
                return False, error_msg

            # Add header
            header = f"// Decompiled from: {os.path.basename(elf_path)}\n"
            header += f"// Function: {func_name}\n"
            header += "// Decompiler: Ghidra\n"
            header += "// Note: This is machine-generated pseudocode\n\n"

            return True, header + content
        else:
            # Check stderr for errors
            if result.returncode != 0:
                logger.error(f"Ghidra analysis failed: {result.stderr}")
                # If cached project failed, clear cache and suggest retry
                if not is_new_project:
                    clear_ghidra_cache()
                return False, f"Ghidra analysis failed: {result.stderr[:200]}"

            return False, "Decompilation produced no output"

    except subprocess.TimeoutExpired:
        if is_new_project:
            return False, "Decompilation timed out (>180s) - ELF file may be too large"
        else:
            # Clear cache on timeout for cached project
            clear_ghidra_cache()
            return False, "Decompilation timed out (>30s)"
    except FileNotFoundError:
        return False, "Ghidra analyzeHeadless not found"
    except Exception as e:
        logger.error(f"Error decompiling function: {e}")
        return False, str(e)
    finally:
        # Cleanup temporary script directory (but keep project cache)
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


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
