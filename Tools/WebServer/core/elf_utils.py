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
import time
from typing import Dict, List, Optional, Tuple

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

from utils.toolchain import get_tool_path, get_subprocess_env

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Symbol type classification helpers
# ---------------------------------------------------------------------------


def _classify_symbol(sym_type: str, section_name: str) -> str:
    """Classify a symbol as 'function', 'variable', or 'const'.

    Args:
        sym_type: ELF symbol type string (STT_FUNC, STT_OBJECT, etc.)
        section_name: Name of the section the symbol belongs to

    Returns:
        One of 'function', 'variable', 'const', or 'other'
    """
    if sym_type == "STT_FUNC":
        return "function"
    if sym_type == "STT_OBJECT":
        if section_name in (".rodata", ".rodata.str1.1", ".rodata.str1.4"):
            return "const"
        if section_name in (".data", ".bss"):
            return "variable"
        # Fallback: treat unknown sections with STT_OBJECT as variable
        if section_name.startswith(".rodata"):
            return "const"
        return "variable"
    return "other"


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


def get_symbols(elf_path: str, toolchain_path: Optional[str] = None) -> Dict[str, dict]:
    """Extract symbols from ELF file using pyelftools.

    Returns a dictionary mapping symbol names to info dicts:
        {"name": {"addr": int, "size": int, "type": str, "section": str}}

    The 'type' field is one of: 'function', 'variable', 'const', 'other'.
    Both mangled and demangled names are included when a toolchain is available.
    """
    symbols: Dict[str, dict] = {}

    if not elf_path or not os.path.exists(elf_path):
        return symbols

    elf_size_mb = os.path.getsize(elf_path) / (1024 * 1024)
    logger.info(f"Loading symbols from ELF ({elf_size_mb:.1f} MB): {elf_path}")
    t_start = time.time()

    try:
        with open(elf_path, "rb") as f:
            elf = ELFFile(f)
            symtab = elf.get_section_by_name(".symtab")
            if not isinstance(symtab, SymbolTableSection):
                logger.warning("No .symtab section found in ELF")
                return symbols

            t_parse = time.time()
            logger.info(f"ELF header parsed in {t_parse - t_start:.2f}s")

            sym_count = 0
            for sym in symtab.iter_symbols():
                sym_count += 1
                if not sym.name:
                    continue
                # Skip undefined and absolute symbols
                shndx = sym["st_shndx"]
                if shndx in ("SHN_UNDEF", "SHN_ABS"):
                    continue
                # Skip zero-size symbols (labels, etc.)
                if sym["st_size"] == 0:
                    continue

                sym_type = sym["st_info"]["type"]
                # Only keep functions and objects
                if sym_type not in ("STT_FUNC", "STT_OBJECT"):
                    continue

                section_name = ""
                try:
                    if isinstance(shndx, int):
                        section = elf.get_section(shndx)
                        section_name = section.name if section else ""
                except Exception:
                    pass

                info = {
                    "addr": sym["st_value"],
                    "size": sym["st_size"],
                    "type": _classify_symbol(sym_type, section_name),
                    "section": section_name,
                }
                symbols[sym.name] = info

    except Exception as e:
        logger.error(f"Error reading symbols with pyelftools: {e}")
        return symbols

    t_symtab = time.time()
    logger.info(
        f"Symbol table scanned: {len(symbols)} symbols extracted "
        f"from {sym_count} entries in {t_symtab - t_start:.2f}s"
    )

    # Also add demangled names via nm -C for C++ support
    try:
        nm_tool = get_tool_path("arm-none-eabi-nm", toolchain_path)
        env = get_subprocess_env(toolchain_path)

        t_nm_start = time.time()
        result = subprocess.run(
            [nm_tool, "-C", "--defined-only", elf_path],
            capture_output=True,
            text=True,
            env=env,
        )
        t_nm_run = time.time()
        logger.info(
            f"nm -C subprocess finished in {t_nm_run - t_nm_start:.2f}s "
            f"({len(result.stdout)} bytes output)"
        )

        # Build addr→info reverse index for O(1) lookup
        addr_index = {}
        for info in symbols.values():
            addr = info["addr"]
            if addr not in addr_index:
                addr_index[addr] = info

        demangle_count = 0
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                try:
                    addr = int(parts[0], 16)
                    full_name = " ".join(parts[2:])
                    mangled = parts[2] if len(parts) == 3 else None

                    # Find the mangled symbol info to copy
                    base_info = None
                    if mangled and mangled in symbols:
                        base_info = symbols[mangled]
                    else:
                        # O(1) address lookup via reverse index
                        base_info = addr_index.get(addr)

                    if base_info and full_name not in symbols:
                        symbols[full_name] = dict(base_info)
                        demangle_count += 1
                        # Also add short name for C++ functions
                        if "(" in full_name:
                            short_name = full_name.split("(")[0]
                            if short_name not in symbols:
                                symbols[short_name] = dict(base_info)
                                demangle_count += 1
                except ValueError:
                    pass

        logger.info(
            f"Demangling added {demangle_count} symbols "
            f"in {time.time() - t_nm_start:.2f}s"
        )
    except Exception as e:
        logger.debug(f"Demangling pass skipped: {e}")

    t_total = time.time() - t_start
    logger.info(f"Symbol loading complete: {len(symbols)} symbols in {t_total:.2f}s")
    return symbols


