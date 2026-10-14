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

from fpbinject.utils.crc import crc16, crc16_update
from fpbinject.core.config_schema import (
    DEFAULT_DOWNLOAD_CHUNK_SIZE,
    DEFAULT_UPLOAD_CHUNK_SIZE,
)
from fpbinject.core.state import tool_log

logger = logging.getLogger(__name__)


class LogDirection(Enum):
    """Direction for serial log entries."""

    TX = "TX"
    RX = "RX"


# Marker the firmware prints when it leaves the fl loop (see fl_port_nuttx.c).
# Part of the [FLxxx] protocol family; the only exit confirmation we rely on.
FL_MODE_EXIT_MARKER = "[FLEXIT]"

# Attempts to leave the fl loop. Every attempt sends a single "q"; a second or
# third one only covers a lost "q" or a lost marker.
EXIT_ATTEMPTS = 3


def note_fl_markers(device, text: str) -> None:
    """Count ``[FLEXIT]`` markers seen on the wire (passive state sync).

    Everything that reads the port feeds its text through here (the protocol's
    own reads via ``_log_raw``, the DeviceWorker's background reads), so a
    device that left the fl loop without our asking (the user typed ``q`` in
    the terminal) is noticed: ``FPBProtocol`` compares the counter with the
    value it saw when it last put the device into the loop.
    """
    if FL_MODE_EXIT_MARKER not in text:
        return
    seen = getattr(device, "fl_exit_seen", 0)
    if not isinstance(seen, int):
        seen = 0
    try:
        device.fl_exit_seen = seen + text.count(FL_MODE_EXIT_MARKER)
    except Exception:
        pass


# A shell prompt as it shows up at the end of a reply: one short token without
# blanks that ends in a prompt character ("ap>", "nsh>", "fl>", "user@dev:~$",
# "#"). Shell prompts are not fixed, so no names are listed here.
_PROMPT_RE = re.compile(r"[^\s\[\]]{0,40}[>#$%]")


def strip_trailing_prompt(text: str) -> str:
    """Drop a shell prompt left at the end of ``text``.

    Only the last line is considered, and only when it consists of nothing but
    a prompt token, so ordinary output that merely ends in ``>`` (``a -> b``)
    is left alone. Used for the fallback path of ``parse_response``; replies
    that carry ``[FLOK]``/``[FLERR]`` never depend on it.
    """
    head, _, last = text.rpartition("\n")
    if _PROMPT_RE.fullmatch(last.strip()):
        return head
    return text


class FPBProtocolError(Exception):
    """Exception for FPB protocol operations."""

    pass


