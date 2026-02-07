#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
FPB Inject functionality for Web Server.

Provides injection operations based on fpb_loader.py but adapted for web server usage.
"""

import logging
import os
import time
from typing import Dict, Optional, Tuple

from core import elf_utils
from core import compiler as compiler_utils
from core.serial_protocol import FPBProtocol, FPBProtocolError
from utils.serial import scan_serial_ports, serial_open

logger = logging.getLogger(__name__)


# Re-export for backward compatibility
FPBInjectError = FPBProtocolError
__all__ = [
    "FPBInject",
    "FPBInjectError",
    "scan_serial_ports",
    "serial_open",
]


class FPBInject:
    """FPB Inject operations manager."""

    def __init__(self, device_state):
        self.device = device_state
        self._toolchain_path = None
        self._protocol = FPBProtocol(device_state)

    def set_toolchain_path(self, path: str):
        """Set the toolchain path."""
        if path and os.path.isdir(path):
            self._toolchain_path = path
            logger.info(f"Toolchain path set to: {path}")
        else:
            self._toolchain_path = None

    def get_tool_path(self, tool_name: str) -> str:
        """Get full path for a toolchain tool."""
        if self._toolchain_path:
            full_path = os.path.join(self._toolchain_path, tool_name)
            if os.path.exists(full_path):
                return full_path
        return tool_name

    def _get_subprocess_env(self) -> dict:
        """Get environment dict with toolchain path prepended to PATH."""
        env = os.environ.copy()
        if self._toolchain_path and os.path.isdir(self._toolchain_path):
            current_path = env.get("PATH", "")
            env["PATH"] = f"{self._toolchain_path}:{current_path}"
            logger.debug(f"Subprocess PATH prepended with: {self._toolchain_path}")
        return env

    def _fix_veneer_thumb_bits(
        self, data: bytes, base_addr: int, elf_path: str, verbose: bool = False
    ) -> bytes:
        """Fix Thumb bit in linker-generated veneer addresses."""
        return compiler_utils.fix_veneer_thumb_bits(
            data, base_addr, elf_path, self._toolchain_path, verbose
        )

    # ========== Protocol Delegation ==========

    def enter_fl_mode(self, timeout: float = 1.0) -> bool:
        """Enter fl interactive mode."""
        return self._protocol.enter_fl_mode(timeout)

    def get_platform(self) -> str:
        """Get detected platform type."""
        return self._protocol.get_platform()

    def exit_fl_mode(self, timeout: float = 1.0) -> bool:
        """Exit fl interactive mode."""
        return self._protocol.exit_fl_mode(timeout)

    def _send_cmd(
        self,
        cmd: str,
        timeout: float = 2.0,
        retry_on_missing_cmd: bool = True,
        max_retries: int = 3,
    ) -> str:
        """Send command and get response."""
        return self._protocol.send_cmd(cmd, timeout, retry_on_missing_cmd, max_retries)

    def _is_response_complete(self, response: str, cmd: str) -> bool:
        """Check if response appears complete."""
        return self._protocol._is_response_complete(response, cmd)

    def _log_raw(self, direction: str, data: str):
        """Log raw serial communication."""
        self._protocol._log_raw(direction, data)

    def _parse_response(self, resp: str) -> dict:
        """Parse response."""
        return self._protocol.parse_response(resp)

    def _update_slot_state(self, info: dict):
        """Update device slot state for frontend push notification."""
        if self.device is None:
            return
        try:
            slots = info.get("slots", [])
            if slots != self.device.cached_slots:
                self.device.cached_slots = slots.copy()
                self.device.slot_update_id += 1
                self.device.device_info = info
                logger.debug(
                    f"Slot state updated (id={self.device.slot_update_id}): "
                    f"{len([s for s in slots if s.get('occupied')])} active slots"
                )
        except Exception as e:
            logger.warning(f"Failed to update slot state: {e}")

    def send_fl_cmd(
        self, cmd: str, timeout: float = 2.0, max_retries: int = 3
    ) -> Tuple[bool, str]:
        """
        Send a fl command and return parsed result.

        Args:
            cmd: Command string (with or without 'fl' prefix)
            timeout: Response timeout in seconds
            max_retries: Maximum retry attempts at protocol level

        Returns:
            Tuple of (success, message)
        """
        try:
            resp = self._protocol.send_cmd(
                cmd, timeout=timeout, max_retries=max_retries
            )
            result = self._protocol.parse_response(resp)
            return result.get("ok", False), result.get("raw", result.get("msg", ""))
        except Exception as e:
            return False, str(e)

    def ping(self) -> Tuple[bool, str]:
        """Ping device."""
        return self._protocol.ping()

    def test_serial_throughput(
        self, start_size: int = 16, max_size: int = 4096, timeout: float = 2.0
    ) -> Dict:
        """Test serial port throughput."""
        return self._protocol.test_serial_throughput(start_size, max_size, timeout)

    def info(self) -> Tuple[Optional[dict], str]:
        """Get device info including slot states."""
        info, error = self._protocol.info()
        if info:
            self._update_slot_state(info)
        return info, error

    def alloc(self, size: int) -> Tuple[Optional[int], str]:
        """Allocate memory buffer."""
        return self._protocol.alloc(size)

    def upload(
        self, data: bytes, start_offset: int = 0, progress_callback=None
    ) -> Tuple[bool, dict]:
        """Upload binary data in chunks."""
        return self._protocol.upload(data, start_offset, progress_callback)

    def patch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set FPB patch (direct mode)."""
        return self._protocol.patch(comp, orig, target)

    def tpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set trampoline patch."""
        return self._protocol.tpatch(comp, orig, target)

    def dpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set DebugMonitor patch."""
        return self._protocol.dpatch(comp, orig, target)

    def unpatch(self, comp: int = 0, all: bool = False) -> Tuple[bool, str]:
        """Clear FPB patch."""
        return self._protocol.unpatch(comp, all)

    def find_slot_for_target(self, target_addr: int) -> Tuple[int, bool]:
        """
        Find a suitable slot for the target address.

        Strategy (B - Smart Reuse):
        1. If target_addr is already patched in some slot, reuse that slot
        2. Otherwise find first empty slot
        3. If no empty slot, return -1

        Returns:
            Tuple of (slot_id, needs_unpatch)
        """
        info, error = self.info()
        if error or not info:
            return 0, False

        slots = info.get("slots", [])
        first_empty = -1

        for slot in slots:
            slot_id = slot.get("id", -1)
            occupied = slot.get("occupied", False)
            orig_addr = slot.get("orig_addr", 0)

            if occupied:
                if orig_addr == target_addr or orig_addr == (target_addr & ~1):
                    return slot_id, True
            else:
                if first_empty < 0:
                    first_empty = slot_id

        if first_empty >= 0:
            return first_empty, False

        return -1, False

    # ========== ELF Utilities ==========

    def get_elf_build_time(self, elf_path: str) -> Optional[str]:
        """Get build time from ELF file."""
        return elf_utils.get_elf_build_time(elf_path)

    def get_symbols(self, elf_path: str) -> Dict[str, int]:
        """Extract symbols from ELF file."""
        return elf_utils.get_symbols(elf_path, self._toolchain_path)

    def disassemble_function(self, elf_path: str, func_name: str) -> Tuple[bool, str]:
        """Disassemble a specific function from ELF file."""
        return elf_utils.disassemble_function(elf_path, func_name, self._toolchain_path)

    def decompile_function(self, elf_path: str, func_name: str) -> Tuple[bool, str]:
        """Decompile a specific function from ELF file using angr."""
        return elf_utils.decompile_function(elf_path, func_name)

    def get_signature(self, elf_path: str, func_name: str) -> Optional[str]:
        """Get function signature from ELF file."""
        return elf_utils.get_signature(elf_path, func_name, self._toolchain_path)

    # ========== Compiler Utilities ==========

    def parse_dep_file_for_compile_command(
        self, source_file: str, build_output_dir: str = None
    ) -> Optional[str]:
        """Parse .d dependency file to extract the original compile command."""
        return compiler_utils.parse_dep_file_for_compile_command(
            source_file, build_output_dir
        )

    def parse_compile_commands(
        self, compile_commands_path: str, source_file: str = None, verbose: bool = False
    ) -> Optional[Dict]:
        """Parse standard CMake compile_commands.json to extract compiler flags."""
        return compiler_utils.parse_compile_commands(
            compile_commands_path, source_file, verbose
        )

    def compile_inject(
        self,
        source_content: str,
        base_addr: int,
        elf_path: str = None,
        compile_commands_path: str = None,
        verbose: bool = False,
        source_ext: str = None,
        original_source_file: str = None,
    ) -> Tuple[Optional[bytes], Optional[Dict[str, int]], str]:
        """Compile injection code from source content to binary."""
        return compiler_utils.compile_inject(
            source_content=source_content,
            base_addr=base_addr,
            elf_path=elf_path,
            compile_commands_path=compile_commands_path,
            verbose=verbose,
            source_ext=source_ext,
            original_source_file=original_source_file,
            toolchain_path=self._toolchain_path,
        )

    # ========== Injection Workflow ==========

    def inject_single(
        self,
        target_addr: int,
        inject_addr: int,
        inject_name: str,
        data: bytes,
        align_offset: int,
        patch_mode: str,
        comp: int,
        progress_callback=None,
    ) -> Tuple[bool, dict]:
        """Inject a single function (internal helper)."""
        result = {
            "target_addr": f"0x{target_addr:08X}",
            "inject_func": inject_name,
            "inject_addr": f"0x{inject_addr:08X}",
            "slot": -1,
        }

        if comp < 0:
            slot_id, needs_unpatch = self.find_slot_for_target(target_addr)
            if slot_id < 0:
                return False, {"error": "No available FPB slots"}

            if needs_unpatch:
                logger.info(
                    f"Reusing slot {slot_id} for target 0x{target_addr:08X}, unpatch first"
                )
                self.unpatch(comp=slot_id)

            comp = slot_id

        result["slot"] = comp

        upload_start = align_offset
        success, upload_result = self.upload(
            data, start_offset=upload_start, progress_callback=progress_callback
        )
        if not success:
            return False, {"error": upload_result.get("error", "Upload failed")}

        result["upload_time"] = round(upload_result.get("time", 0), 2)

        patch_addr = inject_addr | 1

        if patch_mode == "trampoline":
            success, msg = self.tpatch(comp, target_addr, patch_addr)
        elif patch_mode == "debugmon":
            success, msg = self.dpatch(comp, target_addr, patch_addr)
        else:
            success, msg = self.patch(comp, target_addr, patch_addr)

        if not success:
            return False, {"error": f"Patch failed: {msg}"}

        return True, result

    def inject(
        self,
        source_content: str,
        target_func: str,
        inject_func: str = None,
        patch_mode: str = "trampoline",
        comp: int = -1,
        progress_callback=None,
        source_ext: str = None,
        original_source_file: str = None,
    ) -> Tuple[bool, dict]:
        """Perform full injection workflow."""
        result = {
            "compile_time": 0,
            "upload_time": 0,
            "total_time": 0,
            "code_size": 0,
            "inject_func": None,
            "target_addr": None,
            "inject_addr": None,
            "slot": -1,
        }

        total_start = time.time()

        elf_path = self.device.elf_path
        if not elf_path or not os.path.exists(elf_path):
            return False, {"error": "ELF file not found"}

        symbols = self.get_symbols(elf_path)
        if target_func not in symbols:
            return False, {"error": f"Target function '{target_func}' not found in ELF"}

        target_addr = symbols[target_func]
        result["target_addr"] = f"0x{target_addr:08X}"

        actual_comp = comp
        if comp < 0:
            slot_id, needs_unpatch = self.find_slot_for_target(target_addr)
            if slot_id < 0:
                return False, {"error": "No available FPB slots"}

            if needs_unpatch:
                logger.info(
                    f"Reusing slot {slot_id} for target 0x{target_addr:08X}, unpatch first"
                )
                self.unpatch(comp=slot_id)

            actual_comp = slot_id

        result["slot"] = actual_comp

        info, error = self.info()
        if error:
            return False, {"error": f"Failed to get device info: {error}"}

        compile_start = time.time()

        data, inject_symbols, error = self.compile_inject(
            source_content,
            0x20000000,
            elf_path,
            self.device.compile_commands_path,
            source_ext=source_ext,
            original_source_file=original_source_file,
        )
        if error:
            return False, {"error": error}

        code_size = len(data)
        alloc_size = code_size + 8

        raw_addr, error = self.alloc(alloc_size)
        if error or raw_addr is None:
            return False, {"error": f"Alloc failed: {error or 'No address returned'}"}

        aligned_addr = (raw_addr + 7) & ~7
        align_offset = aligned_addr - raw_addr
        base_addr = aligned_addr

        data, inject_symbols, error = self.compile_inject(
            source_content,
            base_addr,
            elf_path,
            self.device.compile_commands_path,
            source_ext=source_ext,
            original_source_file=original_source_file,
        )
        if error:
            return False, {"error": error}

        compile_time = time.time() - compile_start
        result["compile_time"] = round(compile_time, 2)
        result["code_size"] = len(data)

        # Find the inject function in compiled symbols
        # New design: function names are preserved (no inject_ prefix)
        # The inject function should match target_func or be specified via inject_func
        # Filter out veneer symbols (they are generated by linker, not user code)
        user_symbols = {
            name: addr
            for name, addr in inject_symbols.items()
            if not name.endswith("_veneer") and not name.startswith("__")
        }

        found_inject_func = None
        if inject_func:
            # User specified exact function name
            for name, addr in inject_symbols.items():
                if inject_func in name:
                    found_inject_func = (name, addr)
                    break
        else:
            # Auto-detect: look for function matching target_func
            target_lower = target_func.lower()
            for name, addr in user_symbols.items():
                name_lower = name.lower()
                # Direct match with target function name
                if name_lower == target_lower:
                    found_inject_func = (name, addr)
                    break
                # Partial match (for mangled names)
                if target_lower in name_lower:
                    found_inject_func = (name, addr)
                    break

            # Fallback: use first user symbol (lowest address, excluding veneers)
            if not found_inject_func and user_symbols:
                found_inject_func = min(user_symbols.items(), key=lambda x: x[1])

        if not found_inject_func:
            return False, {
                "error": "No FPB_INJECT marked function found in compiled code"
            }

        result["inject_func"] = found_inject_func[0]
        result["inject_addr"] = f"0x{found_inject_func[1]:08X}"

        upload_start = align_offset
        success, upload_result = self.upload(
            data, start_offset=upload_start, progress_callback=progress_callback
        )
        if not success:
            return False, {"error": upload_result.get("error", "Upload failed")}

        result["upload_time"] = round(upload_result.get("time", 0), 2)

        patch_addr = found_inject_func[1] | 1

        if patch_mode == "trampoline":
            success, msg = self.tpatch(actual_comp, target_addr, patch_addr)
        elif patch_mode == "debugmon":
            success, msg = self.dpatch(actual_comp, target_addr, patch_addr)
        else:
            success, msg = self.patch(actual_comp, target_addr, patch_addr)

        if not success:
            return False, {"error": f"Patch failed: {msg}"}

        result["total_time"] = round(time.time() - total_start, 2)
        result["patch_mode"] = patch_mode

        self.device.inject_active = True
        self.device.last_inject_target = target_func
        self.device.last_inject_func = found_inject_func[0]
        self.device.last_inject_time = time.time()

        return True, result

    def inject_multi(
        self,
        source_content: str,
        patch_mode: str = "trampoline",
        progress_callback=None,
        source_ext: str = None,
        original_source_file: str = None,
    ) -> Tuple[bool, dict]:
        """
        Perform multi-function injection workflow.

        Each inject_<target_func> function in the source gets its own Slot
        with independent memory allocation.
        """
        result = {
            "compile_time": 0,
            "upload_time": 0,
            "total_time": 0,
            "code_size": 0,
            "injections": [],
            "errors": [],
        }

        total_start = time.time()

        elf_path = self.device.elf_path
        if not elf_path or not os.path.exists(elf_path):
            return False, {"error": "ELF file not found"}

        elf_symbols = self.get_symbols(elf_path)

        data, inject_symbols, error = self.compile_inject(
            source_content,
            0x20000000,
            elf_path,
            self.device.compile_commands_path,
            source_ext=source_ext,
            original_source_file=original_source_file,
        )
        if error:
            return False, {"error": error}

        # New design: functions are not renamed, they keep original names
        # Filter out veneer symbols and internal symbols
        user_symbols = {
            name: addr
            for name, addr in inject_symbols.items()
            if not name.endswith("_veneer") and not name.startswith("__")
        }
        inject_funcs = list(user_symbols.items())

        if not inject_funcs:
            return False, {
                "error": "No FPB_INJECT marked functions found in compiled code"
            }

        inject_funcs.sort(key=lambda x: x[1])

        logger.info(
            f"Found {len(inject_funcs)} inject functions: {[f[0] for f in inject_funcs]}"
        )

        injection_targets = []
        for inject_name, _ in inject_funcs:
            # In new design, inject_name IS the target function name
            target_func = inject_name

            target_addr = None
            actual_target_name = target_func
            for sym_name, sym_addr in elf_symbols.items():
                if sym_name.lower() == target_func.lower():
                    target_addr = sym_addr
                    actual_target_name = sym_name
                    break

            if target_addr is None:
                result["errors"].append(f"Target '{target_func}' not found in ELF")
                logger.warning(
                    f"Target function '{target_func}' not found in ELF symbols"
                )
                continue

            injection_targets.append((actual_target_name, inject_name))

        if not injection_targets:
            return False, {"error": "No valid injection targets found"}

        total_compile_time = 0
        total_upload_time = 0
        total_code_size = 0

        for target_func, inject_func in injection_targets:
            logger.info(f"Injecting {target_func} -> {inject_func}")

            success, inj_result = self.inject(
                source_content=source_content,
                target_func=target_func,
                inject_func=inject_func,
                patch_mode=patch_mode,
                comp=-1,
                progress_callback=progress_callback,
                source_ext=source_ext,
                original_source_file=original_source_file,
            )

            injection_entry = {
                "target_func": target_func,
                "target_addr": inj_result.get("target_addr", "?"),
                "inject_func": inject_func,
                "inject_addr": inj_result.get("inject_addr", "?"),
                "slot": inj_result.get("slot", -1),
                "code_size": inj_result.get("code_size", 0),
                "success": success,
            }

            if not success:
                injection_entry["error"] = inj_result.get("error", "Unknown error")
                result["errors"].append(
                    f"Inject '{target_func}' failed: {inj_result.get('error', '?')}"
                )
                logger.error(
                    f"Inject failed for {target_func}: {inj_result.get('error')}"
                )
            else:
                total_compile_time += inj_result.get("compile_time", 0)
                total_upload_time += inj_result.get("upload_time", 0)
                total_code_size += inj_result.get("code_size", 0)
                logger.info(
                    f"Injected {target_func} -> {inject_func} @ slot {inj_result.get('slot', '?')}"
                )

            result["injections"].append(injection_entry)

        result["compile_time"] = round(total_compile_time, 2)
        result["upload_time"] = round(total_upload_time, 2)
        result["code_size"] = total_code_size
        result["total_time"] = round(time.time() - total_start, 2)
        result["patch_mode"] = patch_mode

        successful = sum(1 for inj in result["injections"] if inj.get("success", False))
        result["successful_count"] = successful
        result["total_count"] = len(injection_targets)

        if successful > 0:
            self.device.inject_active = True
            self.device.last_inject_time = time.time()

        return successful > 0, result