def search_symbols(
    elf_path: str,
    query: str,
    limit: int = 100,
    toolchain_path: Optional[str] = None,
) -> Tuple[List[dict], int]:
    """Search symbols in ELF file without loading all into memory.

    Streams through the symbol table and returns only matching entries.

    Args:
        elf_path: Path to ELF file
        query: Search query (name substring or 0x address)
        limit: Maximum number of results to return
        toolchain_path: Optional toolchain path for demangling

    Returns:
        Tuple of (matched symbol list, total symbol count)
    """
    if not elf_path or not os.path.exists(elf_path):
        return [], 0

    t_start = time.time()
    logger.info(f"Searching symbols: query='{query}', limit={limit}")

    query_lower = query.lower().strip()
    is_addr_search = query_lower.startswith("0x") or (
        len(query_lower) >= 4 and all(c in "0123456789abcdef" for c in query_lower)
    )
    addr_str = query_lower[2:] if query_lower.startswith("0x") else query_lower

    results = []
    total = 0

    try:
        with open(elf_path, "rb") as f:
            elf = ELFFile(f)
            symtab = elf.get_section_by_name(".symtab")
            if not isinstance(symtab, SymbolTableSection):
                return [], 0

            # Cache section names by index to avoid repeated lookups
            section_cache = {}

            for sym in symtab.iter_symbols():
                if not sym.name:
                    continue
                shndx = sym["st_shndx"]
                if shndx in ("SHN_UNDEF", "SHN_ABS"):
                    continue
                if sym["st_size"] == 0:
                    continue
                sym_type = sym["st_info"]["type"]
                if sym_type not in ("STT_FUNC", "STT_OBJECT"):
                    continue

                total += 1

                # Check match
                if is_addr_search:
                    if addr_str not in f"{sym['st_value']:08x}":
                        continue
                else:
                    if query_lower not in sym.name.lower():
                        continue

                # Resolve section name (cached)
                if isinstance(shndx, int):
                    if shndx not in section_cache:
                        try:
                            sec = elf.get_section(shndx)
                            section_cache[shndx] = sec.name if sec else ""
                        except Exception:
                            section_cache[shndx] = ""
                    section_name = section_cache[shndx]
                else:
                    section_name = ""

                results.append(
                    {
                        "name": sym.name,
                        "addr": f"0x{sym['st_value']:08X}",
                        "size": sym["st_size"],
                        "type": _classify_symbol(sym_type, section_name),
                        "section": section_name,
                    }
                )

    except Exception as e:
        logger.error(f"Error searching symbols: {e}")
        return [], 0

    # Sort by name and apply limit
    results.sort(key=lambda x: x["name"])
    elapsed = time.time() - t_start
    logger.info(
        f"Symbol search done: {len(results[:limit])} matches / {total} total "
        f"in {elapsed:.2f}s"
    )
    return results[:limit], total


def lookup_symbol(elf_path: str, sym_name: str) -> Optional[dict]:
    """Look up a single symbol by exact name without loading all symbols.

    Returns:
        Symbol info dict or None if not found.
    """
    if not elf_path or not os.path.exists(elf_path):
        return None

    t_start = time.time()

    try:
        with open(elf_path, "rb") as f:
            elf = ELFFile(f)
            symtab = elf.get_section_by_name(".symtab")
            if not isinstance(symtab, SymbolTableSection):
                return None

            for sym in symtab.iter_symbols():
                if sym.name != sym_name:
                    continue
                if sym["st_size"] == 0:
                    continue
                shndx = sym["st_shndx"]
                if shndx in ("SHN_UNDEF", "SHN_ABS"):
                    continue
                sym_type = sym["st_info"]["type"]
                if sym_type not in ("STT_FUNC", "STT_OBJECT"):
                    continue

                section_name = ""
                try:
                    if isinstance(shndx, int):
                        section = elf.get_section(shndx)
                        section_name = section.name if section else ""
                except Exception:
                    pass

                elapsed = time.time() - t_start
                logger.info(f"Symbol lookup '{sym_name}' found in {elapsed:.2f}s")
                return {
                    "addr": sym["st_value"],
                    "size": sym["st_size"],
                    "type": _classify_symbol(sym_type, section_name),
                    "section": section_name,
                }
    except Exception as e:
        logger.error(f"Error looking up symbol '{sym_name}': {e}")

    elapsed = time.time() - t_start
    logger.info(f"Symbol lookup '{sym_name}' not found ({elapsed:.2f}s)")
    return None