class FPBProtocol:
    """FPB serial protocol handler.

    fl mode: a device whose ``info`` reports ``Mode: interactive`` (a port that
    runs ``fl`` as a program from a shell, e.g. NuttX) keeps running the
    ``fl>`` loop after any ``fl ...`` command, so there is
    nothing to "enter": the command line itself does it. The host only has to
    leave the loop when it is done (``exit_fl_mode``, confirmed by the
    ``[FLEXIT]`` marker). A ``oneshot`` device has no loop at all and
    ``exit_fl_mode`` does nothing.
    """

    def __init__(self, device_state):
        """Initialize FPB protocol handler."""
        self.device = device_state
        # What the device said about itself in ``info`` ("Mode:", "Platform:").
        # Learned once per serial object (see ensure_mode), so a reconnect
        # starts from scratch.
        self._mode_ser = None
        self._interactive = False
        self.platform_desc = ""
        # The host believes the device sits in the fl loop. Only ever set for
        # an interactive device.
        self._in_fl_mode = False
        self._exit_mark = 0  # device.fl_exit_seen when the flag was set
        # Serial object on which an exec command ended in an unknown state
        # (see core/exec_client.py). Tied to the port object so reconnecting
        # (a new serial object) clears it automatically.
        self.exec_suspect_ser = None
        # Last exec request id put on the wire; the next one must differ from it
        self.exec_last_seq = None

    @property
    def interactive(self) -> bool:
        """True if the device runs the interactive fl loop (valid after ensure_mode)."""
        return self._interactive

    def wakeup_shell(self, cnt: int):
        """Send ``cnt`` newlines so a half-typed shell line cannot spoil the next command."""
        for _ in range(cnt):
            self.device.ser.write(b"\n")
            self.device.ser.flush()
            time.sleep(0.05)

    def _learn_mode(self, raw: str) -> bool:
        """Record Mode:/Platform: from an ``info`` reply. False if it is not one."""
        if "[FLOK]" not in raw:
            return False
        mode = ""
        self.platform_desc = ""
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("Mode:"):
                mode = line.split(":", 1)[1].strip()
            elif line.startswith("Platform:"):
                self.platform_desc = line.split(":", 1)[1].strip()
        if not mode:
            logger.warning("Device 'info' has no Mode: line, treating it as oneshot")
        self._interactive = mode == "interactive"
        self._mode_ser = self.device.ser
        logger.info(
            f"Device mode: {mode or 'unknown'}"
            f"{' (' + self.platform_desc + ')' if self.platform_desc else ''}"
        )
        return True

    def ensure_mode(self) -> None:
        """Ask the device once per serial port whether it runs the fl loop.

        The first command on a port is ``fl -c info``. The reply carries
        ``Mode:`` (and ``Platform:``), nothing else about the shell is
        guessed. From a shell prompt this command also starts the loop, which is
        why the device is marked as inside it afterwards.
        """
        ser = self.device.ser
        if not ser or self._mode_ser is ser:
            return
        # A new port: forget what we knew about the previous one
        self._interactive = False
        self._in_fl_mode = False
        wake = getattr(self.device, "wakeup_shell_cnt", 0)
        self.wakeup_shell(wake if isinstance(wake, int) else 0)
        resp = self._transact("fl -c info", timeout=0.8, max_retries=1)
        if self._learn_mode(resp):
            self.mark_in_fl()
        else:
            logger.warning("Device did not answer the mode probe (fl -c info)")

    def mark_in_fl(self) -> None:
        """An fl command was just sent: an interactive device is now in the loop."""
        if self._interactive:
            self._in_fl_mode = True
            seen = getattr(self.device, "fl_exit_seen", 0)
            self._exit_mark = seen if isinstance(seen, int) else 0

    def _sync_exit_marker(self) -> None:
        """Drop the flag if a [FLEXIT] we did not ask for went by."""
        if not self._in_fl_mode:
            return
        seen = getattr(self.device, "fl_exit_seen", 0)
        if isinstance(seen, int) and seen != self._exit_mark:
            logger.debug("[FLEXIT] seen on the wire, device left fl mode")
            self._in_fl_mode = False

    def _read_pending(self, ser, max_wait: float = 0.05) -> str:
        """Drain whatever is already buffered, returning once it empties.

        After a command the fl loop prints its next ``fl> `` prompt and blocks
        in ``fgets`` -- that stale prompt is sitting in the buffer. Reading it
        out (and forwarding it) here keeps it from polluting the exit probe.
        """
        start = time.time()
        buf = ""
        while time.time() - start < max_wait:
            if ser.in_waiting:
                buf += ser.read(ser.in_waiting).decode("utf-8", errors="replace")
            else:
                break
        return buf

    def _drain_serial(self, ser, idle: float, max_wait: float) -> str:
        """Read until the device goes quiet for ``idle`` s (cap ``max_wait``).

        Returns as soon as the reply stops, so a normal probe costs a few tens
        of ms instead of the full window. If nothing arrives at all it gives up
        after a short first-byte grace rather than blocking the whole timeout.
        """
        start = time.time()
        last_rx = start
        first_byte = min(max_wait, max(idle * 2, 0.05))
        buf = ""
        while True:
            now = time.time()
            if now - start >= max_wait:
                break
            if ser.in_waiting:
                buf += ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                last_rx = time.time()
            elif buf and now - last_rx >= idle:
                break
            elif not buf and now - start >= first_byte:
                break
            else:
                time.sleep(0.005)
        return buf

    def exit_fl_mode(self, timeout: float = 0.3) -> bool:
        """Leave the fl loop with ``q`` and wait for the ``[FLEXIT]`` marker.

        Nothing to do (returns True) for a oneshot device, when the host does
        not believe the device is in the loop, or when a ``[FLEXIT]`` already
        went by. Otherwise ``q`` is sent and the reply is read until it goes
        quiet: ``[FLEXIT]`` confirms. ``command not found`` means the device
        was already at the shell prompt (host and device had drifted apart).
        Anything else is unconfirmed: the flag stays set so a later call tries
        again, and the call returns False.

        Reads are idle-based and every byte is forwarded to the terminal log.
        If a previous exec ended in an unknown state the device is busy running
        the command and cannot read ``q``: one attempt only, so no pile of
        ``q`` lines is left for the shell to chew on later.
        """
        self._sync_exit_marker()
        if not self._in_fl_mode:
            logger.debug("Not in fl mode, skipping exit")
            return True

        ser = self.device.ser
        if not ser:
            self._in_fl_mode = False
            return False

        attempts = 1 if self.exec_suspect_ser is ser else EXIT_ATTEMPTS
        try:
            # Flush the stale prompt so only fresh output is inspected.
            self._log_raw(LogDirection.RX, self._read_pending(ser))
            self._sync_exit_marker()
            if not self._in_fl_mode:
                return True

            for attempt in range(attempts):
                self._log_raw(LogDirection.TX, "q")
                ser.write(b"q\n")
                ser.flush()

                response = self._drain_serial(ser, idle=0.03, max_wait=timeout)
                # Forward, don't swallow: keep whatever the device printed.
                self._log_raw(LogDirection.RX, response)

                if FL_MODE_EXIT_MARKER in response:
                    self._in_fl_mode = False
                    logger.debug("Exited fl mode ([FLEXIT] confirmed)")
                    return True

                if "command not found" in response:
                    self._in_fl_mode = False
                    logger.debug("Already at the shell prompt, nothing to exit")
                    return True

                logger.warning(
                    f"exit_fl_mode: [FLEXIT] not seen "
                    f"(attempt {attempt + 1}/{attempts}): {response[:80]!r}"
                )
        except Exception as e:
            logger.error(f"Error exiting fl mode: {e}")
            return False

        logger.warning("exit_fl_mode: could not confirm exit from fl mode")
        return False

    def _write_line(self, line: str) -> None:
        """Write one command line (plus newline) to the serial port.

        Honours the configured TX fragmentation (serial_tx_fragment_size /
        serial_tx_fragment_delay). Shared by send_cmd and the exec client so
        both put bytes on the wire exactly the same way.
        """
        ser = self.device.ser
        data_bytes = (line + "\n").encode()
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

    def send_cmd(
        self,
        cmd: str,
        timeout: float = 0.5,
        max_retries: int = 3,
    ) -> str:
        """Send command and get response with automatic retry."""
        if not self.device.ser:
            raise FPBProtocolError("Serial port not connected")

        self.ensure_mode()

        full_cmd = f"fl {cmd}" if not cmd.strip().startswith("fl ") else cmd
        return self._transact(full_cmd, timeout, max_retries)

    def _transact(self, full_cmd: str, timeout: float, max_retries: int) -> str:
        """Send one ``fl ...`` line and read the reply, resending on failure."""
        ser = self.device.ser
        if not ser:
            raise FPBProtocolError("Serial port not connected")

        last_response = ""
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.warning(
                    f"Retry {attempt}/{max_retries} for command: {full_cmd[:50]}..."
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

            self._write_line(full_cmd)

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
                if self._is_response_complete(response, full_cmd):
                    break
                else:
                    logger.warning("Response appears incomplete")
                    tool_log(self.device, "WARN", "Response incomplete, retrying...")
                    continue
            else:
                logger.warning("No valid response marker ([FLOK]/[FLERR]), retrying...")
                tool_log(self.device, "WARN", "No response marker, retrying...")
                continue

        if "[FLOK]" in last_response or "[FLERR]" in last_response:
            self.mark_in_fl()
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

        if direction == LogDirection.RX:
            note_fl_markers(self.device, data)

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
        clean_resp = strip_trailing_prompt(clean_resp)
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

                # If response has no FLOK marker, device didn't actually respond
                if "[FLOK]" not in raw:
                    return None, "Device not responding"

                info = {"ok": True, "slots": [], "fpb_version": 1}  # Default to v1
                for line in raw.split("\n"):
                    line = line.strip()
                    if line.startswith("FPBInject") or line.startswith("FPBINJECT"):
                        info["version_string"] = line
                    elif line.startswith("Build:"):
                        info["build_time"] = line.split(":", 1)[1].strip()
                    elif line.startswith("FPB:"):
                        # Parse FPB version: "FPB: v1, 6 code + 2 lit = 8 total"
                        # or "FPB: v2, 8 code + 0 lit = 8 total"
                        info["fpb_detail"] = line.split(":", 1)[1].strip()
                        if "v1" in line:
                            info["fpb_version"] = 1
                        elif "v2" in line:
                            info["fpb_version"] = 2
                    elif line.startswith("FileTransfer:"):
                        info["file_transfer"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Exec:"):
                        info["exec"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Mode:"):
                        info["mode"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Platform:"):
                        info["platform"] = line.split(":", 1)[1].strip()
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
            crc = crc16_update(0xFFFF, struct.pack("<I", size))
            resp = self.send_cmd(f"-c alloc -s {size} -r 0x{crc:04X}")
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
            self.device.upload_chunk_size
            if self.device.upload_chunk_size > 0
            else DEFAULT_UPLOAD_CHUNK_SIZE
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
            else DEFAULT_DOWNLOAD_CHUNK_SIZE
        )
        buf = bytearray()
        offset = 0

        while offset < length:
            n = min(bytes_per_chunk, length - offset)
            chunk_addr = addr + offset
            # CRC covers: addr(4B LE) + len(4B LE) for request verification
            crc_val = crc16_update(0xFFFF, struct.pack("<II", chunk_addr, n))
            cmd = f"-c read -a 0x{chunk_addr:X} -l {n} -r 0x{crc_val:04X}"
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
            self.device.upload_chunk_size
            if self.device.upload_chunk_size > 0
            else DEFAULT_UPLOAD_CHUNK_SIZE
        )

        def _b64_len(n):
            return ((n + 2) // 3) * 4

        # upload_chunk_size is calibrated (by test-serial) so an fwrite command
        # fits the device's interactive line buffer. The write command carries
        # an extra "-a 0x{addr}" arg, so reusing upload_chunk_size verbatim can
        # overflow that buffer and the device silently truncates the line.
        # Budget the write command to the same total length a proven-safe
        # fwrite would have, then shrink the payload to fit.
        cmd_budget = _b64_len(bytes_per_chunk) + len("fl -c fwrite -d  -r 65535")

        total = len(data)
        offset = 0

        while offset < total:
            chunk_addr = addr + offset
            # Reserve room for this command's fixed overhead (incl. the address
            # arg and the "fl " prefix send_cmd prepends).
            overhead = len(f"fl -c write -a 0x{chunk_addr:X} -d  -r 0x{0:04X}")
            max_bytes = ((cmd_budget - overhead) // 4) * 3
            eff_chunk = max(1, min(bytes_per_chunk, max_bytes))

            chunk = data[offset : offset + eff_chunk]
            b64 = base64.b64encode(chunk).decode("ascii")
            # CRC covers: addr(4B LE) + len(4B LE) + data payload
            crc_val = crc16_update(0xFFFF, struct.pack("<II", chunk_addr, len(chunk)))
            crc_val = crc16_update(crc_val, chunk)
            cmd = f"-c write -a 0x{chunk_addr:X} -d {b64} -r 0x{crc_val:04X}"
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
            cmd = f"-c patch --comp {comp} --orig 0x{orig:X} --target 0x{target:X} -r 0x{crc_val:04X}"
            resp = self.send_cmd(cmd)
            result = self.parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def tpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set trampoline patch."""
        try:
            crc_val = self._patch_crc(comp, orig, target)
            cmd = f"-c tpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X} -r 0x{crc_val:04X}"
            resp = self.send_cmd(cmd)
            result = self.parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def dpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set DebugMonitor patch."""
        try:
            crc_val = self._patch_crc(comp, orig, target)
            cmd = f"-c dpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X} -r 0x{crc_val:04X}"
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
                crc = crc16_update(0xFFFF, struct.pack("<I", comp))
                cmd = f"-c unpatch --comp {comp} -r 0x{crc:04X}"
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
                crc = crc16_update(0xFFFF, struct.pack("<II", comp, enable_val))
                cmd = f"-c enable --comp {comp} --enable {enable_val} -r 0x{crc:04X}"
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

        Sends a short echo command (16 bytes). If it succeeds, fragmentation is
        not needed. If it fails, fragmentation is required but the optimal
        fragment size is left to the user or a future probe.
        """
        result: Dict = {
            "needed": False,
            "test": None,
        }
        max_retries = 3
        for attempt in range(max_retries):
            probe = self._probe_echo(16, timeout=timeout)
            if probe["passed"]:
                break
        result["test"] = probe
        if not probe["passed"]:
            result["needed"] = True
        return result

    def _phase_fragment_size_probe(self, timeout: float = 2.0) -> Dict:
        """Phase 1.5: Find optimal TX fragment size and delay.

        Called when Phase 1 detects that fragmentation is needed.

        Strategy:
        1. Fix delay=5ms, try fragment_size from large to small (128→8).
           Find the largest size that lets a 256B echo succeed.
        2. Fix fragment_size, try reducing delay (3ms→1ms).
           Find the smallest delay that still works (verified 3 times).

        Temporarily sets device.serial_tx_fragment_size/delay during probing,
        restores originals on failure.
        """
        result: Dict = {
            "success": False,
            "recommended_fragment_size": 0,
            "recommended_fragment_delay": 0.005,
            "tests": [],
        }

        orig_size = getattr(self.device, "serial_tx_fragment_size", 0)
        orig_delay = getattr(self.device, "serial_tx_fragment_delay", 0.002)

        conservative_delay = 0.005  # 5ms starting point
        test_sizes = [128, 64, 32, 16, 8]

        # Step 1: find largest working fragment_size
        best_size = 0
        for size in test_sizes:
            self.device.serial_tx_fragment_size = size
            self.device.serial_tx_fragment_delay = conservative_delay

            passed = False
            for _ in range(3):
                probe = self._probe_echo(256, timeout=timeout)
                if probe["passed"]:
                    passed = True
                    break

            result["tests"].append(
                {"phase": "size", "fragment_size": size, "passed": passed}
            )

            if passed:
                best_size = size
                break  # largest first, so first pass is best

        if best_size == 0:
            # Restore originals
            self.device.serial_tx_fragment_size = orig_size
            self.device.serial_tx_fragment_delay = orig_delay
            result["error"] = "All fragment sizes failed"
            return result

        # Step 2: fix size, try reducing delay
        best_delay = conservative_delay
        self.device.serial_tx_fragment_size = best_size
        test_delays = [0.003, 0.002, 0.001]

        for delay in test_delays:
            self.device.serial_tx_fragment_delay = delay
            # Verify 3 times for stability
            passed = True
            for _ in range(3):
                probe = self._probe_echo(256, timeout=timeout)
                if not probe["passed"]:
                    passed = False
                    break

            result["tests"].append(
                {"phase": "delay", "fragment_delay": delay, "passed": passed}
            )

            if passed:
                best_delay = delay
            else:
                break  # delays are decreasing, stop at first failure

        # Apply best params
        self.device.serial_tx_fragment_size = best_size
        self.device.serial_tx_fragment_delay = best_delay

        result["success"] = True
        result["recommended_fragment_size"] = best_size
        result["recommended_fragment_delay"] = best_delay
        return result

    def _sample_probe(
        self,
        probe_fn,
        size: int,
        timeout: float,
        trials: int,
        min_success_rate: float,
    ) -> Dict:
        """Run a single-shot probe multiple times and aggregate reliability.

        The old strategy tested each size once (with retries that stopped on
        the first success), which masks intermittent loss and can accept a
        size that only works by luck. This runs ``trials`` independent probes
        with no early exit, then marks the size as passed only if the observed
        success rate meets ``min_success_rate`` — turning the throughput test
        into an actual reliability stress test.

        Args:
            probe_fn: ``_probe_echo`` or ``_probe_echoback``.
            size: Payload size under test.
            timeout: Per-probe timeout.
            trials: Number of independent round-trips to run.
            min_success_rate: Fraction in [0, 1] required to consider the size
                reliable (1.0 = every trial must pass).

        Returns:
            Aggregated dict compatible with the single-probe result (keys:
            size, passed, response_time_ms, error, cmd_len) plus reliability
            fields (trials, passes, success_rate, min_ms, max_ms).
        """
        passes = 0
        latencies = []
        last_error = None
        cmd_len = 0
        for _ in range(max(1, trials)):
            probe = probe_fn(size, timeout=timeout)
            if probe.get("cmd_len"):
                cmd_len = probe["cmd_len"]
            if probe.get("passed"):
                passes += 1
                rt = probe.get("response_time_ms")
                if rt:
                    latencies.append(rt)
            else:
                last_error = probe.get("error") or last_error

        trials_run = max(1, trials)
        success_rate = passes / trials_run
        passed = success_rate >= min_success_rate
        avg_ms = round(sum(latencies) / len(latencies), 2) if latencies else 0
        result: Dict = {
            "size": size,
            "trials": trials_run,
            "passes": passes,
            "success_rate": round(success_rate, 3),
            "passed": passed,
            "response_time_ms": avg_ms,
            "min_ms": round(min(latencies), 2) if latencies else 0,
            "max_ms": round(max(latencies), 2) if latencies else 0,
            "cmd_len": cmd_len,
            "error": (
                None if passed else (last_error or f"{passes}/{trials_run} passed")
            ),
        }
        return result

    def _phase_upload_probe(
        self,
        start_size: int = 16,
        max_size: int = 512,
        timeout: float = 2.0,
        trials: int = 8,
        min_success_rate: float = 1.0,
    ) -> Dict:
        """Phase 2: Find the device shell receive buffer limit (upload direction).

        Uses increasing echo commands with x1.4 stepping. Each size is sampled
        ``trials`` times and must meet ``min_success_rate`` to be accepted, so
        the reported max working size is a reliable limit, not a lucky one-off.
        """
        result: Dict = {
            "max_working_size": 0,
            "failed_size": 0,
            "recommended_upload_chunk_size": 0,
            "tests": [],
            "trials": trials,
            "min_success_rate": min_success_rate,
        }

        test_size = start_size
        max_working = 0

        while test_size <= max_size:
            probe = self._sample_probe(
                self._probe_echo,
                test_size,
                timeout=timeout,
                trials=trials,
                min_success_rate=min_success_rate,
            )
            result["tests"].append(probe)

            if probe["passed"]:
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
          Request:  fl -c echoback -l {N}
          Response: [FLOK] ECHOBACK {N} bytes crc=0x{CRC} data={base64}

        Returns a test_result dict with keys: size, passed, error,
        response_time_ms.
        """
        cmd = f"-c echoback -l {test_size}"

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
        trials: int = 8,
        min_success_rate: float = 1.0,
    ) -> Dict:
        """Phase 3: Find the max reliable download chunk size.

        Uses the `echoback` command to have the device generate and send
        increasing amounts of data. The device reuses its send buffer to
        fill with a pattern, so no RAM allocation is needed. Each size is
        sampled ``trials`` times and must meet ``min_success_rate``.
        """
        result: Dict = {
            "max_working_size": 0,
            "failed_size": 0,
            "recommended_download_chunk_size": DEFAULT_DOWNLOAD_CHUNK_SIZE,
            "tests": [],
            "skipped": False,
            "trials": trials,
            "min_success_rate": min_success_rate,
        }

        # Quick capability check: does the device support echoback at all?
        # A single unsupported/no-response reply means we should skip cleanly
        # rather than sample it many times.
        capability = self._probe_echoback(start_size, timeout=timeout)
        if capability.get("error") and (
            "Device returned error" in (capability["error"] or "")
            or "No response" in (capability["error"] or "")
        ):
            result["skipped"] = True
            result["skip_reason"] = (
                f"Device does not support echoback command: {capability['error']}"
            )
            return result

        probe = self._sample_probe(
            self._probe_echoback,
            start_size,
            timeout=timeout,
            trials=trials,
            min_success_rate=min_success_rate,
        )
        result["tests"].append(probe)
        if not probe["passed"]:
            result["failed_size"] = start_size
            return result

        max_working = start_size
        test_size = max(start_size + 64, int(start_size * 1.5) // 64 * 64)

        while test_size <= max_size:
            probe = self._sample_probe(
                self._probe_echoback,
                test_size,
                timeout=timeout,
                trials=trials,
                min_success_rate=min_success_rate,
            )
            result["tests"].append(probe)

            if probe["passed"]:
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
        self,
        start_size: int = 16,
        max_size: int = 512,
        timeout: float = 2.0,
        trials: int = 8,
        min_success_rate: float = 1.0,
    ) -> Dict:
        """Test serial throughput with 3-phase probing.

        Each candidate size is sampled ``trials`` times and only accepted if
        its success rate reaches ``min_success_rate`` (1.0 = must pass every
        trial), so the recommended chunk sizes reflect reliable limits under
        repeated load rather than a single lucky round-trip.

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
                "recommended_download_chunk_size": DEFAULT_DOWNLOAD_CHUNK_SIZE,
                "fragment_needed": False,
            }

        results: Dict = {
            "success": True,
            "max_working_size": 0,
            "failed_size": 0,
            "tests": [],
            "recommended_upload_chunk_size": 16,
            "recommended_download_chunk_size": DEFAULT_DOWNLOAD_CHUNK_SIZE,
            "fragment_needed": False,
            "phases": {},
        }

        try:
            # Phase 1: TX Fragment probe
            frag = self._phase_fragment_probe(timeout=timeout)
            results["phases"]["fragment"] = frag
            results["fragment_needed"] = frag["needed"]

            # Phase 1.5: If fragmentation needed, probe optimal params
            if frag["needed"]:
                frag_probe = self._phase_fragment_size_probe(timeout=timeout)
                results["phases"]["fragment_probe"] = frag_probe

                if frag_probe["success"]:
                    results["recommended_fragment_size"] = frag_probe[
                        "recommended_fragment_size"
                    ]
                    results["recommended_fragment_delay"] = frag_probe[
                        "recommended_fragment_delay"
                    ]
                else:
                    results["success"] = False
                    results["error"] = (
                        "TX fragmentation probe failed: "
                        + frag_probe.get("error", "unknown")
                    )
                    return results

            # Phase 2: Upload chunk probe
            # (now works correctly with fragmentation if Phase 1.5 set it)
            upload = self._phase_upload_probe(
                start_size=start_size,
                max_size=max_size,
                timeout=timeout,
                trials=trials,
                min_success_rate=min_success_rate,
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
                trials=trials,
                min_success_rate=min_success_rate,
            )
            results["phases"]["download"] = download
            results["recommended_download_chunk_size"] = download[
                "recommended_download_chunk_size"
            ]

        except Exception as e:
            results["success"] = False
            results["error"] = str(e)

        return results
