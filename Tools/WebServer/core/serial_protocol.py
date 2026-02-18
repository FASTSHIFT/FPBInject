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
import time
from typing import Dict, Optional, Tuple

from utils.crc import crc16

logger = logging.getLogger(__name__)


class FPBProtocolError(Exception):
    """Exception for FPB protocol operations."""

    pass


class FPBProtocol:
    """FPB serial protocol handler."""

    def __init__(self, device_state):
        """Initialize FPB protocol handler."""
        self.device = device_state
        self._in_fl_mode = False
        self._platform = "unknown"

    def get_platform(self) -> str:
        """Get detected platform type."""
        return self._platform

    def enter_fl_mode(self, timeout: float = 0.5) -> bool:
        """Enter fl interactive mode by sending 'fl' command."""
        ser = self.device.ser
        if not ser:
            self._in_fl_mode = False
            self._platform = "unknown"
            return False

        # If already in fl mode, just return
        if self._in_fl_mode:
            return True

        try:
            self._log_raw("TX", "fl")
            ser.reset_input_buffer()
            ser.write(b"fl\n")
            ser.flush()

            start = time.time()
            response = ""
            while time.time() - start < timeout:
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                    response += chunk
                    if (
                        "fl>" in response
                        or "[FLOK]" in response
                        or "[FLERR]" in response
                    ):
                        break
                time.sleep(0.01)

            self._log_raw("RX", response.strip())
            logger.debug(f"Entered fl mode: {response.strip()}")

            if "fl>" in response:
                self._in_fl_mode = True
                self._platform = "nuttx"
                logger.info("Detected NuttX platform (fl interactive mode)")
                return True
            elif "Enter" in response and "interactive mode" in response:
                self._platform = "nuttx"
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
                self._platform = "bare-metal"
                return False
        except Exception as e:
            logger.error(f"Error entering fl mode: {e}")
            self._in_fl_mode = False
            self._platform = "unknown"
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
            self._log_raw("TX", "exit")
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
        timeout: float = 2.0,
        retry_on_missing_cmd: bool = True,
        max_retries: int = 3,
    ) -> str:
        """Send command and get response with automatic retry."""
        ser = self.device.ser
        if not ser:
            raise FPBProtocolError("Serial port not connected")

        full_cmd = f"fl {cmd}" if not cmd.strip().startswith("fl ") else cmd

        last_response = ""
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.warning(
                    f"Retry {attempt}/{max_retries} for command: {cmd[:50]}..."
                )
                self._log_raw("RETRY", f"Attempt {attempt + 1}/{max_retries + 1}")
                time.sleep(0.05)

            logger.debug(f"TX: {full_cmd}")
            self._log_raw("TX", full_cmd)

            ser.reset_input_buffer()

            data_bytes = (full_cmd + "\n").encode()
            tx_chunk_size = getattr(self.device, "tx_chunk_size", 0)
            tx_chunk_delay = getattr(self.device, "tx_chunk_delay", 0.005)
            if tx_chunk_size > 0 and len(data_bytes) > tx_chunk_size:
                for i in range(0, len(data_bytes), tx_chunk_size):
                    chunk = data_bytes[i : i + tx_chunk_size]
                    ser.write(chunk)
                    ser.flush()
                    if i + tx_chunk_size < len(data_bytes):
                        time.sleep(tx_chunk_delay)
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
            self._log_raw("RX", response)

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
                    self._log_raw("WARN", "Response incomplete, retrying...")
                    continue
            elif "Missing --cmd" in response:
                break
            else:
                logger.warning("No valid response marker ([FLOK]/[FLERR]), retrying...")
                self._log_raw("WARN", "No response marker, retrying...")
                continue

        need_fl_mode = False
        if "Enter" in last_response and "interactive mode" in last_response:
            self._platform = "nuttx"
            need_fl_mode = True
            logger.info("Detected NuttX platform (requires fl interactive mode)")
        elif "Missing --cmd" in last_response:
            need_fl_mode = True

        if retry_on_missing_cmd and need_fl_mode:
            self._log_raw("INFO", "Entering fl interactive mode...")
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

    def _log_raw(self, direction: str, data: str):
        """Log raw serial communication."""
        if not data:
            return
        try:
            entry = {
                "id": self.device.raw_log_next_id,
                "time": time.time(),
                "dir": direction,
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
                info = {"ok": True, "slots": []}
                for line in raw.split("\n"):
                    line = line.strip()
                    if line.startswith("Build:"):
                        info["build_time"] = line.split(":", 1)[1].strip()
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
        bytes_per_chunk = self.device.chunk_size if self.device.chunk_size > 0 else 128

        upload_start = time.time()
        chunk_count = 0

        while data_offset < total:
            chunk = data[data_offset : data_offset + bytes_per_chunk]
            b64_data = base64.b64encode(chunk).decode("ascii")
            crc = crc16(chunk)

            device_offset = start_offset + data_offset
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

    def patch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set FPB patch (direct mode)."""
        try:
            cmd = f"-c patch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
            resp = self.send_cmd(cmd)
            result = self.parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def tpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set trampoline patch."""
        try:
            cmd = f"-c tpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
            resp = self.send_cmd(cmd)
            result = self.parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def dpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set DebugMonitor patch."""
        try:
            cmd = f"-c dpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
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

    def test_serial_throughput(
        self, start_size: int = 16, max_size: int = 4096, timeout: float = 2.0
    ) -> Dict:
        """Test serial port throughput by sending increasing data sizes."""
        if self.device is None or self.device.ser is None:
            return {
                "success": False,
                "error": "Serial port not connected",
                "max_working_size": 0,
                "failed_size": 0,
                "tests": [],
                "recommended_chunk_size": 16,
            }

        results = {
            "success": True,
            "max_working_size": 0,
            "failed_size": 0,
            "tests": [],
            "recommended_chunk_size": 16,
        }

        try:
            test_size = start_size
            max_working = 0

            while test_size <= max_size:
                hex_data = "".join(f"{(i % 256):02X}" for i in range(test_size))
                cmd = f"-c echo -d {hex_data}"

                test_result = {
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
                            test_result["passed"] = True
                            max_working = test_size
                    else:
                        test_result["passed"] = False
                        if "[FLERR]" in response:
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
                test_size *= 2

            results["max_working_size"] = max_working
            if max_working > 0:
                # Use 75% of max working size as safe chunk size
                # Don't force minimum - respect actual device capability
                results["recommended_chunk_size"] = (max_working * 3) // 4
                if results["recommended_chunk_size"] < 16:
                    results["recommended_chunk_size"] = max_working
            else:
                results["recommended_chunk_size"] = 16

        except Exception as e:
            results["success"] = False
            results["error"] = str(e)

        return results
