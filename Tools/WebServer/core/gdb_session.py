#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
GDB Session manager for FPBInject Web Server.

Manages an arm-none-eabi-gdb subprocess connected to the GDB RSP Bridge,
providing high-level APIs for symbol lookup, type resolution, and memory access.

Uses pygdbmi for structured GDB/MI communication instead of fragile text parsing
of the MI transport layer. High-level command output (ptype, info address, etc.)
is still parsed from console text since GDB/MI has no native equivalents.
"""

import logging
import os
import re
import subprocess
import threading
import time
from typing import Dict, List, Optional, Tuple

from pygdbmi.IoManager import IoManager

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

    Communication uses pygdbmi's IoManager for reliable GDB/MI parsing.
    High-level APIs execute CLI commands via -interpreter-exec and extract
    console output from the structured MI responses.

    Usage:
        session = GDBSession(elf_path, toolchain_path)
        session.start(rsp_port=3333)
        result = session.execute("ptype my_struct_var")
        session.stop()
    """

    def __init__(self, elf_path: str, toolchain_path: Optional[str] = None):
        self._elf_path = elf_path
        self._toolchain_path = toolchain_path
        self._proc: Optional[subprocess.Popen] = None
        self._io: Optional[IoManager] = None
        self._lock = threading.Lock()
        self._alive = False
        self._rsp_port: Optional[int] = None
        self._search_generation = 0

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
            self._proc = subprocess.Popen(
                [gdb_path, "--interpreter=mi3", "--nx", "-q"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                bufsize=0,
            )

            # Create pygdbmi IoManager for structured MI communication
            self._io = IoManager(
                self._proc.stdin,
                self._proc.stdout,
                self._proc.stderr,
                time_to_check_for_additional_output_sec=0.3,
            )

            # Read initial GDB startup output
            self._io.get_gdb_response(timeout_sec=5.0, raise_error_on_timeout=False)

            # For gdb-multiarch: set ARM architecture before loading ELF
            if is_multiarch:
                logger.info("Setting ARM architecture for gdb-multiarch...")
                self._write_mi("set architecture arm", timeout=5.0)

            # Load ELF file
            logger.info("Loading ELF file into GDB...")
            resp = self._write_mi(f"file {self._elf_path}", timeout=GDB_STARTUP_TIMEOUT)
            if resp is None:
                self.stop()
                return False

            t_elf = time.time()
            logger.info(f"GDB loaded ELF in {t_elf - t_start:.2f}s")

            # Connect to RSP bridge
            logger.info(f"Connecting to RSP bridge on port {rsp_port}...")
            resp = self._write_mi(f"target remote 127.0.0.1:{rsp_port}", timeout=10.0)
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

        Returns:
            (gdb_path, is_multiarch) tuple. gdb_path is None if not found.
        """
        import shutil

        for candidate in _GDB_CANDIDATES:
            path = get_tool_path(candidate, self._toolchain_path)
            if os.path.isfile(path):
                try:
                    result = subprocess.run(
                        [path, "--version"], capture_output=True, timeout=5.0
                    )
                    if result.returncode == 0:
                        return path, "multiarch" in candidate
                except Exception:
                    logger.debug(f"GDB candidate failed: {path}")
                    continue

            sys_path = shutil.which(candidate)
            if sys_path:
                try:
                    result = subprocess.run(
                        [sys_path, "--version"], capture_output=True, timeout=5.0
                    )
                    if result.returncode == 0:
                        return sys_path, "multiarch" in candidate
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
        self._io = None
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
        """Look up a symbol by name. Returns symbol info dict or None."""
        if not self.is_alive:
            return None
        with self._lock:
            return self._lookup_symbol_impl(sym_name)

    def search_symbols(self, query: str, limit: int = 100) -> Tuple[List[dict], int]:
        """Search symbols by name pattern. Returns (list, total_count)."""
        if not self.is_alive:
            return [], 0
        self._search_generation += 1
        with self._lock:
            return self._search_symbols_impl(query, limit)

    def get_struct_layout(self, sym_name: str) -> Optional[List[dict]]:
        """Get struct member layout via 'ptype /o'. Returns member list or None."""
        if not self.is_alive:
            return None
        with self._lock:
            return self._get_struct_layout_impl(sym_name)

    def get_sizeof(self, type_or_sym: str) -> int:
        """Get size of a type or symbol. Returns 0 on failure."""
        if not self.is_alive:
            return 0
        with self._lock:
            return self._get_sizeof(type_or_sym)

    def get_symbols(self) -> Dict[str, dict]:
        """Get all symbols. Returns dict mapping name to info."""
        if not self.is_alive:
            return {}
        with self._lock:
            return self._get_symbols_impl()

    def read_symbol_value(self, sym_name: str) -> Optional[bytes]:
        """Read raw bytes of a symbol's initial value from the ELF."""
        if not self.is_alive:
            return None
        with self._lock:
            return self._read_symbol_value_impl(sym_name)

    # ------------------------------------------------------------------
    # Internal: GDB/MI communication via pygdbmi
    # ------------------------------------------------------------------

    def _write_mi(
        self, cmd: str, timeout: float = GDB_CMD_TIMEOUT
    ) -> Optional[List[dict]]:
        """Execute a GDB command via MI and return parsed responses.

        Uses pygdbmi IoManager for structured MI output parsing.
        Commands are sent as: -interpreter-exec console "<cmd>"

        Returns:
            List of pygdbmi response dicts, or None on error/timeout.
            Each dict has keys: type, message, payload, token, stream
        """
        if not self._io:
            return None

        mi_cmd = f'-interpreter-exec console "{cmd}"'
        try:
            responses = self._io.write(
                mi_cmd,
                timeout_sec=timeout,
                raise_error_on_timeout=False,
                read_response=True,
            )
        except Exception as e:
            logger.error(f"GDB MI write failed: {e}")
            return None

        if not responses:
            return None

        # Check for error in result records
        for r in responses:
            if r.get("type") == "result" and r.get("message") == "error":
                err_msg = ""
                if isinstance(r.get("payload"), dict):
                    err_msg = r["payload"].get("msg", "")
                logger.debug(f"GDB command error: {cmd} -> {err_msg}")
                # Still return responses so caller can inspect
                break

        return responses

    def _execute_cli(self, cmd: str, timeout: float = GDB_CMD_TIMEOUT) -> Optional[str]:
        """Execute a GDB CLI command and return console output text.

        Sends command via MI, extracts console-stream output from responses.
        """
        t0 = time.time()
        responses = self._write_mi(cmd, timeout)
        elapsed = time.time() - t0

        if responses is None:
            logger.warning(f"[GDB] command timed out ({elapsed:.2f}s): {cmd}")
            return None

        if elapsed > 1.0:
            logger.warning(f"[GDB] slow command ({elapsed:.2f}s): {cmd}")
        else:
            logger.debug(f"[GDB] command ({elapsed:.3f}s): {cmd}")

        console_text = self._extract_console_output(responses)

        # Log MI-level errors when no console output was produced
        if not console_text:
            for r in responses:
                if r.get("type") == "result" and r.get("message") == "error":
                    err_payload = r.get("payload", {})
                    err_msg = (
                        err_payload.get("msg", "")
                        if isinstance(err_payload, dict)
                        else str(err_payload)
                    )
                    logger.warning(f"[GDB] command '{cmd}' returned error: {err_msg}")
                    break

        return console_text

    @staticmethod
    def _extract_console_output(responses: List[dict]) -> str:
        """Extract console text from pygdbmi response list.

        Console output comes as responses with type='console' and
        payload containing the text string (already unescaped by pygdbmi).
        """
        lines = []
        for r in responses:
            if r.get("type") == "console" and r.get("payload"):
                text = r["payload"].rstrip("\n")
                if text:
                    lines.append(text)
        result = "\n".join(lines)
        if not result and responses:
            # Log non-console responses for debugging
            non_console = [r for r in responses if r.get("type") != "console"]
            if non_console:
                logger.debug(f"[GDB] no console output, other responses: {non_console}")
        return result

    # ------------------------------------------------------------------
    # Internal: Symbol lookup implementation
    # ------------------------------------------------------------------

    def _lookup_symbol_impl(self, sym_name: str) -> Optional[dict]:
        """Internal implementation of lookup_symbol."""
        t_start = time.time()
        logger.info(f"[GDB] lookup_symbol start: '{sym_name}'")

        # Strip array suffix (e.g. "PIN_MAP[128]" -> "PIN_MAP")
        bare_name = re.sub(r"\[.*\]$", "", sym_name)

        output = self._execute_cli(f"info address {bare_name}")
        if not output or "No symbol" in output:
            logger.info(f"[GDB] lookup_symbol: '{sym_name}' not found, raw={output!r}")
            return None

        addr = self._parse_address_from_info(output)
        if addr is None:
            logger.warning(
                f"[GDB] lookup_symbol: cannot parse address for '{sym_name}', raw={output!r}"
            )
            return None

        # For scoped C++ symbols, sizeof/ptype on the qualified name may fail.
        # Resolve a GDB-queryable name via the linker symbol at this address.
        query_name = bare_name
        size = self._get_sizeof(query_name)
        if size == 0 and addr:
            linker_name = self._resolve_linker_name(addr)
            if linker_name:
                query_name = linker_name
                size = self._get_sizeof(query_name)

        sym_type = "variable"
        if "is a function" in output or "in .text" in output:
            sym_type = "function"

        section = self._get_symbol_section(output)

        # Fallback: 'info address' often lacks section for non-function symbols
        # (e.g. "static storage at address 0x...").  Use 'info symbol <addr>'
        # which reliably returns "NAME in section .XXXX".
        if not section and addr:
            sym_output = self._execute_cli(f"info symbol 0x{addr:x}")
            if sym_output and "in section" in sym_output:
                m = re.search(r"in section (\.\w+)", sym_output)
                if m:
                    section = m.group(1)

        # Re-check type based on resolved section — mangled C++ function names
        # may not contain "is a function" in 'info address' output, but their
        # section will be .text.
        if sym_type == "variable" and section == ".text":
            sym_type = "function"

        if sym_type == "variable":
            if section.startswith(".rodata"):
                sym_type = "const"
            else:
                ptype_out = self._execute_cli(f"ptype {query_name}")
                if ptype_out and re.match(r"type\s*=\s*const\b", ptype_out):
                    sym_type = "const"

        # Detect pointer types via whatis (e.g. "type = lv_disp_t *")
        is_pointer = False
        pointer_target = None
        if sym_type in ("variable", "const"):
            whatis_out = self._execute_cli(f"whatis {query_name}")
            if whatis_out:
                wm = re.match(r"type\s*=\s*(.+)", whatis_out.strip())
                if wm:
                    raw_type = wm.group(1).strip()
                    # Pointer if type ends with '*' (but not function pointer)
                    if raw_type.endswith("*") and "(" not in raw_type:
                        is_pointer = True
                        pointer_target = raw_type[:-1].rstrip()

        elapsed = time.time() - t_start
        logger.info(
            f"[GDB] lookup_symbol done: '{sym_name}' -> "
            f"0x{addr:08X} size={size} type={sym_type}"
            f"{' ptr->' + pointer_target if is_pointer else ''}"
            f" ({elapsed:.3f}s)"
        )

        result = {
            "addr": addr,
            "size": size,
            "type": sym_type,
            "section": section,
        }
        if is_pointer:
            result["is_pointer"] = True
            result["pointer_target"] = pointer_target
        return result

    def _search_symbols_impl(
        self, query: str, limit: int = 100
    ) -> Tuple[List[dict], int]:
        """Internal implementation of search_symbols."""
        t_start = time.time()
        my_gen = self._search_generation
        logger.info(
            f"[GDB] search_symbols start: query='{query}' limit={limit} gen={my_gen}"
        )
        query_lower = query.lower().strip()
        is_addr = query_lower.startswith("0x") or (
            len(query_lower) >= 4 and all(c in "0123456789abcdef" for c in query_lower)
        )

        if is_addr:
            try:
                addr_val = int(query_lower, 16)
                output = self._execute_cli(f"info symbol 0x{addr_val:x}")
                if output and "No symbol" not in output:
                    results = self._parse_info_symbol(output, addr_val)
                    return results[:limit], len(results)
            except ValueError:
                pass
            return [], 0

        results = []

        var_output = self._execute_cli(f"info variables {query}")
        if var_output:
            results.extend(self._parse_info_functions(var_output, "variable"))

        if self._search_generation != my_gen:
            logger.info(
                f"[GDB] search_symbols cancelled (gen {my_gen} -> {self._search_generation})"
            )
            return [], 0

        func_output = self._execute_cli(f"info functions {query}")
        if func_output:
            results.extend(self._parse_info_functions(func_output, "function"))

        # Deduplicate by name
        seen = set()
        unique = []
        for r in results:
            if r["name"] not in seen:
                seen.add(r["name"])
                unique.append(r)

        t_parse = time.time()
        total_count = len(unique)
        logger.info(
            f"[GDB] search_symbols: found {total_count} unique symbols "
            f"(parse took {t_parse - t_start:.3f}s)"
        )

        if self._search_generation != my_gen:
            return [], 0

        unique.sort(key=lambda x: x["name"])
        capped = unique[:limit]
        if total_count > limit:
            logger.info(
                f"[GDB] search_symbols: capping address resolution to {limit}/{total_count} symbols"
            )

        self._resolve_addresses(capped, generation=my_gen)

        if self._search_generation != my_gen:
            return [], 0

        elapsed = time.time() - t_start
        logger.info(
            f"[GDB] search_symbols done: query='{query}' -> "
            f"{len(capped)} results, {total_count} total ({elapsed:.3f}s)"
        )
        return capped, total_count

    def _get_symbols_impl(self) -> Dict[str, dict]:
        """Internal implementation of get_symbols (full symbol dump)."""
        symbols: Dict[str, dict] = {}

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
        """Internal implementation of get_struct_layout."""
        t0 = time.time()
        logger.info(f"[GDB] get_struct_layout start: '{sym_name}'")

        bare_name = re.sub(r"\[.*\]$", "", sym_name)
        output = self._execute_cli(f"ptype /o {bare_name}", timeout=30.0)

        # Fallback for scoped symbols (e.g. "Class::Method()::var"):
        # Resolve linker name via address, then whatis -> ptype /o <type>.
        if not output or "No symbol" in output or "no debug info" in output:
            addr_output = self._execute_cli(f"info address {bare_name}")
            if addr_output:
                addr = self._parse_address_from_info(addr_output)
                if addr is not None:
                    linker_name = self._resolve_linker_name(addr)
                    if linker_name:
                        # Try ptype /o on the linker name directly first
                        output = self._execute_cli(
                            f"ptype /o {linker_name}", timeout=30.0
                        )
                        # If not struct/class, try getting type name via whatis
                        if not output or (
                            "type = struct" not in output
                            and "type = class" not in output
                            and "type = union" not in output
                        ):
                            whatis_out = self._execute_cli(f"whatis {linker_name}")
                            if whatis_out:
                                tm = re.match(r"type\s*=\s*(.+)", whatis_out.strip())
                                if tm:
                                    type_name = tm.group(1).strip()
                                    logger.info(
                                        f"[GDB] get_struct_layout: fallback via "
                                        f"type '{type_name}' for '{sym_name}'"
                                    )
                                    # Try with struct prefix if needed
                                    output = self._execute_cli(
                                        f"ptype /o struct {type_name}",
                                        timeout=30.0,
                                    )
                                    if not output or (
                                        "type = struct" not in output
                                        and "type = class" not in output
                                    ):
                                        output = self._execute_cli(
                                            f"ptype /o {type_name}",
                                            timeout=30.0,
                                        )

        if not output:
            logger.info(f"[GDB] get_struct_layout: no output for '{sym_name}'")
            return None

        # Check if output describes a struct, union, or class.  The "type = ..."
        # line may have qualifiers like "const" before the keyword.
        # C++ classes use "type = class ..." instead of "type = struct ...".
        has_struct = re.search(
            r"type\s*=\s*(?:const\s+|volatile\s+)*(?:struct|class)\b", output
        )
        has_union = re.search(r"type\s*=\s*(?:const\s+|volatile\s+)*union\b", output)
        if not has_struct and not has_union:
            logger.info(
                f"[GDB] get_struct_layout: '{sym_name}' is not struct/union, raw={output!r}"
            )
            return None

        result = self._parse_ptype_output(output)
        elapsed = time.time() - t0
        member_count = len(result) if result else 0
        logger.info(
            f"[GDB] get_struct_layout done: '{sym_name}' -> "
            f"{member_count} members ({elapsed:.3f}s)"
        )
        return result

    def _resolve_linker_name(self, addr: int) -> Optional[str]:
        """Resolve a linker-level symbol name from an address.

        Uses 'info symbol <addr>' to get the simple name that GDB can
        use for sizeof/ptype/whatis queries. This works even when the
        original symbol name is a scoped C++ qualified name.

        Returns:
            Simple symbol name (e.g. "fl_ctx") or None.
        """
        output = self._execute_cli(f"info symbol 0x{addr:x}")
        if not output or "No symbol" not in output:
            if output:
                # "fl_ctx in section .bss" or "foo + 0 in section .data"
                m = re.match(r"(\S+)\s*(?:\+\s*\d+\s+)?in section", output.strip())
                if m:
                    name = m.group(1)
                    logger.debug(f"[GDB] _resolve_linker_name: 0x{addr:x} -> '{name}'")
                    return name
        return None

    def _read_symbol_value_impl(self, sym_name: str) -> Optional[bytes]:
        """Read raw bytes of a symbol from the loaded ELF image."""
        info = self._lookup_symbol_impl(sym_name)
        if not info:
            return None

        size = info.get("size", 0)
        if size <= 0:
            return None

        section = info.get("section", "")
        if section.startswith(".bss"):
            return None

        addr = info.get("addr", 0)
        if addr == 0:
            return None

        num_words = (size + 3) // 4
        read_timeout = max(10.0, num_words * 0.05)
        logger.info(
            f"[GDB] read_symbol_value: reading {size} bytes "
            f"({num_words} words) from 0x{addr:x}, timeout={read_timeout:.1f}s"
        )
        output = self._execute_cli(f"x/{num_words}wx 0x{addr:x}", timeout=read_timeout)
        if not output:
            return None

        raw_bytes = bytearray()
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            colon_idx = line.find(":")
            if colon_idx >= 0:
                line = line[colon_idx + 1 :]
            for token in line.split():
                token = token.strip()
                if token.startswith("0x"):
                    try:
                        word = int(token, 16)
                        raw_bytes.extend(word.to_bytes(4, byteorder="little"))
                    except ValueError:
                        continue

        if len(raw_bytes) == 0:
            return None

        return bytes(raw_bytes[:size])

    # ------------------------------------------------------------------
    # Internal: Output parsing helpers
    # ------------------------------------------------------------------

    def _resolve_addresses(self, symbols: List[dict], generation: int = -1):
        """Resolve missing addresses for debug-format symbols."""
        unresolved = [s for s in symbols if s["addr"] == "0x00000000"]
        if unresolved:
            logger.info(
                f"[GDB] _resolve_addresses: {len(unresolved)}/{len(symbols)} "
                f"symbols need address resolution"
            )
        t0 = time.time()
        resolved_count = 0
        for sym in symbols:
            if sym["addr"] != "0x00000000":
                continue
            if generation >= 0 and resolved_count % 10 == 0:
                if self._search_generation != generation:
                    logger.info(
                        f"[GDB] _resolve_addresses cancelled at {resolved_count}/{len(unresolved)}"
                    )
                    return
            output = self._execute_cli(f"info address {sym['name']}")
            if not output or "No symbol" in output:
                continue
            addr = self._parse_address_from_info(output)
            if addr is not None:
                sym["addr"] = f"0x{addr:08X}"
                resolved_count += 1
                section = self._get_symbol_section(output)
                if section:
                    sym["section"] = section
                if "is a function" in output:
                    sym["type"] = "function"
                elif sym["type"] != "function":
                    if section.startswith(".rodata"):
                        sym["type"] = "const"
                    elif sym["type"] != "const":
                        sym["type"] = "variable"

        if unresolved:
            elapsed = time.time() - t0
            logger.info(
                f"[GDB] _resolve_addresses done: resolved {resolved_count}/{len(unresolved)} "
                f"({elapsed:.3f}s)"
            )

    @staticmethod
    def _parse_address_from_info(output: str) -> Optional[int]:
        """Parse address from 'info address' output.

        Handles multiple GDB output formats:
          - "Symbol \"foo\" is at address 0x20001234."
          - "Symbol \"bar\" is static storage at address 0x8001000."
          - "Symbol \"baz\" is at 0x80eb1cc in a file compiled without debugging."
        """
        m = re.search(r"(?:address|at)\s+0x([0-9a-fA-F]+)", output)
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
            logger.debug(
                f"[GDB] _get_sizeof: cannot parse for '{sym_name}', raw={output!r}"
            )

        # Fallback: strip ".N" suffix from local static variables
        # (e.g. "sm_pdu_size.1" -> "sm_pdu_size")
        if re.search(r"\.\d+$", sym_name):
            base_name = re.sub(r"\.\d+$", "", sym_name)
            output = self._execute_cli(f"print sizeof({base_name})")
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
        """Parse 'info symbol <addr>' output."""
        results = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line or "No symbol" in line:
                continue
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
        """Parse 'info functions/variables <pattern>' output."""
        results = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

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
                name = _extract_name_from_decl(decl)
                if name:
                    sym_type = default_type
                    if default_type == "variable" and _decl_is_const(decl):
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
        """Parse 'ptype /o <sym>' output into struct member list."""
        members = []

        for line in output.split("\n"):
            m = re.match(
                r"\s*/\*\s*(\d+)\s*\|\s*(\d+)\s*\*/\s+(.+?)\s*;",
                line,
            )
            if not m:
                continue

            offset = int(m.group(1))
            size = int(m.group(2))
            decl = m.group(3).strip()

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
    """Check if a C declaration has a const qualifier."""
    tokens = decl.split()
    return "const" in tokens


def _extract_name_from_decl(decl: str) -> Optional[str]:
    """Extract symbol name from a C declaration string."""
    paren = decl.find("(")
    if paren >= 0:
        prefix = decl[:paren].strip()
        parts = prefix.rsplit(None, 1)
        if parts:
            name = parts[-1].lstrip("*")
            return name if name else None

    parts = decl.split()
    if parts:
        name = parts[-1].rstrip(";").lstrip("*")
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
    """Split a C member declaration into (type_name, member_name)."""
    decl = decl.strip()

    bracket = decl.rfind("[")
    if bracket >= 0:
        array_suffix = decl[bracket:]
        prefix = decl[:bracket].strip()
        parts = prefix.rsplit(None, 1)
        if len(parts) == 2:
            return (parts[0] + array_suffix, parts[1])
        return (decl, "?")

    colon = decl.find(" : ")
    if colon >= 0:
        prefix = decl[:colon].strip()
        parts = prefix.rsplit(None, 1)
        if len(parts) == 2:
            return (parts[0], parts[1])

    parts = decl.rsplit(None, 1)
    if len(parts) == 2:
        type_part = parts[0]
        name_part = parts[1]
        while name_part.startswith("*"):
            type_part += " *"
            name_part = name_part[1:]
        return (type_part.strip(), name_part)

    return (decl, "?")
