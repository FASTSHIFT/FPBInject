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

# CRC-16-CCITT Table
CRC16_TABLE = [
    0x0000,
    0x1021,
    0x2042,
    0x3063,
    0x4084,
    0x50A5,
    0x60C6,
    0x70E7,
    0x8108,
    0x9129,
    0xA14A,
    0xB16B,
    0xC18C,
    0xD1AD,
    0xE1CE,
    0xF1EF,
    0x1231,
    0x0210,
    0x3273,
    0x2252,
    0x52B5,
    0x4294,
    0x72F7,
    0x62D6,
    0x9339,
    0x8318,
    0xB37B,
    0xA35A,
    0xD3BD,
    0xC39C,
    0xF3FF,
    0xE3DE,
    0x2462,
    0x3443,
    0x0420,
    0x1401,
    0x64E6,
    0x74C7,
    0x44A4,
    0x5485,
    0xA56A,
    0xB54B,
    0x8528,
    0x9509,
    0xE5EE,
    0xF5CF,
    0xC5AC,
    0xD58D,
    0x3653,
    0x2672,
    0x1611,
    0x0630,
    0x76D7,
    0x66F6,
    0x5695,
    0x46B4,
    0xB75B,
    0xA77A,
    0x9719,
    0x8738,
    0xF7DF,
    0xE7FE,
    0xD79D,
    0xC7BC,
    0x48C4,
    0x58E5,
    0x6886,
    0x78A7,
    0x0840,
    0x1861,
    0x2802,
    0x3823,
    0xC9CC,
    0xD9ED,
    0xE98E,
    0xF9AF,
    0x8948,
    0x9969,
    0xA90A,
    0xB92B,
    0x5AF5,
    0x4AD4,
    0x7AB7,
    0x6A96,
    0x1A71,
    0x0A50,
    0x3A33,
    0x2A12,
    0xDBFD,
    0xCBDC,
    0xFBBF,
    0xEB9E,
    0x9B79,
    0x8B58,
    0xBB3B,
    0xAB1A,
    0x6CA6,
    0x7C87,
    0x4CE4,
    0x5CC5,
    0x2C22,
    0x3C03,
    0x0C60,
    0x1C41,
    0xEDAE,
    0xFD8F,
    0xCDEC,
    0xDDCD,
    0xAD2A,
    0xBD0B,
    0x8D68,
    0x9D49,
    0x7E97,
    0x6EB6,
    0x5ED5,
    0x4EF4,
    0x3E13,
    0x2E32,
    0x1E51,
    0x0E70,
    0xFF9F,
    0xEFBE,
    0xDFDD,
    0xCFFC,
    0xBF1B,
    0xAF3A,
    0x9F59,
    0x8F78,
    0x9188,
    0x81A9,
    0xB1CA,
    0xA1EB,
    0xD10C,
    0xC12D,
    0xF14E,
    0xE16F,
    0x1080,
    0x00A1,
    0x30C2,
    0x20E3,
    0x5004,
    0x4025,
    0x7046,
    0x6067,
    0x83B9,
    0x9398,
    0xA3FB,
    0xB3DA,
    0xC33D,
    0xD31C,
    0xE37F,
    0xF35E,
    0x02B1,
    0x1290,
    0x22F3,
    0x32D2,
    0x4235,
    0x5214,
    0x6277,
    0x7256,
    0xB5EA,
    0xA5CB,
    0x95A8,
    0x8589,
    0xF56E,
    0xE54F,
    0xD52C,
    0xC50D,
    0x34E2,
    0x24C3,
    0x14A0,
    0x0481,
    0x7466,
    0x6447,
    0x5424,
    0x4405,
    0xA7DB,
    0xB7FA,
    0x8799,
    0x97B8,
    0xE75F,
    0xF77E,
    0xC71D,
    0xD73C,
    0x26D3,
    0x36F2,
    0x0691,
    0x16B0,
    0x6657,
    0x7676,
    0x4615,
    0x5634,
    0xD94C,
    0xC96D,
    0xF90E,
    0xE92F,
    0x99C8,
    0x89E9,
    0xB98A,
    0xA9AB,
    0x5844,
    0x4865,
    0x7806,
    0x6827,
    0x18C0,
    0x08E1,
    0x3882,
    0x28A3,
    0xCB7D,
    0xDB5C,
    0xEB3F,
    0xFB1E,
    0x8BF9,
    0x9BD8,
    0xABBB,
    0xBB9A,
    0x4A75,
    0x5A54,
    0x6A37,
    0x7A16,
    0x0AF1,
    0x1AD0,
    0x2AB3,
    0x3A92,
    0xFD2E,
    0xED0F,
    0xDD6C,
    0xCD4D,
    0xBDAA,
    0xAD8B,
    0x9DE8,
    0x8DC9,
    0x7C26,
    0x6C07,
    0x5C64,
    0x4C45,
    0x3CA2,
    0x2C83,
    0x1CE0,
    0x0CC1,
    0xEF1F,
    0xFF3E,
    0xCF5D,
    0xDF7C,
    0xAF9B,
    0xBFBA,
    0x8FD9,
    0x9FF8,
    0x6E17,
    0x7E36,
    0x4E55,
    0x5E74,
    0x2E93,
    0x3EB2,
    0x0ED1,
    0x1EF0,
]


