#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
GDB Session manager for FPBInject Web Server.

Manages an arm-none-eabi-gdb subprocess connected to the GDB RSP Bridge,
providing high-level APIs for symbol lookup, type resolution, and memory access.

This replaces pyelftools for ELF/DWARF parsing with GDB's native capabilities,
achieving ~100-300x speedup for symbol and type queries.
"""

import logging
import os
import re
import subprocess
import threading
import time
from typing import Dict, List, Optional, Tuple

from utils.toolchain import get_tool_path, get_subprocess_env

logger = logging.getLogger(__name__)

# GDB candidates in priority order
_GDB_CANDIDATES = [
    "arm-none-eabi-gdb",  # Toolchain-specific (preferred)
    "gdb-multiarch",  # System multiarch fallback
]

# Timeout for individual GDB commands (seconds)
GDB_CMD_TIMEOUT = 10.0

# Timeout for GDB startup + ELF loading (seconds)
GDB_STARTUP_TIMEOUT = 30.0


class GDBSession:
    """Manages a persistent arm-none-eabi-gdb subprocess.

    The GDB process loads the ELF file once and builds internal indexes.
    Subsequent queries (symbol lookup, ptype, etc.) are near-instant.

    Usage:
        session = GDBSession(elf_path, toolchain_path)
        session.start(rsp_port=3333)  # Connect to RSP bridge
        result = session.execute("ptype my_struct_var")
        session.stop()
    """

    def __init__(self, elf_path: str, toolchain_path: Optional[str] = None):
        self._elf_path = elf_path
        self._toolchain_path = toolchain_path
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._alive = False
        self._rsp_port: Optional[int] = None

    @property
    def is_alive(self) -> bool:
        """Check if GDB process is running."""
        if not self._alive or not self._proc:
            return False
        return self._proc.poll() is None

    @property
    def elf_path(self) -> str:
        return self._elf_path

    def start(self, rsp_port: int) -> bool:
        """Launch GDB, load ELF, and connect to RSP bridge.

        Args:
            rsp_port: TCP port of the GDB RSP bridge

        Returns:
            True if GDB started and connected successfully
        """
        if self.is_alive:
            logger.warning("GDB session already running")
            return True

        self._rsp_port = rsp_port
        gdb_path, is_multiarch = self._find_gdb()
        env = get_subprocess_env(self._toolchain_path)

        if not gdb_path:
            logger.error(
                "No usable GDB found (tried arm-none-eabi-gdb and gdb-multiarch)"
            )
            return False

        if not os.path.exists(self._elf_path):
            logger.error(f"ELF file not found: {self._elf_path}")
            return False

        t_start = time.time()
        logger.info(
            f"Starting GDB session: {gdb_path}{' (multiarch)' if is_multiarch else ''}"
        )
        logger.info(f"  ELF: {self._elf_path}")
        logger.info(f"  RSP port: {rsp_port}")

        try:
            # Launch GDB in MI mode for structured output
            # --nx: don't read .gdbinit
            # -q: quiet
            self._proc = subprocess.Popen(
                [
                    gdb_path,
                    "--interpreter=mi3",
                    "--nx",
                    "-q",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                bufsize=0,
            )

            # Wait for GDB prompt
            self._read_until_prompt(timeout=5.0)

            # For gdb-multiarch: set ARM architecture before loading ELF
            if is_multiarch:
                logger.info("Setting ARM architecture for gdb-multiarch...")
                self._execute_mi("set architecture arm", timeout=5.0)

            # Load ELF file
            logger.info("Loading ELF file into GDB...")
            resp = self._execute_mi(
                f"file {self._elf_path}", timeout=GDB_STARTUP_TIMEOUT
            )
            if resp is None:
                self.stop()
                return False

            t_elf = time.time()
            logger.info(f"GDB loaded ELF in {t_elf - t_start:.2f}s")

            # Connect to RSP bridge
            logger.info(f"Connecting to RSP bridge on port {rsp_port}...")
            resp = self._execute_mi(f"target remote 127.0.0.1:{rsp_port}", timeout=10.0)
            if resp is None:
                logger.error("Failed to connect GDB to RSP bridge")
                self.stop()
                return False

            self._alive = True
            elapsed = time.time() - t_start
            logger.info(f"GDB session ready in {elapsed:.2f}s")
            return True

        except FileNotFoundError:
            logger.error(f"GDB executable not found: {gdb_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to start GDB session: {e}")
            self.stop()
            return False

    def _find_gdb(self):
        """Find a usable GDB executable.

        Tries arm-none-eabi-gdb from toolchain first, then gdb-multiarch.

        Returns:
            (gdb_path, is_multiarch) tuple. gdb_path is None if not found.
        """
        import shutil

        for candidate in _GDB_CANDIDATES:
            # Try toolchain path first
            path = get_tool_path(candidate, self._toolchain_path)
            if os.path.isfile(path):
                # Verify it actually runs
                try:
                    result = subprocess.run(
                        [path, "--version"],
                        capture_output=True,
                        timeout=5.0,
                    )
                    if result.returncode == 0:
                        is_multiarch = "multiarch" in candidate
                        return path, is_multiarch
                except Exception:
                    logger.debug(f"GDB candidate failed: {path}")
                    continue

            # Try system PATH
            sys_path = shutil.which(candidate)
            if sys_path:
                try:
                    result = subprocess.run(
                        [sys_path, "--version"],
                        capture_output=True,
                        timeout=5.0,
                    )
                    if result.returncode == 0:
                        is_multiarch = "multiarch" in candidate
                        return sys_path, is_multiarch
                except Exception:
                    logger.debug(f"GDB candidate failed: {sys_path}")
                    continue

        return None, False

    def stop(self):
        """Terminate the GDB subprocess."""
        self._alive = False
        if self._proc:
            try:
                if self._proc.stdin:
                    self._proc.stdin.write(b"-gdb-exit\n")
                    self._proc.stdin.flush()
            except Exception:
                pass
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        logger.info("GDB session stopped")

    def execute(self, cmd: str, timeout: float = GDB_CMD_TIMEOUT) -> Optional[str]:
        """Execute a GDB CLI command and return the console output.

        Args:
            cmd: GDB command (e.g., "ptype my_var", "info address foo")
            timeout: Command timeout in seconds

        Returns:
            Console output string, or None on error/timeout
        """
        if not self.is_alive:
            return None

        with self._lock:
            return self._execute_cli(cmd, timeout)

    # ------------------------------------------------------------------
    # High-level APIs (replace pyelftools functions)
    # ------------------------------------------------------------------

    def lookup_symbol(self, sym_name: str) -> Optional[dict]:
        """Look up a symbol by name. Replaces elf_utils.lookup_symbol().

        Returns:
            {"addr": int, "size": int, "type": str, "section": str} or None
        """
        if not self.is_alive:
            return None

        with self._lock:
            return self._lookup_symbol_impl(sym_name)

    def search_symbols(self, query: str, limit: int = 100) -> Tuple[List[dict], int]:
        """Search symbols by name pattern. Replaces elf_utils.search_symbols().

        Returns:
            (list of symbol dicts, total count)
        """
        if not self.is_alive:
            return [], 0

        with self._lock:
            return self._search_symbols_impl(query, limit)

    def get_struct_layout(self, sym_name: str) -> Optional[List[dict]]:
        """Get struct member layout. Replaces elf_utils.get_struct_layout().

        Returns:
            [{"name", "offset", "size", "type_name"}, ...] or None
        """
        if not self.is_alive:
            return None

        with self._lock:
            return self._get_struct_layout_impl(sym_name)

    def get_symbols(self) -> Dict[str, dict]:
        """Get all symbols. Replaces elf_utils.get_symbols().

        Returns:
            Dict mapping symbol name to info dict
        """
        if not self.is_alive:
            return {}

        with self._lock:
            return self._get_symbols_impl()

    # ------------------------------------------------------------------
    # Internal: GDB/MI communication
    # ------------------------------------------------------------------

    def _execute_mi(self, cmd: str, timeout: float = GDB_CMD_TIMEOUT) -> Optional[str]:
        """Execute a GDB/MI command (via -interpreter-exec console) and return raw output."""
        if not self._proc or not self._proc.stdin:
            return None

        try:
            # Use MI command to execute CLI command
            mi_cmd = f'-interpreter-exec console "{cmd}"\n'
            self._proc.stdin.write(mi_cmd.encode("utf-8"))
            self._proc.stdin.flush()
            return self._read_until_prompt(timeout)
        except Exception as e:
            logger.error(f"GDB MI command failed: {e}")
            return None

    def _execute_cli(self, cmd: str, timeout: float = GDB_CMD_TIMEOUT) -> Optional[str]:
        """Execute a GDB CLI command and return console output lines."""
        raw = self._execute_mi(cmd, timeout)
        if raw is None:
            return None
        return self._extract_console_output(raw)

    def _read_until_prompt(self, timeout: float = 5.0) -> Optional[str]:
        """Read GDB/MI output until we see the (gdb) prompt or ^done/^error."""
        if not self._proc or not self._proc.stdout:
            return None

        lines = []
        deadline = time.time() + timeout

        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            try:
                # Non-blocking read with select
                import select

                ready, _, _ = select.select(
                    [self._proc.stdout], [], [], min(remaining, 0.5)
                )
                if not ready:
                    continue

                line = self._proc.stdout.readline()
                if not line:
                    break

                line_str = line.decode("utf-8", errors="replace").rstrip("\r\n")
                lines.append(line_str)

                # MI prompt indicates command completion
                if line_str == "(gdb) " or line_str == "(gdb)":
                    break
                if line_str.startswith("^done") or line_str.startswith("^error"):
                    # Read remaining until (gdb) prompt
                    while time.time() < deadline:
                        ready2, _, _ = select.select([self._proc.stdout], [], [], 0.1)
                        if not ready2:
                            break
                        next_line = self._proc.stdout.readline()
                        if not next_line:
                            break
                        nl = next_line.decode("utf-8", errors="replace").rstrip("\r\n")
                        lines.append(nl)
                        if nl == "(gdb) " or nl == "(gdb)":
                            break
                    break

            except Exception as e:
                logger.debug(f"GDB read error: {e}")
                break

        return "\n".join(lines)

    @staticmethod
    def _extract_console_output(raw: str) -> str:
        """Extract console output from GDB/MI response.

        MI console output lines start with ~"..." (C-string escaped).
        """
        lines = []
        for line in raw.split("\n"):
            if line.startswith('~"'):
                # Unescape MI C-string: ~"text\\n"
                content = line[2:]
                if content.endswith('"'):
                    content = content[:-1]
                # Unescape common sequences
                content = content.replace("\\n", "\n").replace("\\t", "\t")
                content = content.replace('\\"', '"').replace("\\\\", "\\")
                lines.append(content.rstrip("\n"))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal: Symbol lookup implementation
    # ------------------------------------------------------------------

    def _lookup_symbol_impl(self, sym_name: str) -> Optional[dict]:
        """Internal implementation of lookup_symbol."""
        # Use 'info address' to get symbol address
        output = self._execute_cli(f"info address {sym_name}")
        if not output or "No symbol" in output:
            return None

        addr = self._parse_address_from_info(output)
        if addr is None:
            return None

        # Get size via 'print sizeof(sym_name)'
        size = self._get_sizeof(sym_name)

        # Determine type (function vs variable)
        sym_type = "variable"
        if "is a function" in output or "in .text" in output:
            sym_type = "function"

        # Get section info
        section = self._get_symbol_section(output)

        # Classify const: check section first, then check type qualifier via ptype
        if sym_type == "variable":
            if section.startswith(".rodata"):
                sym_type = "const"
            else:
                # Check if the type has const qualifier
                ptype_out = self._execute_cli(f"ptype {sym_name}")
                if ptype_out and re.match(r"type\s*=\s*const\b", ptype_out):
                    sym_type = "const"

        return {
            "addr": addr,
            "size": size,
            "type": sym_type,
            "section": section,
        }

    def _search_symbols_impl(
        self, query: str, limit: int = 100
    ) -> Tuple[List[dict], int]:
        """Internal implementation of search_symbols."""
        query_lower = query.lower().strip()
        is_addr = query_lower.startswith("0x") or (
            len(query_lower) >= 4 and all(c in "0123456789abcdef" for c in query_lower)
        )

        if is_addr:
            # Address search: use 'info symbol <addr>'
            try:
                addr_val = (
                    int(query_lower, 16)
                    if not query_lower.startswith("0x")
                    else int(query_lower, 16)
                )
                output = self._execute_cli(f"info symbol 0x{addr_val:x}")
                if output and "No symbol" not in output:
                    results = self._parse_info_symbol(output, addr_val)
                    return results[:limit], len(results)
            except ValueError:
                pass
            return [], 0

        # Name search: use 'info variables' first (more useful), then 'info functions'
        results = []

        # Search variables first
        var_output = self._execute_cli(f"info variables {query}")
        if var_output:
            results.extend(self._parse_info_functions(var_output, "variable"))

        # Search functions
        func_output = self._execute_cli(f"info functions {query}")
        if func_output:
            results.extend(self._parse_info_functions(func_output, "function"))

        # Deduplicate by name (first occurrence wins — variables before functions)
        seen = set()
        unique = []
        for r in results:
            if r["name"] not in seen:
                seen.add(r["name"])
                unique.append(r)

        # Resolve missing addresses via 'info address'
        self._resolve_addresses(unique)

        unique.sort(key=lambda x: x["name"])
        return unique[:limit], len(unique)

    def _get_symbols_impl(self) -> Dict[str, dict]:
        """Internal implementation of get_symbols (full symbol dump)."""
        symbols: Dict[str, dict] = {}

        # Get all functions
        func_output = self._execute_cli("info functions", timeout=30.0)
        if func_output:
            func_list = self._parse_info_functions(func_output, "function")
            self._resolve_addresses(func_list)
            for sym in func_list:
                symbols[sym["name"]] = {
                    "addr": (
                        int(sym["addr"], 16)
                        if isinstance(sym["addr"], str)
                        else sym["addr"]
                    ),
                    "size": sym.get("size", 0),
                    "type": sym["type"],
                    "section": sym.get("section", ""),
                }

        # Get all variables
        var_output = self._execute_cli("info variables", timeout=30.0)
        if var_output:
            var_list = self._parse_info_functions(var_output, "variable")
            self._resolve_addresses(var_list)
            for sym in var_list:
                name = sym["name"]
                if name not in symbols:
                    symbols[name] = {
                        "addr": (
                            int(sym["addr"], 16)
                            if isinstance(sym["addr"], str)
                            else sym["addr"]
                        ),
                        "size": sym.get("size", 0),
                        "type": sym["type"],
                        "section": sym.get("section", ""),
                    }

        return symbols

    def _get_struct_layout_impl(self, sym_name: str) -> Optional[List[dict]]:
        """Internal implementation of get_struct_layout.

        Uses 'ptype /o <sym>' which shows struct members with offsets.
        """
        output = self._execute_cli(f"ptype /o {sym_name}")
        if not output:
            return None

        # Check if it's a struct/union
        if "type = struct" not in output and "type = union" not in output:
            return None

        return self._parse_ptype_output(output)

    # ------------------------------------------------------------------
    # Internal: Output parsing helpers
    # ------------------------------------------------------------------

    def _resolve_addresses(self, symbols: List[dict]):
        """Resolve missing addresses for debug-format symbols.

        Debug-format 'info functions/variables' output has line numbers but no
        addresses. This method queries 'info address <name>' for each symbol
        with addr "0x00000000" to fill in the real address and section.
        """
        for sym in symbols:
            if sym["addr"] != "0x00000000":
                continue
            output = self._execute_cli(f"info address {sym['name']}")
            if not output or "No symbol" in output:
                continue
            addr = self._parse_address_from_info(output)
            if addr is not None:
                sym["addr"] = f"0x{addr:08X}"
                # Also fix section and type from info address output
                section = self._get_symbol_section(output)
                if section:
                    sym["section"] = section
                # Reclassify type based on actual info
                if "is a function" in output:
                    sym["type"] = "function"
                elif sym["type"] != "function":
                    if section.startswith(".rodata"):
                        sym["type"] = "const"
                    elif sym["type"] != "const":
                        # Preserve const classification from declaration
                        sym["type"] = "variable"

    @staticmethod
    def _parse_address_from_info(output: str) -> Optional[int]:
        """Parse address from 'info address' output.

        Examples:
            "Symbol \"foo\" is at address 0x20001234."
            "Symbol \"bar\" is static storage at address 0x8001000."
        """
        m = re.search(r"address\s+0x([0-9a-fA-F]+)", output)
        if m:
            return int(m.group(1), 16)
        return None

    def _get_sizeof(self, sym_name: str) -> int:
        """Get size of a symbol via 'print sizeof(sym)'."""
        output = self._execute_cli(f"print sizeof({sym_name})")
        if output:
            m = re.search(r"\$\d+\s*=\s*(\d+)", output)
            if m:
                return int(m.group(1))
        return 0

    @staticmethod
    def _get_symbol_section(info_output: str) -> str:
        """Infer section from 'info address' output text."""
        text = info_output.lower()
        if ".text" in text or "is a function" in text:
            return ".text"
        if ".rodata" in text:
            return ".rodata"
        if ".bss" in text:
            return ".bss"
        if ".data" in text:
            return ".data"
        return ""

    @staticmethod
    def _parse_info_symbol(output: str, addr: int) -> List[dict]:
        """Parse 'info symbol <addr>' output.

        Example: "foo + 0 in section .text"
        """
        results = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line or "No symbol" in line:
                continue
            # "name + offset in section .sect"
            m = re.match(r"(\S+)\s*\+\s*(\d+)\s+in section\s+(\S+)", line)
            if m:
                name = m.group(1)
                offset = int(m.group(2))
                section = m.group(3)
                sym_type = "function" if section == ".text" else "variable"
                if section.startswith(".rodata"):
                    sym_type = "const"
                results.append(
                    {
                        "name": name,
                        "addr": f"0x{addr - offset:08X}",
                        "size": 0,
                        "type": sym_type,
                        "section": section,
                    }
                )
        return results

    @staticmethod
    def _parse_info_functions(
        output: str, default_type: str = "function"
    ) -> List[dict]:
        """Parse 'info functions/variables <pattern>' output.

        GDB output format:
            File path/to/file.c:
            123:	void foo(int);
            456:	static int bar;

        Or non-debug:
            Non-debugging symbols:
            0x08001234  func_name
        """
        results = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # Skip file headers and section headers
            if line.endswith(":") or line.startswith("File "):
                continue
            if "All defined" in line or "Non-debugging" in line:
                continue

            # Non-debug format: "0xADDR  name"
            m = re.match(r"0x([0-9a-fA-F]+)\s+(\S+)", line)
            if m:
                addr_val = int(m.group(1), 16)
                name = m.group(2)
                results.append(
                    {
                        "name": name,
                        "addr": f"0x{addr_val:08X}",
                        "size": 0,
                        "type": default_type,
                        "section": "",
                    }
                )
                continue

            # Debug format: "123: type name(args);" or "123: type name;"
            m = re.match(r"\d+:\s+(.+);", line)
            if m:
                decl = m.group(1).strip()
                # Extract function/variable name from declaration
                name = _extract_name_from_decl(decl)
                if name:
                    # Detect type from declaration
                    sym_type = default_type
                    if default_type == "variable":
                        # Check if declaration has const qualifier
                        if _decl_is_const(decl):
                            sym_type = "const"
                    results.append(
                        {
                            "name": name,
                            "addr": "0x00000000",
                            "size": 0,
                            "type": sym_type,
                            "section": "",
                        }
                    )

        return results

    @staticmethod
    def _parse_ptype_output(output: str) -> Optional[List[dict]]:
        """Parse 'ptype /o <sym>' output into struct member list.

        GDB 'ptype /o' output format:
        type = struct foo {
        /*    0      |     4 */    int x;
        /*    4      |     4 */    int y;
        /*    8      |     8 */    double z;

                                   /* total size (bytes):   16 */
                                 }

        Each member line: /* offset | size */  type name;
        """
        members = []

        for line in output.split("\n"):
            # Match member lines: /*  offset  |  size  */  type name;
            m = re.match(
                r"\s*/\*\s*(\d+)\s*\|\s*(\d+)\s*\*/\s+(.+?)\s*;",
                line,
            )
            if not m:
                continue

            offset = int(m.group(1))
            size = int(m.group(2))
            decl = m.group(3).strip()

            # Split declaration into type and name
            # Handle arrays: "int arr[10]" -> type="int", name="arr[10]"
            # Handle pointers: "int *ptr" -> type="int *", name="ptr"
            type_name, member_name = _split_type_and_name(decl)

            members.append(
                {
                    "name": member_name,
                    "offset": offset,
                    "size": size,
                    "type_name": type_name,
                }
            )

        return members if members else None


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _decl_is_const(decl: str) -> bool:
    """Check if a C declaration has a const qualifier.

    Examples:
        "const lv_font_t lv_font_montserrat_14" -> True
        "static const int foo" -> True
        "int bar" -> False
        "const char *baz" -> True
    """
    # Split into tokens and check for 'const' before the variable name
    tokens = decl.split()
    return "const" in tokens


def _extract_name_from_decl(decl: str) -> Optional[str]:
    """Extract symbol name from a C declaration string.

    Examples:
        "void foo(int, int)" -> "foo"
        "static int bar" -> "bar"
        "const char *baz" -> "baz"
    """
    # Function: look for name before '('
    paren = decl.find("(")
    if paren >= 0:
        prefix = decl[:paren].strip()
        parts = prefix.rsplit(None, 1)
        if parts:
            name = parts[-1].lstrip("*")
            return name if name else None

    # Variable: last word (skip type qualifiers)
    parts = decl.split()
    if parts:
        name = parts[-1].rstrip(";").lstrip("*")
        # Skip if it looks like a type keyword
        if name in (
            "int",
            "char",
            "void",
            "float",
            "double",
            "long",
            "short",
            "unsigned",
            "signed",
            "struct",
            "union",
            "enum",
            "const",
            "static",
            "volatile",
            "extern",
        ):
            return None
        return name if name else None
    return None


def _split_type_and_name(decl: str) -> Tuple[str, str]:
    """Split a C member declaration into (type_name, member_name).

    Examples:
        "int x" -> ("int", "x")
        "int *ptr" -> ("int *", "ptr")
        "char buf[64]" -> ("char[64]", "buf")
        "struct foo bar" -> ("struct foo", "bar")
    """
    decl = decl.strip()

    # Handle arrays: find '[' in the name part
    bracket = decl.rfind("[")
    if bracket >= 0:
        # "type name[N]" or "type name[N][M]"
        array_suffix = decl[bracket:]  # "[N]" or "[N][M]"
        prefix = decl[:bracket].strip()
        parts = prefix.rsplit(None, 1)
        if len(parts) == 2:
            return (parts[0] + array_suffix, parts[1])
        return (decl, "?")

    # Handle bitfields: "type name : N"
    colon = decl.find(" : ")
    if colon >= 0:
        prefix = decl[:colon].strip()
        parts = prefix.rsplit(None, 1)
        if len(parts) == 2:
            return (parts[0], parts[1])

    # Normal: "type name" or "type *name"
    parts = decl.rsplit(None, 1)
    if len(parts) == 2:
        type_part = parts[0]
        name_part = parts[1]
        # Move leading * from name to type
        while name_part.startswith("*"):
            type_part += " *"
            name_part = name_part[1:]
        return (type_part.strip(), name_part)

    return (decl, "?")