def read_symbol_value(elf_path: str, sym_name: str) -> Optional[bytes]:
    """Read the raw bytes of a symbol's value from the ELF section data.

    Returns None for .bss symbols (no initial value) or if symbol not found.
    """
    if not elf_path or not os.path.exists(elf_path):
        return None

    t_start = time.time()
    try:
        with open(elf_path, "rb") as f:
            elf = ELFFile(f)
            symtab = elf.get_section_by_name(".symtab")
            if not isinstance(symtab, SymbolTableSection):
                return None

            for sym in symtab.iter_symbols():
                if sym.name == sym_name and sym["st_size"] > 0:
                    shndx = sym["st_shndx"]
                    if not isinstance(shndx, int):
                        continue
                    section = elf.get_section(shndx)
                    if not section:
                        continue
                    # .bss has no data in ELF
                    if section.name.startswith(".bss"):
                        return None
                    if section["sh_type"] == "SHT_NOBITS":
                        return None
                    offset = sym["st_value"] - section["sh_addr"]
                    data = section.data()
                    elapsed = time.time() - t_start
                    logger.info(f"read_symbol_value '{sym_name}': {elapsed:.2f}s")
                    return data[offset : offset + sym["st_size"]]
    except Exception as e:
        logger.error(f"Error reading symbol value: {e}")

    elapsed = time.time() - t_start
    if elapsed > 1.0:
        logger.warning(f"read_symbol_value '{sym_name}' not found ({elapsed:.2f}s)")
    return None


# ---------------------------------------------------------------------------
# DWARF struct layout parsing
# ---------------------------------------------------------------------------


def _resolve_type_die(die, max_depth=20):
    """Follow DW_AT_type references to reach the underlying type DIE.

    Traverses through typedef, const, volatile, pointer qualifiers.
    Returns the terminal type DIE (e.g. DW_TAG_structure_type, DW_TAG_base_type).
    """
    visited = set()
    current = die
    for _ in range(max_depth):
        if current is None or current.offset in visited:
            return current
        visited.add(current.offset)

        type_attr = current.attributes.get("DW_AT_type")
        if type_attr is None:
            return current

        # Tags that are just qualifiers — keep following
        if current.tag in (
            "DW_TAG_typedef",
            "DW_TAG_const_type",
            "DW_TAG_volatile_type",
            "DW_TAG_restrict_type",
        ):
            ref_offset = type_attr.value
            try:
                current = current.cu.get_DIE_from_refaddr(
                    ref_offset + current.cu.cu_offset
                    if type_attr.form.startswith("DW_FORM_ref")
                    and not type_attr.form == "DW_FORM_ref_addr"
                    else ref_offset
                )
            except Exception:
                return current
        else:
            return current
    return current


def _get_type_die_from_attr(die):
    """Get the type DIE referenced by a DIE's DW_AT_type attribute."""
    type_attr = die.attributes.get("DW_AT_type")
    if type_attr is None:
        return None
    try:
        ref_offset = type_attr.value
        if (
            type_attr.form.startswith("DW_FORM_ref")
            and type_attr.form != "DW_FORM_ref_addr"
        ):
            ref_offset += die.cu.cu_offset
        return die.cu.get_DIE_from_refaddr(ref_offset)
    except Exception:
        return None


