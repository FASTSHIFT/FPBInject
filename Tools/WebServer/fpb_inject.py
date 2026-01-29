#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
FPB Inject functionality for Web Server.

Provides injection operations based on fpb_loader.py but adapted for web server usage.
"""

import base64
import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import serial
import serial.tools.list_ports

from utils.crc import crc16

logger = logging.getLogger(__name__)


class FPBInjectError(Exception):
    """Exception for FPB inject operations."""

    pass


class FPBInject:
    """FPB Inject operations manager."""

    def __init__(self, device_state):
        self.device = device_state
        self._toolchain_path = None
        self._in_fl_mode = False
        self._platform = "unknown"  # "nuttx", "bare-metal", or "unknown"

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
            # Prepend toolchain path to PATH so ccache and other tools can find the compiler
            current_path = env.get("PATH", "")
            env["PATH"] = f"{self._toolchain_path}:{current_path}"
            logger.debug(f"Subprocess PATH prepended with: {self._toolchain_path}")
        return env

    def _fix_veneer_thumb_bits(
        self, data: bytes, base_addr: int, elf_path: str, verbose: bool = False
    ) -> bytes:
        """
        Fix Thumb bit in linker-generated veneer addresses.

        When using --just-symbols, GCC linker generates long call veneers like:
            ldr.w pc, [pc, #0]   ; F8 5F F0 00
            .word <address>      ; Target address (missing Thumb bit)

        For Thumb functions, the target address must have bit 0 set.
        This function scans the binary for such patterns and fixes them.

        Args:
            data: Compiled binary data
            base_addr: Base address of the binary
            elf_path: Path to the firmware ELF (to check function types)
            verbose: Enable verbose logging

        Returns:
            Fixed binary data with Thumb bits set in veneers
        """
        if not elf_path or len(data) < 8:
            return data

        # Build a set of Thumb function addresses from the ELF
        # Thumb functions in ELF have odd addresses (bit 0 set) in symbol table
        thumb_funcs = set()
        try:
            import subprocess

            readelf_cmd = self.get_tool_path("arm-none-eabi-readelf")
            result = subprocess.run(
                [readelf_cmd, "-s", elf_path],
                capture_output=True,
                text=True,
                env=self._get_subprocess_env(),
            )
            for line in result.stdout.split("\n"):
                parts = line.split()
                if len(parts) >= 8 and parts[3] == "FUNC":
                    try:
                        addr = int(parts[1], 16)
                        # Thumb functions have odd address in symbol table
                        if addr & 1:
                            thumb_funcs.add(addr & ~1)  # Store even address for lookup
                    except ValueError:
                        pass
        except Exception as e:
            logger.warning(f"Failed to read ELF symbols for Thumb fix: {e}")
            return data

        if not thumb_funcs:
            return data

        # Convert to bytearray for modification
        data = bytearray(data)

        # Pattern: F8 5F F0 00 = ldr.w pc, [pc, #0] (little-endian: 5F F8 00 F0)
        # Followed by 4-byte address
        veneer_pattern = bytes([0x5F, 0xF8, 0x00, 0xF0])
        fixed_count = 0

        i = 0
        while i < len(data) - 8:
            if data[i : i + 4] == veneer_pattern:
                # Found veneer instruction, get the address (little-endian)
                addr_offset = i + 4
                target_addr = int.from_bytes(
                    data[addr_offset : addr_offset + 4], "little"
                )

                # Check if this is a Thumb function (even address that should be odd)
                if (target_addr & 1) == 0 and target_addr in thumb_funcs:
                    # Fix: set Thumb bit
                    fixed_addr = target_addr | 1
                    data[addr_offset : addr_offset + 4] = fixed_addr.to_bytes(
                        4, "little"
                    )
                    fixed_count += 1
                    if verbose:
                        veneer_addr = base_addr + i
                        logger.info(
                            f"Fixed veneer Thumb bit at 0x{veneer_addr:08X}: "
                            f"0x{target_addr:08X} -> 0x{fixed_addr:08X}"
                        )
                i += 8  # Skip past the veneer
            else:
                i += 2  # Thumb instructions are 2-byte aligned

        if fixed_count > 0:
            logger.info(f"Fixed {fixed_count} veneer Thumb bit(s)")

        return bytes(data)

    def enter_fl_mode(self, timeout: float = 1.0) -> bool:
        """Enter fl interactive mode by sending 'fl' command.

        Returns True if we entered fl interactive mode (fl> prompt detected),
        False if not needed (bare-metal mode or no response).
        """
        ser = self.device.ser
        if not ser:
            self._in_fl_mode = False
            self._platform = "unknown"
            return False

        try:
            self._log_raw("TX", "fl")
            ser.reset_input_buffer()
            ser.write(b"fl\n")
            ser.flush()

            # Wait for prompt or response
            start = time.time()
            response = ""
            while time.time() - start < timeout:
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                    response += chunk
                    if "fl>" in response or "[OK]" in response or "[ERR]" in response:
                        break
                time.sleep(0.01)

            self._log_raw("RX", response.strip())
            logger.debug(f"Entered fl mode: {response.strip()}")

            # Detect platform type based on response
            if "fl>" in response:
                # NuttX platform - entered interactive mode
                self._in_fl_mode = True
                self._platform = "nuttx"
                logger.info("Detected NuttX platform (fl interactive mode)")
                return True
            elif "Enter" in response and "interactive mode" in response:
                # NuttX platform - got the hint message, need to enter fl mode
                # This happens when NuttX receives direct command without fl prefix
                self._platform = "nuttx"
                logger.info("Detected NuttX platform (requires interactive mode)")
                # Already sent 'fl', should be in fl mode now - retry read
                start = time.time()
                while time.time() - start < timeout:
                    if ser.in_waiting:
                        chunk = ser.read(ser.in_waiting).decode(
                            "utf-8", errors="replace"
                        )
                        response += chunk
                        if "fl>" in response:
                            self._in_fl_mode = True
                            return True
                    time.sleep(0.01)
                self._in_fl_mode = False
                return False
            else:
                # Bare-metal or unknown - commands work directly
                self._in_fl_mode = False
                self._platform = "bare-metal"
                return False
        except Exception as e:
            logger.error(f"Error entering fl mode: {e}")
            self._in_fl_mode = False
            self._platform = "unknown"
            return False

    def get_platform(self) -> str:
        """Get detected platform type.

        Returns:
            "nuttx" - NuttX RTOS (requires fl interactive mode)
            "bare-metal" - Bare-metal firmware (direct commands)
            "unknown" - Not detected yet
        """
        return getattr(self, "_platform", "unknown")

    def exit_fl_mode(self, timeout: float = 1.0) -> bool:
        """Exit fl interactive mode by sending 'exit' command.

        Only sends 'exit' if we previously entered fl interactive mode.
        """
        # Only exit if we actually entered fl mode
        if not getattr(self, "_in_fl_mode", False):
            logger.debug("Not in fl mode, skipping exit")
            return True

        ser = self.device.ser
        if not ser:
            return False

        try:
            self._log_raw("TX", "exit")
            ser.reset_input_buffer()
            ser.write(b"exit\n")
            ser.flush()

            # Wait for response
            start = time.time()
            response = ""
            while time.time() - start < timeout:
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                    response += chunk
                time.sleep(0.01)

            self._log_raw("RX", response.strip())
            logger.debug(f"Exited fl mode: {response.strip()}")
            self._in_fl_mode = False
            return True
        except Exception as e:
            logger.error(f"Error exiting fl mode: {e}")
            return False

    def _send_cmd(
        self,
        cmd: str,
        timeout: float = 2.0,
        retry_on_missing_cmd: bool = True,
        max_retries: int = 3,
    ) -> str:
        """
        Send command and get response with automatic retry on interrupted responses.

        Args:
            cmd: Command to send
            timeout: Response timeout in seconds
            retry_on_missing_cmd: Whether to retry if "Missing --cmd" is detected
            max_retries: Maximum number of retries on interrupted/invalid responses

        Returns:
            Response string
        """
        ser = self.device.ser
        if not ser:
            raise FPBInjectError("Serial port not connected")

        # Build command: fl --cmd ...
        # Note: -ni flag is NOT used here - it's only for entering interactive mode
        full_cmd = f"fl {cmd}" if not cmd.strip().startswith("fl ") else cmd

        last_response = ""
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.warning(
                    f"Retry {attempt}/{max_retries} for command: {cmd[:50]}..."
                )
                self._log_raw("RETRY", f"Attempt {attempt + 1}/{max_retries + 1}")
                time.sleep(0.05)  # Brief delay before retry

            logger.debug(f"TX: {full_cmd}")
            self._log_raw("TX", full_cmd)

            # Clear buffer
            ser.reset_input_buffer()

            # Send command with chunking to workaround slow serial drivers
            data_bytes = (full_cmd + "\n").encode()
            tx_chunk_size = getattr(self.device, "tx_chunk_size", 0)
            tx_chunk_delay = getattr(self.device, "tx_chunk_delay", 0.005)
            if tx_chunk_size > 0 and len(data_bytes) > tx_chunk_size:
                # Split into chunks for slow serial drivers
                for i in range(0, len(data_bytes), tx_chunk_size):
                    chunk = data_bytes[i : i + tx_chunk_size]
                    ser.write(chunk)
                    ser.flush()
                    if i + tx_chunk_size < len(data_bytes):
                        time.sleep(tx_chunk_delay)
            else:
                # Send all at once
                ser.write(data_bytes)
            ser.flush()

            # Read response
            response = ""
            start = time.time()
            while time.time() - start < timeout:
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                    response += chunk
                    if "[OK]" in response or "[ERR]" in response:
                        time.sleep(0.005)
                        if ser.in_waiting:
                            response += ser.read(ser.in_waiting).decode(
                                "utf-8", errors="replace"
                            )
                        break
                time.sleep(0.002)

            response = response.strip()
            last_response = response
            logger.debug(f"RX: {response}")
            self._log_raw("RX", response)

            # Check if response is valid (contains [OK] or [ERR])
            if "[OK]" in response or "[ERR]" in response:
                # Check if this is NuttX platform detection message
                if "Enter" in response and "interactive mode" in response:
                    # NuttX platform: need to enter fl mode first
                    break
                # Valid response, check if it looks complete
                # A valid response should have [OK] or [ERR] followed by optional data
                if self._is_response_complete(response, cmd):
                    break  # Success, exit retry loop
                else:
                    logger.warning(
                        f"Response appears incomplete, may have been interrupted"
                    )
                    self._log_raw("WARN", "Response incomplete, retrying...")
                    continue  # Retry
            elif "Missing --cmd" in response:
                # Not in fl mode (bare-metal platform or direct execution)
                break
            else:
                # No valid response marker, might be interrupted by logs
                logger.warning(f"No valid response marker ([OK]/[ERR]), retrying...")
                self._log_raw("WARN", "No response marker, retrying...")
                continue  # Retry

        # Detect platform and enter fl mode if needed
        need_fl_mode = False
        if "Enter" in last_response and "interactive mode" in last_response:
            # NuttX platform: explicitly requires fl interactive mode
            self._platform = "nuttx"
            need_fl_mode = True
            logger.info("Detected NuttX platform (requires fl interactive mode)")
        elif "Missing --cmd" in last_response:
            # Bare-metal or older NuttX - try entering fl mode
            need_fl_mode = True

        if retry_on_missing_cmd and need_fl_mode:
            self._log_raw("INFO", "Entering fl interactive mode...")
            if self.enter_fl_mode():
                return self._send_cmd(
                    cmd, timeout, retry_on_missing_cmd=False, max_retries=max_retries
                )

        return last_response

    def _is_response_complete(self, response: str, cmd: str) -> bool:
        """
        Check if response appears complete and not interrupted.

        Args:
            response: The response string
            cmd: The original command (for context)

        Returns:
            True if response appears complete
        """
        # Basic check: response should have [OK] or [ERR]
        has_marker = "[OK]" in response or "[ERR]" in response

        if not has_marker:
            return False

        # For data commands (like read), check if data looks complete
        # Data is usually hex encoded, should have even length
        if "-c read" in cmd or "-c info" in cmd:
            # Extract data after [OK]
            if "[OK]" in response:
                parts = response.split("[OK]", 1)
                if len(parts) > 1:
                    data_part = parts[1].strip()
                    # If there's data, it should look like valid output
                    # Check for common signs of interruption: truncated hex, mixed logs
                    if data_part:
                        # Check if interrupted by log messages (common patterns)
                        log_patterns = [
                            "[I]",
                            "[W]",
                            "[E]",
                            "[D]",
                            "INFO:",
                            "WARN:",
                            "ERR:",
                        ]
                        for pattern in log_patterns:
                            if pattern in data_part:
                                # Log message mixed in - likely interrupted
                                return False

        return True

    def _log_raw(self, direction: str, data: str):
        """Log raw serial communication to device's raw_serial_log."""
        if not data:
            return
        try:
            import time as t

            entry = {
                "id": self.device.raw_log_next_id,
                "time": t.time(),
                "dir": direction,
                "data": data,
            }
            self.device.raw_serial_log.append(entry)
            self.device.raw_log_next_id += 1
            # Trim if too large
            max_size = getattr(self.device, "raw_log_max_size", 5000)
            if len(self.device.raw_serial_log) > max_size:
                self.device.raw_serial_log = self.device.raw_serial_log[-max_size:]
        except Exception:
            pass

    def _parse_response(self, resp: str) -> dict:
        """Parse response - format: [OK] msg or [ERR] msg"""
        resp = resp.strip()

        # Remove ANSI escape sequences and shell prompts
        # Remove ANSI escape codes: ESC[...X sequences only (must have ESC prefix)
        # Do NOT match [OK] or [ERR] which don't have ESC prefix
        clean_resp = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", resp)
        # Remove standalone terminal control codes like [K (but not [OK] or [ERR])
        # Only match single letter codes that are NOT O or E (to preserve [OK]/[ERR])
        clean_resp = re.sub(r"\[([0-9;]*[A-NP-Za-df-z])\b", "", clean_resp)
        # Remove common shell prompts
        clean_resp = re.sub(r"(ap|nsh|fl)>\s*$", "", clean_resp, flags=re.MULTILINE)
        clean_resp = clean_resp.strip()

        # First, check for [OK] or [ERR] in the original response (before cleaning)
        # This ensures we don't miss them due to overzealous cleaning
        lines = resp.split("\n")
        for line in reversed(lines):
            line = line.strip()
            if "[OK]" in line:
                # Extract message after [OK]
                idx = line.find("[OK]")
                msg = line[idx + 4 :].strip()
                return {"ok": True, "msg": msg, "raw": resp}
            elif "[ERR]" in line:
                idx = line.find("[ERR]")
                msg = line[idx + 5 :].strip()
                return {"ok": False, "msg": msg, "raw": resp}

        # If no [OK] or [ERR] found, check if response looks successful
        # (some commands may not return explicit status)
        lower_resp = clean_resp.lower()
        if "error" in lower_resp or "fail" in lower_resp or "invalid" in lower_resp:
            return {"ok": False, "msg": clean_resp, "raw": resp}

        # If response is mostly empty or just prompts, assume success
        if not clean_resp or len(clean_resp) < 5:
            return {"ok": True, "msg": "", "raw": resp}

        return {"ok": False, "msg": clean_resp, "raw": resp}

    def _update_slot_state(self, info: dict):
        """
        Update device slot state for frontend push notification.

        This method is called automatically when info() successfully parses
        slot information, enabling the frontend to detect slot changes
        through the /api/logs polling endpoint without explicit requests.

        Args:
            info: Parsed info dictionary containing slot information
        """
        if self.device is None:
            return

        try:
            slots = info.get("slots", [])
            # Check if slots changed
            if slots != self.device.cached_slots:
                self.device.cached_slots = slots.copy()
                self.device.slot_update_id += 1
                self.device.device_info = info  # Also update device_info
                logger.debug(
                    f"Slot state updated (id={self.device.slot_update_id}): "
                    f"{len([s for s in slots if s.get('occupied')])} active slots"
                )
        except Exception as e:
            logger.warning(f"Failed to update slot state: {e}")

    def ping(self) -> Tuple[bool, str]:
        """Ping device."""
        try:
            resp = self._send_cmd("-c ping")
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def test_serial_throughput(
        self, start_size: int = 16, max_size: int = 4096, timeout: float = 2.0
    ) -> Dict:
        """
        Test serial port throughput by sending increasing data sizes.

        Uses x2 stepping to find the maximum single-transfer size the device can handle.
        Sends test data and verifies echo response.

        Args:
            start_size: Starting test size in bytes (default: 16)
            max_size: Maximum test size in bytes (default: 4096)
            timeout: Timeout for each test in seconds (default: 2.0)

        Returns:
            dict with test results:
                - success: bool - True if test completed
                - max_working_size: int - Largest size that worked
                - failed_size: int - First size that failed (0 if all passed)
                - tests: list - Details of each test
                - recommended_chunk_size: int - Recommended safe chunk size
        """
        if self.device is None or self.device.ser is None:
            return {
                "success": False,
                "error": "Serial port not connected",
                "max_working_size": 0,
                "failed_size": 0,
                "tests": [],
                "recommended_chunk_size": 64,
            }

        results = {
            "success": True,
            "max_working_size": 0,
            "failed_size": 0,
            "tests": [],
            "recommended_chunk_size": 64,
        }

        try:
            # Test using x2 stepping
            test_size = start_size
            max_working = 0

            while test_size <= max_size:
                # Create test data: hex pattern of target size
                hex_data = "".join(f"{(i % 256):02X}" for i in range(test_size))

                # Build echo command - use standard format for _send_cmd
                cmd = f"-c echo -d {hex_data}"

                test_result = {
                    "size": test_size,
                    "cmd_len": len(cmd),
                    "passed": False,
                    "error": None,
                    "response_time_ms": 0,
                }

                try:
                    # Use _send_cmd which handles fl mode automatically
                    start_time = time.time()
                    response = self._send_cmd(cmd, timeout=timeout)
                    elapsed_ms = (time.time() - start_time) * 1000
                    test_result["response_time_ms"] = round(elapsed_ms, 2)

                    # Check response and verify CRC
                    if "[OK]" in response:
                        # Parse response: "[OK] ECHO <len> Bytes, CRC 0x<crc>"
                        # Calculate expected CRC (on hex string, not bytes)
                        expected_crc = crc16(hex_data.encode("ascii"))

                        # Extract CRC from response
                        crc_match = re.search(r"0x([0-9A-Fa-f]{4})", response)
                        if crc_match:
                            received_crc = int(crc_match.group(1), 16)
                            if received_crc == expected_crc:
                                test_result["passed"] = True
                                max_working = test_size
                            else:
                                test_result["passed"] = False
                                test_result["error"] = (
                                    f"CRC mismatch: expected 0x{expected_crc:04X}, "
                                    f"got 0x{received_crc:04X}"
                                )
                                results["failed_size"] = test_size
                                results["tests"].append(test_result)
                                break
                        else:
                            # No CRC in response, just check [OK]
                            test_result["passed"] = True
                            max_working = test_size
                    else:
                        test_result["passed"] = False
                        if "[ERR]" in response:
                            test_result["error"] = "Device returned error"
                        elif not response:
                            test_result["error"] = "No response (timeout)"
                        else:
                            test_result["error"] = "Incomplete/invalid response"
                        results["failed_size"] = test_size
                        results["tests"].append(test_result)
                        break

                except Exception as e:
                    test_result["passed"] = False
                    test_result["error"] = str(e)
                    results["failed_size"] = test_size
                    results["tests"].append(test_result)
                    break

                results["tests"].append(test_result)

                # x2 stepping
                test_size *= 2

            results["max_working_size"] = max_working
            # Recommend 75% of max working size for safety margin
            if max_working > 0:
                results["recommended_chunk_size"] = max(64, (max_working * 3) // 4)
            else:
                results["recommended_chunk_size"] = 64

        except Exception as e:
            results["success"] = False
            results["error"] = str(e)

        return results

    def info(self) -> Tuple[Optional[dict], str]:
        """Get device info including slot states."""
        try:
            resp = self._send_cmd("-c info")
            result = self._parse_response(resp)

            if result.get("ok"):
                raw = result.get("raw", "")
                info = {"ok": True, "slots": [], "is_dynamic": False}
                for line in raw.split("\n"):
                    line = line.strip()
                    if line.startswith("Build:"):
                        # Parse: Build: Jan 29 2026 14:30:00
                        info["build_time"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Alloc:"):
                        alloc_type = line.split(":")[1].strip().lower()
                        info["is_dynamic"] = alloc_type == "dynamic"
                    elif line.startswith("Base:"):
                        try:
                            info["base"] = int(line.split(":")[1].strip(), 0)
                        except:
                            pass
                    elif line.startswith("Size:"):
                        try:
                            info["size"] = int(line.split(":")[1].strip())
                        except:
                            pass
                    elif line.startswith("Used:"):
                        try:
                            info["used"] = int(line.split(":")[1].strip())
                        except:
                            pass
                    elif line.startswith("Slots:"):
                        try:
                            parts = line.split(":")[1].strip().split("/")
                            info["active_slots"] = int(parts[0])
                            info["total_slots"] = int(parts[1])
                        except:
                            pass
                    elif line.startswith("Slot["):
                        # Parse: Slot[0]: 0x08001234 -> 0x20001000, 128 bytes
                        # or:    Slot[0]: empty
                        try:
                            match = re.match(
                                r"Slot\[(\d+)\]:\s*(0x[0-9A-Fa-f]+)\s*->\s*(0x[0-9A-Fa-f]+),\s*(\d+)\s*bytes",
                                line,
                            )
                            if match:
                                slot_id = int(match.group(1))
                                orig_addr = int(match.group(2), 16)
                                target_addr = int(match.group(3), 16)
                                code_size = int(match.group(4))
                                info["slots"].append(
                                    {
                                        "id": slot_id,
                                        "occupied": True,
                                        "orig_addr": orig_addr,
                                        "target_addr": target_addr,
                                        "code_size": code_size,
                                    }
                                )
                            elif "empty" in line:
                                match = re.match(r"Slot\[(\d+)\]:", line)
                                if match:
                                    slot_id = int(match.group(1))
                                    info["slots"].append(
                                        {
                                            "id": slot_id,
                                            "occupied": False,
                                            "orig_addr": 0,
                                            "target_addr": 0,
                                            "code_size": 0,
                                        }
                                    )
                        except:
                            pass

                # Auto-update device slot state for frontend push
                self._update_slot_state(info)

                return info, ""
            return None, result.get("msg", "Unknown error")
        except Exception as e:
            return None, str(e)

    def alloc(self, size: int) -> Tuple[Optional[int], str]:
        """Allocate memory buffer."""
        try:
            resp = self._send_cmd(f"-c alloc -s {size}")
            logger.debug(f"Alloc response: {resp}")
            result = self._parse_response(resp)
            logger.debug(f"Alloc parsed result: {result}")
            if result.get("ok"):
                msg = result.get("msg", "")
                match = re.search(r"0x([0-9A-Fa-f]+)", msg)
                if match:
                    base = int(match.group(1), 16)
                    logger.info(f"Alloc successful: size={size}, base=0x{base:08X}")
                    return base, ""
                else:
                    logger.warning(f"Alloc: Could not parse address from msg: {msg}")
            return None, result.get("msg", "Alloc failed")
        except Exception as e:
            logger.exception(f"Alloc exception: {e}")
            return None, str(e)

    def upload(
        self, data: bytes, start_offset: int = 0, progress_callback=None
    ) -> Tuple[bool, dict]:
        """Upload binary data in chunks using base64 encoding."""
        total = len(data)
        data_offset = 0
        bytes_per_chunk = self.device.chunk_size if self.device.chunk_size > 0 else 128

        upload_start = time.time()
        chunk_count = 0
        total_chunks = (total + bytes_per_chunk - 1) // bytes_per_chunk

        while data_offset < total:
            chunk = data[data_offset : data_offset + bytes_per_chunk]
            b64_data = base64.b64encode(chunk).decode("ascii")
            crc = crc16(chunk)

            device_offset = start_offset + data_offset
            cmd = f"-c upload -a 0x{device_offset:X} -d {b64_data} -r 0x{crc:04X}"

            try:
                resp = self._send_cmd(cmd)
                result = self._parse_response(resp)

                if not result.get("ok"):
                    return False, {
                        "error": f"Upload failed at offset 0x{device_offset:X}: {result.get('msg')}"
                    }
            except Exception as e:
                return False, {"error": str(e)}

            data_offset += len(chunk)
            chunk_count += 1

            if progress_callback:
                progress_callback(data_offset, total)

        upload_time = time.time() - upload_start
        speed = total / upload_time if upload_time > 0 else 0

        return True, {
            "bytes": total,
            "chunks": chunk_count,
            "time": upload_time,
            "speed": speed,
        }

    def patch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set FPB patch (direct mode)."""
        try:
            cmd = f"-c patch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
            resp = self._send_cmd(cmd)
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def tpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set trampoline patch."""
        try:
            cmd = f"-c tpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
            resp = self._send_cmd(cmd)
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def dpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set DebugMonitor patch."""
        try:
            cmd = f"-c dpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
            resp = self._send_cmd(cmd)
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def unpatch(self, comp: int = 0, all: bool = False) -> Tuple[bool, str]:
        """Clear FPB patch. If all=True, clear all patches and free memory."""
        try:
            if all:
                cmd = "-c unpatch --all"
            else:
                cmd = f"-c unpatch --comp {comp}"
            resp = self._send_cmd(cmd)
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def find_slot_for_target(self, target_addr: int) -> Tuple[int, bool]:
        """
        Find a suitable slot for the target address.

        Strategy (B - Smart Reuse):
        1. If target_addr is already patched in some slot, reuse that slot
        2. Otherwise find first empty slot
        3. If no empty slot, return -1

        Returns:
            Tuple of (slot_id, needs_unpatch)
            - slot_id: The slot to use, or -1 if no slot available
            - needs_unpatch: True if the slot needs to be cleared first
        """
        info, error = self.info()
        if error or not info:
            return 0, False  # Default to slot 0 if can't get info

        slots = info.get("slots", [])
        first_empty = -1

        for slot in slots:
            slot_id = slot.get("id", -1)
            occupied = slot.get("occupied", False)
            orig_addr = slot.get("orig_addr", 0)

            if occupied:
                # Check if this slot already patches our target
                if orig_addr == target_addr or orig_addr == (target_addr & ~1):
                    return slot_id, True  # Reuse this slot, need to unpatch first
            else:
                if first_empty < 0:
                    first_empty = slot_id

        if first_empty >= 0:
            return first_empty, False

        return -1, False  # No slot available

    def get_elf_build_time(self, elf_path: str) -> Optional[str]:
        """Get build time from ELF file.

        Searches for __DATE__ and __TIME__ strings embedded in the binary.
        These are typically compiled into the firmware when using the macros.

        Returns:
            Build time string in format "Mon DD YYYY HH:MM:SS" or None if not found
        """
        if not elf_path or not os.path.exists(elf_path):
            return None

        try:
            # Use strings command to extract printable strings from ELF
            result = subprocess.run(
                ["strings", "-a", elf_path], capture_output=True, text=True, timeout=60
            )

            if result.returncode != 0:
                return None

            # __DATE__ format: "Jan 29 2026" (month day year)
            # __TIME__ format: "14:30:00" (HH:MM:SS)
            date_pattern = (
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{4}"
            )
            time_pattern = r"\d{2}:\d{2}:\d{2}"

            lines = result.stdout.split("\n")

            # Strategy 1: Look for "FPBInject" marker and find date/time nearby
            for i, line in enumerate(lines):
                if "FPBInject" in line and "v1.0" in line:
                    # Search in a window around this line
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

    def get_symbols(self, elf_path: str) -> Dict[str, int]:
        """Extract symbols from ELF file.

        Returns a dictionary with both mangled and demangled names pointing to addresses.
        For C++ symbols, the mangled name (e.g., _ZN5Print5printEPKc) and demangled name
        (e.g., Print::print) are both included.
        """
        symbols = {}
        try:
            nm_tool = self.get_tool_path("arm-none-eabi-nm")
            env = self._get_subprocess_env()

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
                        # Join all parts after type to get full demangled name
                        full_name = " ".join(parts[2:])
                        # Also extract just the function name (before parentheses)
                        if "(" in full_name:
                            short_name = full_name.split("(")[0]
                            symbols[short_name] = addr
                        symbols[full_name] = addr
                    except ValueError:
                        pass
        except Exception as e:
            logger.error(f"Error reading symbols: {e}")
        return symbols

    def disassemble_function(self, elf_path: str, func_name: str) -> Tuple[bool, str]:
        """Disassemble a specific function from ELF file."""
        try:
            objdump_tool = self.get_tool_path("arm-none-eabi-objdump")
            env = self._get_subprocess_env()

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
                # Detect function start - look for address followed by function name
                # Format: "0000000 <func_name>:" at the start of line
                if f"<{func_name}" in line and ">:" in line:
                    # Make sure it's actually a function definition, not a call target
                    # Function definitions start with address at beginning of line
                    stripped = line.strip()
                    if stripped and stripped[0].isalnum():
                        in_function = True
                        disasm_lines.append(line)
                        empty_line_count = 0
                        continue

                if in_function:
                    # Track consecutive empty lines
                    if not line.strip():
                        empty_line_count += 1
                        # Two consecutive empty lines usually means end of function
                        if empty_line_count >= 2:
                            break
                        continue

                    # Reset empty line counter on non-empty line
                    empty_line_count = 0

                    # Check if a new function started (line starts with address and has <>:)
                    stripped = line.strip()
                    if (
                        stripped
                        and stripped[0].isalnum()
                        and ":" in stripped
                        and "<" in stripped
                        and ">:" in stripped
                    ):
                        # New function definition started
                        break
                    else:
                        disasm_lines.append(line)

            if not disasm_lines:
                return False, f"Could not extract disassembly for '{func_name}'"

            # Filter out empty section headers (e.g., "Disassembly of section .trampoline:")
            # Keep only the actual function disassembly
            filtered_lines = []
            for line in disasm_lines:
                # Skip empty section headers that appear after the function
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

    def decompile_function(self, elf_path: str, func_name: str) -> Tuple[bool, str]:
        """
        Decompile a specific function from ELF file using angr.

        Args:
            elf_path: Path to ELF file
            func_name: Name of the function to decompile

        Returns:
            Tuple of (success, decompiled_code or error_message)
        """
        try:
            import angr
            from angr.analyses.decompiler.structured_codegen import (
                DummyStructuredCodeGenerator,
            )
        except ImportError:
            return False, "ANGR_NOT_INSTALLED"

        # Suppress noisy angr logs (e.g., unsupported ARM CCall warnings)
        import logging as angr_logging

        for name in [
            "angr",
            "cle",
            "pyvex",
            "angr.analyses.calling_convention",
        ]:
            angr_logging.getLogger(name).setLevel(angr_logging.CRITICAL)

        try:
            # Load the ELF file with angr
            # auto_load_libs=False to avoid loading system libraries
            proj = angr.Project(elf_path, auto_load_libs=False)

            # Find the function symbol
            func_symbol = proj.loader.find_symbol(func_name)
            if not func_symbol:
                # Try with underscore prefix (common in C)
                func_symbol = proj.loader.find_symbol(f"_{func_name}")

            if not func_symbol:
                return False, f"Function '{func_name}' not found in ELF"

            # Get the CFG (Control Flow Graph)
            cfg = proj.analyses.CFGFast(normalize=True, data_references=True)

            # Find the function in CFG
            func_addr = func_symbol.rebased_addr
            func = cfg.kb.functions.get(func_addr)

            if not func:
                # Try to find by name in knowledge base
                for f in cfg.kb.functions.values():
                    if f.name == func_name or f.name == f"_{func_name}":
                        func = f
                        break

            if not func:
                return False, f"Could not analyze function '{func_name}'"

            # Decompile the function
            try:
                dec = proj.analyses.Decompiler(func, cfg=cfg)

                if dec.codegen is None or isinstance(
                    dec.codegen, DummyStructuredCodeGenerator
                ):
                    return False, f"Could not decompile '{func_name}' - analysis failed"

                decompiled = dec.codegen.text

                if not decompiled or not decompiled.strip():
                    return (
                        False,
                        f"Decompilation produced empty output for '{func_name}'",
                    )

                # Add header comment
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

    def get_signature(self, elf_path: str, func_name: str) -> Optional[str]:
        """
        Get function signature from ELF file using DWARF debug info.

        Args:
            elf_path: Path to ELF file
            func_name: Name of the function

        Returns:
            Function signature string or None if not found
        """
        try:
            # First try using nm to get demangled name (for C++)
            nm_tool = self.get_tool_path("arm-none-eabi-nm")
            env = self._get_subprocess_env()

            result = subprocess.run(
                [nm_tool, "-C", elf_path],
                capture_output=True,
                text=True,
                env=env,
            )

            # Search for function in demangled output
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    name = " ".join(parts[2:])  # Name might have spaces in C++
                    if func_name in name:
                        # If it has parentheses, it's likely a signature
                        if "(" in name:
                            return name
                        # Otherwise return basic name
                        return name

            # Fallback: try to get signature from readelf debug info
            readelf_tool = self.get_tool_path("arm-none-eabi-readelf")
            result = subprocess.run(
                [readelf_tool, "--debug-dump=info", elf_path],
                capture_output=True,
                text=True,
                env=env,
            )

            # Parse DWARF info for function (simplified)
            in_function = False
            for line in result.stdout.splitlines():
                if "DW_AT_name" in line and func_name in line:
                    in_function = True
                elif in_function and "DW_AT_type" in line:
                    # Found type info - return basic signature
                    return f"{func_name}()"

            # If nothing found, return just the name
            return func_name

        except Exception as e:
            logger.debug(f"Could not get signature for {func_name}: {e}")
            return func_name

    def parse_dep_file_for_compile_command(
        self,
        source_file: str,
        build_output_dir: str = None,
    ) -> Optional[str]:
        """
        Parse .d dependency file to extract the original compile command.

        vendor/bes build system stores compile commands in .d files with format:
        cmd_<path>/<file>.o := <full compile command>

        Args:
            source_file: Path to the source file
            build_output_dir: Optional build output directory to search for .d files

        Returns:
            The compile command string if found, None otherwise
        """
        import subprocess

        if not source_file:
            return None

        source_file = os.path.normpath(source_file)
        source_basename = os.path.basename(source_file)
        source_name_no_ext = os.path.splitext(source_basename)[0]

        # Determine search directories
        search_dirs = []
        if build_output_dir:
            search_dirs.append(build_output_dir)

        # Also search in common build output locations
        workspace_root = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    )
                )
            )
        )

        # Search for .d files in out directory
        out_dir = os.path.join(workspace_root, "out")
        if os.path.isdir(out_dir):
            search_dirs.append(out_dir)

        # Look for .d file with matching name
        dep_file_pattern = f".{source_name_no_ext}.o.d"

        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue

            # Use find command for faster search (much faster than os.walk for large directories)
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

                        # Read and parse the .d file
                        try:
                            with open(dep_file_path, "r") as df:
                                content = df.read()

                            # Check if this .d file is for our source file
                            if source_file in content or source_basename in content:
                                # Look for cmd_xxx := pattern
                                for line in content.split("\n"):
                                    if line.startswith("cmd_") and ":=" in line:
                                        # Extract the command after :=
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
                # Fallback to os.walk if find command fails
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
                                                compile_cmd = line[
                                                    cmd_start + 2 :
                                                ].strip()
                                                logger.info(
                                                    f"Found compile command in .d file: {dep_file_path}"
                                                )
                                                return compile_cmd
                            except Exception as e2:
                                logger.debug(
                                    f"Error reading .d file {dep_file_path}: {e2}"
                                )
                                continue

        return None

    def parse_compile_commands(
        self,
        compile_commands_path: str,
        source_file: str = None,
        verbose: bool = False,
    ) -> Optional[Dict]:
        """
        Parse standard CMake compile_commands.json to extract compiler flags.

        Args:
            compile_commands_path: Path to compile_commands.json
            source_file: Optional source file path to match for specific compile flags
            verbose: Enable verbose output
        """
        import json
        import shlex

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

        # Standard CMake compile_commands.json format: [{directory, command, file}, ...]
        if not isinstance(commands, list):
            logger.error(
                f"Invalid compile_commands.json format: expected array, got {type(commands).__name__}. "
                "Please use standard CMake compile_commands.json (set CMAKE_EXPORT_COMPILE_COMMANDS=ON)"
            )
            return None

        # Find a suitable entry - prioritize matching source_file if provided
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
                    logger.info(
                        f"Found exact match in compile_commands.json: {file_path}"
                    )
                    break

        # Second pass: try to find a file in the same directory or parent directories
        if not selected_entry and source_file:
            source_dir = os.path.dirname(os.path.normpath(source_file))
            # Try to find files in the same directory tree (up to 3 levels up)
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
                    # Check if the file is in the same directory tree
                    if file_dir.startswith(search_dir) or search_dir.startswith(
                        file_dir
                    ):
                        selected_entry = entry
                        logger.info(
                            f"Found related file in compile_commands.json: {file_path} (same directory tree as {source_file})"
                        )
                        break
                if selected_entry:
                    break

        # Third pass: try to find compile command from .d dependency file (vendor/bes build system)
        dep_file_command = None
        if not selected_entry and source_file:
            build_output_dir = os.path.dirname(compile_commands_path)
            dep_file_command = self.parse_dep_file_for_compile_command(
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
                        f"Using fallback compile command from: {file_path} (source file not found in compile_commands.json)"
                    )
                    break

        if not selected_entry and not dep_file_command:
            logger.error("No suitable C file entry found in compile_commands.json")
            return None

        # Use dep_file_command if available, otherwise use selected_entry
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

            # Handle -U (undefine) options - keep all of them for type consistency
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
                for p in [
                    "-mthumb",
                    "-mcpu",
                    "-mtune",
                    "-march",
                    "-mfpu",
                    "-mfloat-abi",
                ]
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
        # This helps resolve headers that use angle brackets but are in the same directory tree
        if source_file and os.path.exists(source_file):
            source_dir = os.path.dirname(os.path.abspath(source_file))
            # Add source directory and up to 3 parent directories
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
        objcopy = (
            os.path.join(compiler_dir, objcopy_name) if compiler_dir else objcopy_name
        )

        return {
            "compiler": compiler,
            "objcopy": objcopy,
            "includes": includes,
            "defines": defines,
            "cflags": cflags,
            "ldflags": [],
            "raw_command": dep_file_command,  # Pass through raw command from .d file
        }

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

        Returns:
            Tuple of (binary_data, symbols, error_message)
        """
        logger.info(
            f"compile_inject called with original_source_file={original_source_file}"
        )
        config = None
        if compile_commands_path:
            config = self.parse_compile_commands(
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
            compiler = self.get_tool_path(compiler)
        if not os.path.isabs(objcopy):
            objcopy = self.get_tool_path(objcopy)

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
            env = self._get_subprocess_env()
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
            subprocess.run(
                [objcopy, "-O", "binary", elf_file, bin_file], check=True, env=env
            )

            # Read binary
            with open(bin_file, "rb") as f:
                data = f.read()

            # Fix Thumb bit in veneer addresses
            # When using --just-symbols, the linker generates veneers for long calls
            # but doesn't set the Thumb bit (bit 0) for Thumb functions.
            # Veneer pattern: LDR PC, [PC, #0] followed by 4-byte address
            # Machine code: F8 5F F0 00 (ldr.w pc, [pc]) followed by address
            data = self._fix_veneer_thumb_bits(data, base_addr, elf_path, verbose)

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
        """
        Inject a single function (internal helper).

        This uploads code and applies patch for ONE function.
        Used by inject() for multi-function injection.

        Args:
            target_addr: Target function address
            inject_addr: Inject function address in compiled code
            inject_name: Name of inject function
            data: Compiled binary data
            align_offset: Alignment offset for upload
            patch_mode: Patch mode (trampoline, debugmon, direct)
            comp: FPB comparator index (auto-select if -1)
            progress_callback: Progress callback function

        Returns:
            Tuple of (success, result_dict)
        """
        result = {
            "target_addr": f"0x{target_addr:08X}",
            "inject_func": inject_name,
            "inject_addr": f"0x{inject_addr:08X}",
            "slot": -1,
        }

        # Auto-select slot if comp == -1
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

        # Upload code
        upload_start = align_offset
        success, upload_result = self.upload(
            data, start_offset=upload_start, progress_callback=progress_callback
        )
        if not success:
            return False, {"error": upload_result.get("error", "Upload failed")}

        result["upload_time"] = round(upload_result.get("time", 0), 2)

        # Apply patch
        patch_addr = inject_addr | 1  # Thumb address

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
        """
        Perform full injection workflow.

        Args:
            source_content: Patch source code content
            target_func: Target function name to replace
            inject_func: Inject function name (default: auto-detect)
            patch_mode: Patch mode (trampoline, debugmon, direct)
            comp: FPB comparator index, -1 for auto-select (default)
            progress_callback: Progress callback function
            source_ext: Source file extension (.c or .cpp)
            original_source_file: Path to original source file for matching compile flags

        Returns:
            Tuple of (success, result_dict)
        """
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

        # Load ELF symbols
        elf_path = self.device.elf_path
        if not elf_path or not os.path.exists(elf_path):
            return False, {"error": "ELF file not found"}

        symbols = self.get_symbols(elf_path)
        if target_func not in symbols:
            return False, {"error": f"Target function '{target_func}' not found in ELF"}

        target_addr = symbols[target_func]
        result["target_addr"] = f"0x{target_addr:08X}"

        # Auto-select slot for this target
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

        # Get device info
        info, error = self.info()
        if error:
            return False, {"error": f"Failed to get device info: {error}"}

        is_dynamic = info and info.get("is_dynamic", False)

        compile_start = time.time()

        if is_dynamic:
            # Dynamic allocation: compile first to get size
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
                return False, {
                    "error": f"Alloc failed: {error or 'No address returned'}"
                }

            aligned_addr = (raw_addr + 7) & ~7
            align_offset = aligned_addr - raw_addr
            base_addr = aligned_addr

            # Recompile with aligned address
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
        else:
            base_addr = info.get("base", 0x20001000) if info else 0x20001000
            align_offset = 0

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

        # Find inject function
        found_inject_func = None
        if inject_func:
            for name, addr in inject_symbols.items():
                if inject_func in name:
                    found_inject_func = (name, addr)
                    break
        else:
            target_lower = target_func.lower()
            for name, addr in inject_symbols.items():
                name_lower = name.lower()
                if name_lower.startswith("inject_") and target_lower in name_lower:
                    found_inject_func = (name, addr)
                    break

            if not found_inject_func:
                inject_funcs = [
                    (n, a) for n, a in inject_symbols.items() if n.startswith("inject_")
                ]
                if inject_funcs:
                    found_inject_func = min(inject_funcs, key=lambda x: x[1])

        if not found_inject_func:
            return False, {"error": "No inject_* function found in source"}

        result["inject_func"] = found_inject_func[0]
        result["inject_addr"] = f"0x{found_inject_func[1]:08X}"

        # Upload code
        # --addr is always offset: dynamic mode uses align_offset, static mode uses 0
        # Lower machine adds offset to last_alloc (dynamic) or static_buf (static)
        upload_start = align_offset
        success, upload_result = self.upload(
            data, start_offset=upload_start, progress_callback=progress_callback
        )
        if not success:
            return False, {"error": upload_result.get("error", "Upload failed")}

        result["upload_time"] = round(upload_result.get("time", 0), 2)

        # Apply patch using auto-selected slot
        patch_addr = found_inject_func[1] | 1  # Thumb address

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

        # Update device state
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

        Args:
            source_content: Patch source code content with multiple inject_* functions
            patch_mode: Patch mode (trampoline, debugmon, direct)
            progress_callback: Progress callback function
            source_ext: Source file extension (.c or .cpp)
            original_source_file: Path to original source file for matching compile flags

        Returns:
            Tuple of (success, result_dict)
        """
        result = {
            "compile_time": 0,
            "upload_time": 0,
            "total_time": 0,
            "code_size": 0,
            "injections": [],  # List of individual injection results
            "errors": [],
        }

        total_start = time.time()

        # Load ELF symbols
        elf_path = self.device.elf_path
        if not elf_path or not os.path.exists(elf_path):
            return False, {"error": "ELF file not found"}

        elf_symbols = self.get_symbols(elf_path)

        # First, do a quick compile to find all inject_* functions
        data, inject_symbols, error = self.compile_inject(
            source_content,
            0x20000000,  # Temporary base address
            elf_path,
            self.device.compile_commands_path,
            source_ext=source_ext,
            original_source_file=original_source_file,
        )
        if error:
            return False, {"error": error}

        # Find all inject_* functions and their target mappings
        inject_funcs = [
            (n, a) for n, a in inject_symbols.items() if n.startswith("inject_")
        ]

        if not inject_funcs:
            return False, {"error": "No inject_* functions found in source"}

        # Sort by address for consistent ordering
        inject_funcs.sort(key=lambda x: x[1])

        logger.info(
            f"Found {len(inject_funcs)} inject functions: {[f[0] for f in inject_funcs]}"
        )

        # Build list of (target_func, inject_func) pairs
        injection_targets = []
        for inject_name, _ in inject_funcs:
            target_func = inject_name[7:]  # Remove "inject_" prefix

            # Try to find target in ELF symbols (case-insensitive match)
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

        # Now inject each function independently using the existing inject() method
        # Each function gets its own alloc -> compile -> upload -> patch cycle
        total_compile_time = 0
        total_upload_time = 0
        total_code_size = 0

        for target_func, inject_func in injection_targets:
            logger.info(f"Injecting {target_func} -> {inject_func}")

            # Use inject() for complete independent injection
            # comp=-1 means auto-select slot with smart reuse
            success, inj_result = self.inject(
                source_content=source_content,
                target_func=target_func,
                inject_func=inject_func,
                patch_mode=patch_mode,
                comp=-1,  # Auto-select slot
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

        # Count successful injections
        successful = sum(1 for inj in result["injections"] if inj.get("success", False))
        result["successful_count"] = successful
        result["total_count"] = len(injection_targets)

        # Update device state
        if successful > 0:
            self.device.inject_active = True
            self.device.last_inject_time = time.time()

        return successful > 0, result


def scan_serial_ports() -> List[dict]:
    """Scan for available serial ports."""
    import glob

    ports = serial.tools.list_ports.comports()
    result = [
        {"device": port.device, "description": port.description} for port in ports
    ]

    # Also scan for CH341 USB serial devices
    ch341_devices = glob.glob("/dev/ttyCH341USB*")
    existing_devices = {item["device"] for item in result}
    for dev in ch341_devices:
        if dev not in existing_devices:
            result.append({"device": dev, "description": "CH341 USB Serial"})

    return result


def serial_open(port: str, baudrate: int = 115200, timeout: float = 2.0):
    """Open a serial port."""
    try:
        ser = serial.Serial(port, baudrate, timeout=timeout, write_timeout=timeout)
        if not ser.isOpen():
            return None, f"Error opening serial port {port}"
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.1)
        return ser, None
    except serial.SerialException as e:
        return None, f"Serial error: {e}"
    except Exception as e:
        return None, f"Error: {e}"
