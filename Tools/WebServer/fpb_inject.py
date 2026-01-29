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
import time
from typing import Dict, List, Optional, Tuple

import serial
import serial.tools.list_ports

from utils.crc import crc16
from utils.serial import scan_serial_ports, serial_open
from core import elf_utils
from core import compiler as compiler_utils

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
        """Fix Thumb bit in linker-generated veneer addresses."""
        return compiler_utils.fix_veneer_thumb_bits(
            data, base_addr, elf_path, self._toolchain_path, verbose
        )

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

    def parse_dep_file_for_compile_command(
        self,
        source_file: str,
        build_output_dir: str = None,
    ) -> Optional[str]:
        """Parse .d dependency file to extract the original compile command."""
        return compiler_utils.parse_dep_file_for_compile_command(
            source_file, build_output_dir
        )

    def parse_compile_commands(
        self,
        compile_commands_path: str,
        source_file: str = None,
        verbose: bool = False,
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
