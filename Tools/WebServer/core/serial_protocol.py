#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Serial protocol for FPB Inject communication.

Provides low-level serial communication with FPB loader firmware.
"""

import base64
import logging
import re
import struct
import time
from enum import Enum
from typing import Dict, Optional, Tuple

from utils.crc import crc16, crc16_update
from core.state import tool_log

logger = logging.getLogger(__name__)


class Platform(Enum):
    """Platform types for FPB communication."""

    UNKNOWN = "unknown"
    NUTTX = "nuttx"
    BARE_METAL = "bare-metal"


class LogDirection(Enum):
    """Direction for serial log entries."""

    TX = "TX"
    RX = "RX"


class FPBProtocolError(Exception):
    """Exception for FPB protocol operations."""

    pass


class FPBProtocol:
    """FPB serial protocol handler."""

    def __init__(self, device_state):
        """Initialize FPB protocol handler."""
        self.device = device_state
        self._in_fl_mode = False
        self._platform = Platform.UNKNOWN

    def get_platform(self) -> Platform:
        """Get detected platform type."""
        return self._platform

    def try_enter_fl_mode(self, timeout: float = 0.5) -> bool:
        """Try to enter fl interactive mode if not already in it."""
        if self._in_fl_mode:
            logger.debug("Already in fl mode, skipping enter_fl_mode")
            return True

        if self._platform == Platform.BARE_METAL:
            logger.debug("Bare Metal platform, skipping enter_fl_mode")
            return True

        return self.enter_fl_mode(timeout)

    def wakeup_shell(self, cnt: int):
        """Wake up shell by sending newlines to trigger any pending output."""
        newline = b"\n"
        for _ in range(cnt):
            self.device.ser.write(newline)
            self.device.ser.flush()
            time.sleep(0.05)

    def enter_fl_mode(self, timeout: float = 0.5) -> bool:
        """Enter fl interactive mode by sending 'fl' command."""
        ser = self.device.ser
        if not ser:
            self._in_fl_mode = False
            self._platform = Platform.UNKNOWN
            return False

        # If already in fl mode, just return
        if self._in_fl_mode:
            return True

        try:
            self._log_raw(LogDirection.TX, "fl")
            ser.reset_input_buffer()

            self.wakeup_shell(getattr(self.device, "wakeup_shell_cnt", 0))

            # Send 'fl' command to enter interactive mode
            ser.write(b"fl\n")
            ser.flush()

            start = time.time()
            response = ""
            while time.time() - start < timeout:
                time.sleep(0.05)
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                    response += chunk
                    if (
                        "fl>" in response
                        or "[FLOK]" in response
                        or "[FLERR]" in response
                    ):
                        break

            self._log_raw(LogDirection.RX, response.strip())
            logger.debug(f"Entered fl mode: {response.strip()}")

            if "fl>" in response:
                self._in_fl_mode = True
                self._platform = Platform.NUTTX
                logger.info("Detected NuttX platform (fl interactive mode)")
                return True
            elif "Enter" in response and "interactive mode" in response:
                self._platform = Platform.NUTTX
                logger.info("Detected NuttX platform (requires interactive mode)")
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
                self._in_fl_mode = False
                self._platform = Platform.BARE_METAL
                return False
        except Exception as e:
            logger.error(f"Error entering fl mode: {e}")
            self._in_fl_mode = False
            self._platform = Platform.UNKNOWN
            return False

    def exit_fl_mode(self, timeout: float = 0.3) -> bool:
        """Exit fl interactive mode by sending 'exit' command."""
        if not self._in_fl_mode:
            logger.debug("Not in fl mode, skipping exit")
            return True

        ser = self.device.ser
        if not ser:
            return False

        try:
            self._log_raw(LogDirection.TX, "exit")
            ser.write(b"exit\n")
            ser.flush()
            self._in_fl_mode = False
            return True
        except Exception as e:
            logger.error(f"Error exiting fl mode: {e}")
            return False

    def send_cmd(
        self,
        cmd: str,
        timeout: float = 0.5,
        retry_on_missing_cmd: bool = True,
        max_retries: int = 3,
    ) -> str:
        """Send command and get response with automatic retry."""
        ser = self.device.ser
        if not ser:
            raise FPBProtocolError("Serial port not connected")

        self.try_enter_fl_mode()

        full_cmd = f"fl {cmd}" if not cmd.strip().startswith("fl ") else cmd

        last_response = ""
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.warning(
                    f"Retry {attempt}/{max_retries} for command: {cmd[:50]}..."
                )
                tool_log(
                    self.device,
                    "WARN",
                    f"Retry attempt {attempt}/{max_retries}",
                )
                time.sleep(0.05)

            logger.debug(f"TX: {full_cmd}")
            self._log_raw(LogDirection.TX, full_cmd)

            ser.reset_input_buffer()

            data_bytes = (full_cmd + "\n").encode()
            tx_fragment_size = getattr(self.device, "serial_tx_fragment_size", 0)
            tx_fragment_delay = getattr(self.device, "serial_tx_fragment_delay", 0.002)
            if tx_fragment_size > 0 and len(data_bytes) > tx_fragment_size:
                for i in range(0, len(data_bytes), tx_fragment_size):
                    chunk = data_bytes[i : i + tx_fragment_size]
                    ser.write(chunk)
                    ser.flush()
                    if i + tx_fragment_size < len(data_bytes):
                        time.sleep(tx_fragment_delay)
            else:
                ser.write(data_bytes)
            ser.flush()

            response = ""
            start = time.time()
            while time.time() - start < timeout:
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                    response += chunk
                    # Check for explicit end marker first (fast path)
                    if "[FLEND]" in response:
                        break
                else:
                    # Wait a bit before checking again
                    time.sleep(0.0001)

            # Log raw response first (with [FLEND] marker)
            response = response.strip()
            logger.debug(f"RX: {response}")
            self._log_raw(LogDirection.RX, response)

            # Remove [FLEND] marker from response for processing
            response = response.replace("[FLEND]", "").strip()
            last_response = response

            if "[FLOK]" in response or "[FLERR]" in response:
                if "Enter" in response and "interactive mode" in response:
                    break
                if self._is_response_complete(response, cmd):
                    break
                else:
                    logger.warning("Response appears incomplete")
                    tool_log(self.device, "WARN", "Response incomplete, retrying...")
                    continue
            elif "Missing --cmd" in response:
                break
            else:
                logger.warning("No valid response marker ([FLOK]/[FLERR]), retrying...")
                tool_log(self.device, "WARN", "No response marker, retrying...")
                continue

        need_fl_mode = False
        if "Enter" in last_response and "interactive mode" in last_response:
            self._platform = Platform.NUTTX
            need_fl_mode = True
            logger.info("Detected NuttX platform (requires fl interactive mode)")
        elif "Missing --cmd" in last_response:
            need_fl_mode = True

        if retry_on_missing_cmd and need_fl_mode:
            tool_log(self.device, "INFO", "Entering fl interactive mode...")
            if self.enter_fl_mode():
                return self.send_cmd(
                    cmd, timeout, retry_on_missing_cmd=False, max_retries=max_retries
                )

        return last_response

    def _is_response_complete(self, response: str, cmd: str) -> bool:
        """Check if response appears complete."""
        has_marker = "[FLOK]" in response or "[FLERR]" in response
        if not has_marker:
            return False

        if "-c read" in cmd or "-c info" in cmd:
            if "[FLOK]" in response:
                parts = response.split("[FLOK]", 1)
                if len(parts) > 1:
                    data_part = parts[1].strip()
                    if data_part:
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
                                return False
        return True

    def _log_raw(self, direction: LogDirection, data: str):
        """Log raw serial communication.

        TX logs are only recorded when serial_echo_enabled is True.
        RX logs are always recorded.
        """
        if not data:
            return

        # TX logs only when serial echo is enabled
        if direction == LogDirection.TX:
            if not getattr(self.device, "serial_echo_enabled", False):
                return

        try:
            entry = {
                "id": self.device.raw_log_next_id,
                "time": time.time(),
                "data": data,
            }
            self.device.raw_serial_log.append(entry)
            self.device.raw_log_next_id += 1
            max_size = getattr(self.device, "raw_log_max_size", 5000)
            if len(self.device.raw_serial_log) > max_size:
                self.device.raw_serial_log = self.device.raw_serial_log[-max_size:]
        except Exception:
            pass

    def parse_response(self, resp: str) -> dict:
        """Parse response - format: [FLOK] msg or [FLERR] msg"""
        resp = resp.strip()

        clean_resp = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", resp)
        clean_resp = re.sub(r"\[([0-9;]*[A-NP-Za-df-z])\b", "", clean_resp)
        clean_resp = re.sub(r"(ap|nsh|fl)>\s*$", "", clean_resp, flags=re.MULTILINE)
        clean_resp = clean_resp.strip()

        lines = resp.split("\n")
        for line in reversed(lines):
            line = line.strip()
            if "[FLOK]" in line:
                idx = line.find("[FLOK]")
                msg = line[idx + 6 :].strip()
                return {"ok": True, "msg": msg, "raw": resp}
            elif "[FLERR]" in line:
                idx = line.find("[FLERR]")
                msg = line[idx + 7 :].strip()
                return {"ok": False, "msg": msg, "raw": resp}

        lower_resp = clean_resp.lower()
        if "error" in lower_resp or "fail" in lower_resp or "invalid" in lower_resp:
            return {"ok": False, "msg": clean_resp, "raw": resp}

        if not clean_resp or len(clean_resp) < 5:
            return {"ok": True, "msg": "", "raw": resp}

        return {"ok": False, "msg": clean_resp, "raw": resp}

    # ========== Device Commands ==========

    def ping(self) -> Tuple[bool, str]:
        """Ping device."""
        try:
            resp = self.send_cmd("-c ping")
            result = self.parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def info(self) -> Tuple[Optional[dict], str]:
        """Get device info including slot states."""
        try:
            resp = self.send_cmd("-c info")
            result = self.parse_response(resp)

            if result.get("ok"):
                raw = result.get("raw", "")
                info = {"ok": True, "slots": [], "fpb_version": 1}  # Default to v1
                for line in raw.split("\n"):
                    line = line.strip()
                    if line.startswith("Build:"):
                        info["build_time"] = line.split(":", 1)[1].strip()
                    elif line.startswith("FPB:"):
                        # Parse FPB version: "FPB: v1, 6 code + 2 lit = 8 total"
                        # or "FPB: v2, 8 code + 0 lit = 8 total"
                        if "v1" in line:
                            info["fpb_version"] = 1
                        elif "v2" in line:
                            info["fpb_version"] = 2
                    elif line.startswith("Used:"):
                        try:
                            info["used"] = int(line.split(":")[1].strip())
                        except ValueError:
                            pass
                    elif line.startswith("Slots:"):
                        try:
                            parts = line.split(":")[1].strip().split("/")
                            info["active_slots"] = int(parts[0])
                            info["total_slots"] = int(parts[1])
                        except (ValueError, IndexError):
                            pass
                    elif line.startswith("Slot["):
                        try:
                            # Try full format with (COMP=..., on|off)
                            match = re.match(
                                r"Slot\[(\d+)\]:\s*(0x[0-9A-Fa-f]+)\s*->\s*(0x[0-9A-Fa-f]+),\s*(\d+)\s*bytes.*\(.*,\s*(on|off)\)",
                                line,
                            )
                            if match:
                                slot_id = int(match.group(1))
                                orig_addr = int(match.group(2), 16)
                                target_addr = int(match.group(3), 16)
                                code_size = int(match.group(4))
                                enabled = match.group(5) == "on"
                                info["slots"].append(
                                    {
                                        "id": slot_id,
                                        "occupied": True,
                                        "enabled": enabled,
                                        "orig_addr": orig_addr,
                                        "target_addr": target_addr,
                                        "code_size": code_size,
                                    }
                                )
                            elif "empty" not in line:
                                # Try simple format without (COMP=..., on|off)
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
                                            "enabled": True,
                                            "orig_addr": orig_addr,
                                            "target_addr": target_addr,
                                            "code_size": code_size,
                                        }
                                    )
                            if "empty" in line:
                                match = re.match(r"Slot\[(\d+)\]:", line)
                                if match:
                                    slot_id = int(match.group(1))
                                    info["slots"].append(
                                        {
                                            "id": slot_id,
                                            "occupied": False,
                                            "enabled": True,
                                            "orig_addr": 0,
                                            "target_addr": 0,
                                            "code_size": 0,
                                        }
                                    )
                        except (ValueError, AttributeError):
                            pass
                return info, ""
            return None, result.get("msg", "Unknown error")
        except Exception as e:
            return None, str(e)

    def alloc(self, size: int) -> Tuple[Optional[int], str]:
        """Allocate memory buffer."""
        try:
            resp = self.send_cmd(f"-c alloc -s {size}")
            logger.debug(f"Alloc response: {resp}")
            result = self.parse_response(resp)
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
        bytes_per_chunk = (
            self.device.upload_chunk_size if self.device.upload_chunk_size > 0 else 128
        )

        upload_start = time.time()
        chunk_count = 0

        while data_offset < total:
            chunk = data[data_offset : data_offset + bytes_per_chunk]
            b64_data = base64.b64encode(chunk).decode("ascii")

            device_offset = start_offset + data_offset
            # CRC covers: offset(4B LE) + len(4B LE) + data payload
            crc = crc16_update(0xFFFF, struct.pack("<II", device_offset, len(chunk)))
            crc = crc16_update(crc, chunk)

            cmd = f"-c upload -a 0x{device_offset:X} -d {b64_data} -r 0x{crc:04X}"

            try:
                resp = self.send_cmd(cmd)
                result = self.parse_response(resp)

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

    def _parse_read_response(self, resp: str, addr: int = 0) -> Optional[bytes]:
        """Parse READ response to extract binary data.

        Expected format: [FLOK] READ <n> bytes crc=0x<XXXX> data=<base64>
        CRC covers: addr(4B LE) + len(4B LE) + data payload.
        Returns decoded bytes if CRC matches, None on error.
        """
        match = re.search(
            r"\[FLOK\]\s+READ\s+(\d+)\s+bytes\s+crc=0x([0-9A-Fa-f]+)\s+data=(\S+)",
            resp,
        )
        if not match:
            return None

        expected_len = int(match.group(1))
        expected_crc = int(match.group(2), 16)
        b64_data = match.group(3)

        try:
            raw = base64.b64decode(b64_data)
        except Exception:
            logger.error("Failed to decode base64 from read response")
            return None

        if len(raw) != expected_len:
            logger.error(
                f"Read length mismatch: got {len(raw)}, expected {expected_len}"
            )
            return None

        actual_crc = crc16_update(0xFFFF, struct.pack("<II", addr, len(raw)))
        actual_crc = crc16_update(actual_crc, raw)
        if actual_crc != expected_crc:
            logger.error(
                f"Read CRC mismatch: 0x{actual_crc:04X} != 0x{expected_crc:04X}"
            )
            return None

        return raw

    def read_memory(
        self, addr: int, length: int, progress_callback=None, max_retries: int = 3
    ) -> Tuple[Optional[bytes], str]:
        """Read memory from device in chunks with retry support.

        Returns (data_bytes, message) on success, (None, error_msg) on failure.
        """
        bytes_per_chunk = (
            self.device.download_chunk_size
            if self.device.download_chunk_size > 0
            else 1024
        )
        buf = bytearray()
        offset = 0

        while offset < length:
            n = min(bytes_per_chunk, length - offset)
            chunk_addr = addr + offset
            # CRC covers: addr(4B LE) + len(4B LE) for request verification
            crc_val = crc16_update(0xFFFF, struct.pack("<II", chunk_addr, n))
            cmd = f"-c read --addr 0x{chunk_addr:X} --len {n} --crc 0x{crc_val:04X}"
            last_error = ""

            for attempt in range(max_retries + 1):
                if attempt > 0:
                    logger.warning(
                        f"read_memory retry {attempt}/{max_retries} at 0x{chunk_addr:X}"
                    )

                try:
                    resp = self.send_cmd(cmd, timeout=2.0)
                    data = self._parse_read_response(resp, addr=chunk_addr)
                    if data is not None:
                        buf.extend(data)
                        break
                    last_error = f"Read failed at offset 0x{offset:X}"
                except Exception as e:
                    last_error = f"Read exception at offset 0x{offset:X}: {e}"
            else:
                return None, last_error

            offset += n
            if progress_callback:
                progress_callback(offset, length)

        return bytes(buf), f"Read {length} bytes OK"

    def write_memory(
        self, addr: int, data: bytes, progress_callback=None, max_retries: int = 3
    ) -> Tuple[bool, str]:
        """Write data to device memory in chunks with retry support.

        Returns (success, message).
        """
        bytes_per_chunk = (
            self.device.upload_chunk_size if self.device.upload_chunk_size > 0 else 128
        )
        total = len(data)
        offset = 0

        while offset < total:
            chunk = data[offset : offset + bytes_per_chunk]
            b64 = base64.b64encode(chunk).decode("ascii")
            chunk_addr = addr + offset
            # CRC covers: addr(4B LE) + len(4B LE) + data payload
            crc_val = crc16_update(0xFFFF, struct.pack("<II", chunk_addr, len(chunk)))
            crc_val = crc16_update(crc_val, chunk)
            cmd = f"-c write --addr 0x{chunk_addr:X} --data {b64} --crc 0x{crc_val:04X}"
            last_error = ""

            for attempt in range(max_retries + 1):
                if attempt > 0:
                    logger.warning(
                        f"write_memory retry {attempt}/{max_retries} at 0x{chunk_addr:X}"
                    )

                try:
                    resp = self.send_cmd(cmd, timeout=2.0)
                    result = self.parse_response(resp)
                    if result.get("ok"):
                        break
                    last_error = (
                        f"Write failed at offset 0x{offset:X}: {result.get('msg')}"
                    )
                except Exception as e:
                    last_error = f"Write exception at offset 0x{offset:X}: {e}"
            else:
                return False, last_error

            offset += len(chunk)
            if progress_callback:
                progress_callback(offset, total)

        return True, f"Write {total} bytes OK"

    def _patch_crc(self, comp: int, orig: int, target: int) -> int:
        """Compute CRC for patch commands: comp(4B LE) + orig(4B LE) + target(4B LE)."""
        return crc16_update(0xFFFF, struct.pack("<III", comp, orig, target))

    def patch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set FPB patch (direct mode)."""
        try:
            crc_val = self._patch_crc(comp, orig, target)
            cmd = f"-c patch --comp {comp} --orig 0x{orig:X} --target 0x{target:X} --crc 0x{crc_val:04X}"
            resp = self.send_cmd(cmd)
            result = self.parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def tpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set trampoline patch."""
        try:
            crc_val = self._patch_crc(comp, orig, target)
            cmd = f"-c tpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X} --crc 0x{crc_val:04X}"
            resp = self.send_cmd(cmd)
            result = self.parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def dpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set DebugMonitor patch."""
        try:
            crc_val = self._patch_crc(comp, orig, target)
            cmd = f"-c dpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X} --crc 0x{crc_val:04X}"
            resp = self.send_cmd(cmd)
            result = self.parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def unpatch(self, comp: int = 0, all: bool = False) -> Tuple[bool, str]:
        """Clear FPB patch."""
        try:
            if all:
                cmd = "-c unpatch --all"
            else:
                cmd = f"-c unpatch --comp {comp}"
            resp = self.send_cmd(cmd)
            result = self.parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def enable_patch(
        self, comp: int = 0, enable: bool = True, all: bool = False
    ) -> Tuple[bool, str]:
        """Enable or disable FPB patch without clearing it."""
        try:
            enable_val = 1 if enable else 0
            if all:
                cmd = f"-c enable --enable {enable_val} --all"
            else:
                cmd = f"-c enable --comp {comp} --enable {enable_val}"
            resp = self.send_cmd(cmd)
            result = self.parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def _probe_echo(self, test_size: int, timeout: float = 2.0) -> Dict:
        """Send an echo command of given size and verify CRC.

        Returns a test_result dict with keys: size, cmd_len, passed, error,
        response_time_ms.
        """
        hex_data = "".join(f"{(i % 256):02X}" for i in range(test_size))
        cmd = f"-c echo -d {hex_data}"

        test_result: Dict = {
            "size": test_size,
            "cmd_len": len(cmd),
            "passed": False,
            "error": None,
            "response_time_ms": 0,
        }

        try:
            start_time = time.time()
            response = self.send_cmd(cmd, timeout=timeout)
            elapsed_ms = (time.time() - start_time) * 1000
            test_result["response_time_ms"] = round(elapsed_ms, 2)

            if "[FLOK]" in response:
                expected_crc = crc16(hex_data.encode("ascii"))
                crc_match = re.search(r"0x([0-9A-Fa-f]{4})", response)
                if crc_match:
                    received_crc = int(crc_match.group(1), 16)
                    if received_crc == expected_crc:
                        test_result["passed"] = True
                    else:
                        test_result["error"] = (
                            f"CRC mismatch: expected 0x{expected_crc:04X}, "
                            f"got 0x{received_crc:04X}"
                        )
                else:
                    test_result["passed"] = True
            else:
                if "[FLERR]" in response:
                    test_result["error"] = "Device returned error"
                elif not response:
                    test_result["error"] = "No response (timeout)"
                else:
                    test_result["error"] = "Incomplete/invalid response"
        except Exception as e:
            test_result["error"] = str(e)

        return test_result

    def _phase_fragment_probe(self, timeout: float = 2.0) -> Dict:
        """Phase 1: Detect whether TX fragmentation is needed.

        Sends a medium-length echo command (256 bytes). If it succeeds,
        fragmentation is not needed. If it fails, fragmentation is required
        but the optimal fragment size is left to the user or a future probe.
        """
        result: Dict = {
            "needed": False,
            "test": None,
        }
        max_retries = 3
        for attempt in range(max_retries):
            probe = self._probe_echo(256, timeout=timeout)
            if probe["passed"]:
                break
        result["test"] = probe
        if not probe["passed"]:
            result["needed"] = True
        return result

    def _phase_upload_probe(
        self, start_size: int = 16, max_size: int = 4096, timeout: float = 2.0
    ) -> Dict:
        """Phase 2: Find the device shell receive buffer limit (upload direction).

        Uses increasing echo commands with x1.4 stepping.
        """
        result: Dict = {
            "max_working_size": 0,
            "failed_size": 0,
            "recommended_upload_chunk_size": 0,
            "tests": [],
        }

        test_size = start_size
        max_working = 0
        max_retries = 3

        while test_size <= max_size:
            passed = False
            probe = None
            for attempt in range(max_retries):
                probe = self._probe_echo(test_size, timeout=timeout)
                if probe["passed"]:
                    passed = True
                    break
            result["tests"].append(probe)

            if passed:
                max_working = test_size
            else:
                result["failed_size"] = test_size
                break

            test_size = max(test_size + 2, int(test_size * 1.4) // 2 * 2)

        result["max_working_size"] = max_working
        if max_working > 0:
            result["recommended_upload_chunk_size"] = (max_working * 3) // 4
            if result["recommended_upload_chunk_size"] < 16:
                result["recommended_upload_chunk_size"] = max_working
        return result

    def _probe_echoback(self, test_size: int, timeout: float = 3.0) -> Dict:
        """Send an echoback request and verify the response.

        The device fills its send buffer with a known pattern of `test_size`
        bytes and returns it as base64 with CRC. This tests the download
        direction (device → PC) throughput.

        Protocol:
          Request:  fl -c echoback --len {N}
          Response: [FLOK] ECHOBACK {N} bytes crc=0x{CRC} data={base64}

        Returns a test_result dict with keys: size, passed, error,
        response_time_ms.
        """
        cmd = f"-c echoback --len {test_size}"

        test_result: Dict = {
            "size": test_size,
            "passed": False,
            "error": None,
            "response_time_ms": 0,
        }

        try:
            start_time = time.time()
            response = self.send_cmd(cmd, timeout=timeout)
            elapsed_ms = (time.time() - start_time) * 1000
            test_result["response_time_ms"] = round(elapsed_ms, 2)

            if "[FLOK]" in response:
                # Parse: [FLOK] ECHOBACK {N} bytes crc=0x{CRC} data={base64}
                data_match = re.search(r"data=(\S+)", response)
                crc_match = re.search(r"crc=0x([0-9A-Fa-f]{4})", response)
                if data_match and crc_match:
                    raw = base64.b64decode(data_match.group(1))
                    received_crc = int(crc_match.group(1), 16)
                    expected_crc = crc16(raw)
                    if len(raw) == test_size and received_crc == expected_crc:
                        test_result["passed"] = True
                    elif len(raw) != test_size:
                        test_result["error"] = (
                            f"Size mismatch: expected {test_size}, got {len(raw)}"
                        )
                    else:
                        test_result["error"] = (
                            f"CRC mismatch: expected 0x{expected_crc:04X}, "
                            f"got 0x{received_crc:04X}"
                        )
                elif not data_match:
                    test_result["error"] = "No data in response"
                else:
                    test_result["error"] = "No CRC in response"
            else:
                if "[FLERR]" in response:
                    test_result["error"] = "Device returned error"
                elif not response:
                    test_result["error"] = "No response (timeout)"
                else:
                    test_result["error"] = "Incomplete/invalid response"
        except Exception as e:
            test_result["error"] = str(e)

        return test_result

    def _phase_download_probe(
        self,
        start_size: int = 256,
        max_size: int = 8192,
        timeout: float = 3.0,
    ) -> Dict:
        """Phase 3: Find the max reliable download chunk size.

        Uses the `echoback` command to have the device generate and send
        increasing amounts of data. The device reuses its send buffer to
        fill with a pattern, so no RAM allocation is needed.
        """
        result: Dict = {
            "max_working_size": 0,
            "failed_size": 0,
            "recommended_download_chunk_size": 1024,
            "tests": [],
            "skipped": False,
        }

        max_retries = 3

        # Quick check: does the device support echoback?
        probe = self._probe_echoback(start_size, timeout=timeout)
        if probe.get("error") and (
            "Device returned error" in (probe["error"] or "")
            or "No response" in (probe["error"] or "")
        ):
            result["skipped"] = True
            result["skip_reason"] = (
                f"Device does not support echoback command: {probe['error']}"
            )
            return result

        result["tests"].append(probe)
        if not probe["passed"]:
            result["failed_size"] = start_size
            return result

        max_working = start_size
        test_size = max(start_size + 64, int(start_size * 1.5) // 64 * 64)

        while test_size <= max_size:
            passed = False
            probe = None
            for attempt in range(max_retries):
                probe = self._probe_echoback(test_size, timeout=timeout)
                if probe["passed"]:
                    passed = True
                    break
            result["tests"].append(probe)

            if passed:
                max_working = test_size
            else:
                result["failed_size"] = test_size
                break

            test_size = max(test_size + 64, int(test_size * 1.5) // 64 * 64)

        result["max_working_size"] = max_working
        if max_working > 0:
            # Download direction is more stable, use 85% safety margin
            recommended = (max_working * 85) // 100 // 64 * 64
            if recommended < 128:
                recommended = max_working
            result["recommended_download_chunk_size"] = recommended
        return result

    def test_serial_throughput(
        self, start_size: int = 16, max_size: int = 4096, timeout: float = 2.0
    ) -> Dict:
        """Test serial throughput with 3-phase probing.

        Phase 1: TX Fragment probe - detect if PC→device needs fragmentation.
        Phase 2: Upload chunk probe - find device shell buffer limit.
        Phase 3: Download chunk probe - find max reliable download size.

        Returns a comprehensive result dict with recommended parameters.
        """
        if self.device is None or self.device.ser is None:
            return {
                "success": False,
                "error": "Serial port not connected",
                "max_working_size": 0,
                "failed_size": 0,
                "tests": [],
                "recommended_upload_chunk_size": 16,
                "recommended_download_chunk_size": 1024,
                "fragment_needed": False,
            }

        results: Dict = {
            "success": True,
            "max_working_size": 0,
            "failed_size": 0,
            "tests": [],
            "recommended_upload_chunk_size": 16,
            "recommended_download_chunk_size": 1024,
            "fragment_needed": False,
            "phases": {},
        }

        try:
            # Phase 1: TX Fragment probe
            frag = self._phase_fragment_probe(timeout=timeout)
            results["phases"]["fragment"] = frag
            results["fragment_needed"] = frag["needed"]

            # Phase 2: Upload chunk probe (same as old test_serial_throughput)
            upload = self._phase_upload_probe(
                start_size=start_size, max_size=max_size, timeout=timeout
            )
            results["phases"]["upload"] = upload
            results["tests"] = upload["tests"]  # backward compat
            results["max_working_size"] = upload["max_working_size"]
            results["failed_size"] = upload["failed_size"]
            results["recommended_upload_chunk_size"] = upload[
                "recommended_upload_chunk_size"
            ]

            if upload["max_working_size"] == 0:
                results["success"] = False
                results["error"] = (
                    "Serial communication failed at minimum size "
                    f"({start_size} bytes). Check connection and try again."
                )
                results["recommended_upload_chunk_size"] = 0
                return results

            # Phase 3: Download chunk probe (uses echoback command)
            download = self._phase_download_probe(
                start_size=256,
                max_size=8192,
                timeout=max(timeout, 3.0),
            )
            results["phases"]["download"] = download
            results["recommended_download_chunk_size"] = download[
                "recommended_download_chunk_size"
            ]

        except Exception as e:
            results["success"] = False
            results["error"] = str(e)

        return results