def crc16(data: bytes) -> int:
    """Calculate CRC-16-CCITT checksum."""
    crc = 0xFFFF
    for byte in data:
        crc = ((crc << 8) ^ CRC16_TABLE[(crc >> 8) ^ byte]) & 0xFFFF
    return crc


logger = logging.getLogger(__name__)


class FPBInjectError(Exception):
    """Exception for FPB inject operations."""

    pass


class FPBInject:
    """FPB Inject operations manager."""

    def __init__(self, device_state):
        self.device = device_state
        self._toolchain_path = None

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

    def enter_fl_mode(self, timeout: float = 1.0) -> bool:
        """Enter fl interactive mode by sending 'fl' command.

        Returns True if we entered fl interactive mode (fl> prompt detected),
        False if not needed (bare-metal mode or no response).
        """
        ser = self.device.ser
        if not ser:
            self._in_fl_mode = False
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
                    if "fl>" in response or "[OK]" in response:
                        break
                time.sleep(0.01)

            self._log_raw("RX", response.strip())
            logger.debug(f"Entered fl mode: {response.strip()}")

            # Check if we actually entered fl interactive mode (has fl> prompt)
            self._in_fl_mode = "fl>" in response
            return self._in_fl_mode
        except Exception as e:
            logger.error(f"Error entering fl mode: {e}")
            self._in_fl_mode = False
            return False

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

            # Send command
            ser.write((full_cmd + "\n").encode())
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
                # Not in fl mode - handle separately
                break
            else:
                # No valid response marker, might be interrupted by logs
                logger.warning(f"No valid response marker ([OK]/[ERR]), retrying...")
                self._log_raw("WARN", "No response marker, retrying...")
                continue  # Retry

        # Check if we got "Missing --cmd" which means we're not in fl mode
        if retry_on_missing_cmd and "Missing --cmd" in last_response:
            logger.info("Detected 'Missing --cmd', entering fl mode and retrying...")
            self._log_raw("INFO", "Not in fl mode, entering...")
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
        if "--cmd read" in cmd or "--cmd info" in cmd:
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
            resp = self._send_cmd("--cmd ping")
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def info(self) -> Tuple[Optional[dict], str]:
        """Get device info including slot states."""
        try:
            resp = self._send_cmd("--cmd info")
            result = self._parse_response(resp)

            if result.get("ok"):
                raw = result.get("raw", "")
                info = {"ok": True, "slots": [], "is_dynamic": False}
                for line in raw.split("\n"):
                    line = line.strip()
                    if line.startswith("Alloc:"):
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
            resp = self._send_cmd(f"--cmd alloc --size {size}")
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
            cmd = f"--cmd upload --addr 0x{device_offset:X} --data {b64_data} --crc 0x{crc:04X}"

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
            cmd = f"--cmd patch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
            resp = self._send_cmd(cmd)
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def tpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set trampoline patch."""
        try:
            cmd = f"--cmd tpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
            resp = self._send_cmd(cmd)
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def dpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set DebugMonitor patch."""
        try:
            cmd = f"--cmd dpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
            resp = self._send_cmd(cmd)
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def unpatch(self, comp: int = 0, all: bool = False) -> Tuple[bool, str]:
        """Clear FPB patch. If all=True, clear all patches and free memory."""
        try:
            if all:
                cmd = "--cmd unpatch --all"
            else:
                cmd = f"--cmd unpatch --comp {comp}"
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

    def get_symbols(self, elf_path: str) -> Dict[str, int]:
        """Extract symbols from ELF file."""
        symbols = {}
        try:
            nm_tool = self.get_tool_path("arm-none-eabi-nm")
            env = self._get_subprocess_env()
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
                    addr = int(parts[0], 16)
                    name = parts[2]
                    symbols[name] = addr
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

        # Second pass: fallback to any C file
        if not selected_entry:
            for entry in commands:
                if not isinstance(entry, dict):
                    continue
                file_path = entry.get("file", "")
                if file_path.endswith(".c") and "__ASSEMBLY__" not in entry.get(
                    "command", ""
                ):
                    selected_entry = entry
                    break

        if not selected_entry:
            logger.error("No suitable C file entry found in compile_commands.json")
            return None

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

            if token == "-D" and i + 1 < len(tokens):
                defines.append(tokens[i + 1])
                i += 2
                continue
            elif token.startswith("-D"):
                defines.append(token[2:])
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

            # Compile to object with -ffunction-sections for gc-sections to work
            cmd = [compiler] + cflags + ["-c", "-ffunction-sections", "-fdata-sections"]

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