def _get_type_name(die, max_depth=20):
    """Get a human-readable type name from a DWARF type DIE."""
    if die is None or max_depth <= 0:
        return "unknown"

    tag = die.tag
    name_attr = die.attributes.get("DW_AT_name")

    if tag in (
        "DW_TAG_base_type",
        "DW_TAG_structure_type",
        "DW_TAG_union_type",
        "DW_TAG_enumeration_type",
    ):
        if name_attr:
            return (
                name_attr.value.decode()
                if isinstance(name_attr.value, bytes)
                else str(name_attr.value)
            )
        return f"<anon {tag.split('_')[-1]}>"

    if tag == "DW_TAG_typedef":
        if name_attr:
            return (
                name_attr.value.decode()
                if isinstance(name_attr.value, bytes)
                else str(name_attr.value)
            )
        child = _get_type_die_from_attr(die)
        return _get_type_name(child, max_depth - 1)

    if tag in ("DW_TAG_const_type", "DW_TAG_volatile_type", "DW_TAG_restrict_type"):
        qualifier = tag.replace("DW_TAG_", "").replace("_type", "")
        child = _get_type_die_from_attr(die)
        return f"{qualifier} {_get_type_name(child, max_depth - 1)}"

    if tag == "DW_TAG_pointer_type":
        child = _get_type_die_from_attr(die)
        if child is None:
            return "void *"
        return f"{_get_type_name(child, max_depth - 1)} *"

    if tag == "DW_TAG_array_type":
        child = _get_type_die_from_attr(die)
        base_name = _get_type_name(child, max_depth - 1) if child else "unknown"
        # Get array dimensions
        for sub in die.iter_children():
            if sub.tag == "DW_TAG_subrange_type":
                count_attr = sub.attributes.get("DW_AT_count") or sub.attributes.get(
                    "DW_AT_upper_bound"
                )
                if count_attr:
                    count = count_attr.value
                    if sub.attributes.get("DW_AT_upper_bound"):
                        count += 1
                    return f"{base_name}[{count}]"
        return f"{base_name}[]"

    if name_attr:
        return (
            name_attr.value.decode()
            if isinstance(name_attr.value, bytes)
            else str(name_attr.value)
        )
    return "unknown"


def _get_type_size(die):
    """Get the byte size of a type DIE."""
    size_attr = die.attributes.get("DW_AT_byte_size")
    if size_attr:
        return size_attr.value

    # Follow type reference for typedef/qualifier
    child = _get_type_die_from_attr(die)
    if child and child.offset != die.offset:
        return _get_type_size(child)
    return 0


def _parse_struct_members(struct_die) -> List[dict]:
    """Parse members of a DW_TAG_structure_type DIE."""
    members = []
    for child in struct_die.iter_children():
        if child.tag != "DW_TAG_member":
            continue

        name_attr = child.attributes.get("DW_AT_name")
        name = ""
        if name_attr:
            name = (
                name_attr.value.decode()
                if isinstance(name_attr.value, bytes)
                else str(name_attr.value)
            )

        offset = 0
        loc_attr = child.attributes.get("DW_AT_data_member_location")
        if loc_attr is not None:
            if isinstance(loc_attr.value, int):
                offset = loc_attr.value
            elif isinstance(loc_attr.value, list) and len(loc_attr.value) > 0:
                # DWARF expression — try to extract constant
                offset = loc_attr.value[0] if isinstance(loc_attr.value[0], int) else 0

        # Get member type info
        member_type_die = _get_type_die_from_attr(child)
        resolved = _resolve_type_die(member_type_die) if member_type_die else None
        type_name = _get_type_name(member_type_die) if member_type_die else "unknown"
        size = _get_type_size(resolved) if resolved else 0

        members.append(
            {
                "name": name,
                "offset": offset,
                "size": size,
                "type_name": type_name,
            }
        )

    return members


def get_struct_layout(elf_path: str, sym_name: str) -> Optional[List[dict]]:
    """Get struct member layout for a symbol via DWARF debug info.

    Returns a list of member dicts: [{"name", "offset", "size", "type_name"}, ...]
    Returns None if the symbol is not a struct, or if no DWARF info is available.
    """
    if not elf_path or not os.path.exists(elf_path):
        return None

    t_start = time.time()
    try:
        with open(elf_path, "rb") as f:
            elf = ELFFile(f)
            if not elf.has_dwarf_info():
                return None

            t_open = time.time()
            dwarf = elf.get_dwarf_info()
            t_dwarf = time.time()
            if t_dwarf - t_open > 1.0:
                logger.info(
                    f"get_struct_layout: DWARF info loaded in {t_dwarf - t_open:.2f}s"
                )

            for cu in dwarf.iter_CUs():
                for die in cu.iter_DIEs():
                    if die.tag != "DW_TAG_variable":
                        continue
                    name_attr = die.attributes.get("DW_AT_name")
                    if not name_attr:
                        continue
                    die_name = (
                        name_attr.value.decode()
                        if isinstance(name_attr.value, bytes)
                        else str(name_attr.value)
                    )
                    if die_name != sym_name:
                        continue

                    # Found the variable — resolve its type
                    type_die = _get_type_die_from_attr(die)
                    resolved = _resolve_type_die(type_die) if type_die else None
                    if resolved and resolved.tag == "DW_TAG_structure_type":
                        return _parse_struct_members(resolved)
                    # Not a struct
                    return None
    except Exception as e:
        logger.debug(f"DWARF struct layout parse failed for {sym_name}: {e}")

    elapsed = time.time() - t_start
    if elapsed > 1.0:
        logger.warning(
            f"get_struct_layout '{sym_name}': {elapsed:.2f}s (no struct found)"
        )
    return None


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
