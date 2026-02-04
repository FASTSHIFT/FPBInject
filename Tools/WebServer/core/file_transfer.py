#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
File transfer module for FPBInject Web Server.

Provides file upload/download functionality between PC and embedded device
via serial port using the func_loader file transfer protocol.
"""

import base64
import logging
import re
from typing import Callable, Optional, Tuple, List, Dict, Any

from utils.crc import crc16

logger = logging.getLogger(__name__)


class FileTransfer:
    """File transfer handler for device communication."""

    DEFAULT_CHUNK_SIZE = 256
    DEFAULT_MAX_RETRIES = 10

    def __init__(
        self,
        fpb_inject,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        max_retries: int = DEFAULT_MAX_RETRIES,
        log_callback: Callable[[str], None] = None,
    ):
        """
        Initialize file transfer handler.

        Args:
            fpb_inject: FPBInject instance for device communication
            chunk_size: Size of data chunks for transfer (default 256)
            max_retries: Maximum retry attempts for transfer (default 10)
            log_callback: Optional callback for logging transfer events to UI
        """
        self.fpb = fpb_inject
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.log_callback = log_callback

        # Transfer statistics
        self.stats = {
            "total_chunks": 0,
            "retry_count": 0,
            "crc_errors": 0,
            "timeout_errors": 0,
            "other_errors": 0,
        }

    def _log(self, message: str):
        """Log message to both logger and UI callback."""
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    def reset_stats(self):
        """Reset transfer statistics."""
        self.stats = {
            "total_chunks": 0,
            "retry_count": 0,
            "crc_errors": 0,
            "timeout_errors": 0,
            "other_errors": 0,
        }

    def get_stats(self) -> dict:
        """Get transfer statistics including packet loss rate."""
        stats = self.stats.copy()
        total = stats["total_chunks"]
        retries = stats["retry_count"]
        if total > 0:
            # Packet loss rate = retries / (total + retries) * 100
            stats["packet_loss_rate"] = round(retries / (total + retries) * 100, 2)
        else:
            stats["packet_loss_rate"] = 0.0
        return stats

    def _send_cmd(self, cmd: str, timeout: float = 2.0) -> Tuple[bool, str]:
        """
        Send a command to device and get response.

        Args:
            cmd: Command string to send
            timeout: Response timeout in seconds

        Returns:
            Tuple of (success, response_message)
        """
        return self.fpb.send_fl_cmd(cmd, timeout=timeout)

    def fopen(self, path: str, mode: str = "r") -> Tuple[bool, str]:
        """
        Open a file on device.

        Args:
            path: File path on device
            mode: Open mode ("r", "w", "a", "rw")

        Returns:
            Tuple of (success, message)
        """
        cmd = f'fl -c fopen --path "{path}" --mode {mode}'
        return self._send_cmd(cmd)

    def fwrite(
        self, data: bytes, max_retries: int = None, current_offset: int = None
    ) -> Tuple[bool, str]:
        """
        Write data to open file on device with retry support.

        Args:
            data: Data bytes to write
            max_retries: Maximum retry attempts (default: self.max_retries)
            current_offset: Current file offset for seek on retry (optional)

        Returns:
            Tuple of (success, message)
        """
        if max_retries is None:
            max_retries = self.max_retries

        b64_data = base64.b64encode(data).decode("ascii")
        crc = crc16(data)
        cmd = f"fl -c fwrite --data {b64_data} --crc {crc}"
        self.stats["total_chunks"] += 1
        data_len = len(data)

        for attempt in range(max_retries + 1):
            # On retry, seek back to the correct position
            if attempt > 0:
                self.stats["retry_count"] += 1
                if current_offset is not None:
                    log_msg = f"[TRANSFER] fwrite retry {attempt}/{max_retries}, offset={current_offset}, len={data_len}"
                    self._log(log_msg)
                    logger.warning(
                        f"fwrite retry {attempt}/{max_retries}, seeking to offset {current_offset}"
                    )
                    seek_success, seek_msg = self.fseek(current_offset, 0)
                    if not seek_success:
                        logger.error(f"fseek failed during retry: {seek_msg}")
                        # Continue anyway, maybe the write will work

            success, response = self._send_cmd(cmd)
            if success:
                return True, response

            # Check if it's a CRC mismatch (retryable)
            if "CRC mismatch" in response and attempt < max_retries:
                log_msg = f"[TRANSFER] fwrite CRC mismatch at offset={current_offset}, len={data_len}, retry {attempt + 1}/{max_retries}"
                self._log(log_msg)
                logger.warning(
                    f"fwrite CRC mismatch, retry {attempt + 1}/{max_retries}"
                )
                self.stats["crc_errors"] += 1
                continue

            if attempt < max_retries:
                self.stats["other_errors"] += 1
                continue

            return False, response

        return False, "Max retries exceeded"

    def fread(
        self, size: int = None, max_retries: int = None, current_offset: int = None
    ) -> Tuple[bool, bytes, str]:
        """
        Read data from open file on device with retry support.

        Args:
            size: Maximum bytes to read (default: chunk_size)
            max_retries: Maximum retry attempts (default: self.max_retries)
            current_offset: Current file offset for seek on retry (optional)

        Returns:
            Tuple of (success, data_bytes, message)
        """
        if size is None:
            size = self.chunk_size
        if max_retries is None:
            max_retries = self.max_retries

        cmd = f"fl -c fread --len {size}"
        self.stats["total_chunks"] += 1

        for attempt in range(max_retries + 1):
            # On retry, seek back to the correct position
            if attempt > 0:
                self.stats["retry_count"] += 1
                if current_offset is not None:
                    log_msg = f"[TRANSFER] fread retry {attempt}/{max_retries}, offset={current_offset}, len={size}"
                    self._log(log_msg)
                    logger.warning(
                        f"fread retry {attempt}/{max_retries}, seeking to offset {current_offset}"
                    )
                    seek_success, seek_msg = self.fseek(current_offset, 0)
                    if not seek_success:
                        logger.error(f"fseek failed during retry: {seek_msg}")
                        # Continue anyway, maybe the read will work

            success, response = self._send_cmd(cmd)

            if not success:
                if attempt < max_retries:
                    log_msg = f"[TRANSFER] fread timeout at offset={current_offset}, len={size}, retry {attempt + 1}/{max_retries}"
                    self._log(log_msg)
                    logger.warning(f"fread failed, retry {attempt + 1}/{max_retries}")
                    self.stats["timeout_errors"] += 1
                    continue
                return False, b"", response

            # Parse response: [FLOK] FREAD <n> bytes crc=0x<crc> data=<base64>
            # or: [FLOK] FREAD 0 bytes EOF
            match = re.search(
                r"FREAD\s+(\d+)\s+bytes(?:\s+crc=0x([0-9A-Fa-f]+)\s+data=(\S+))?",
                response,
            )
            if not match:
                if "EOF" in response:
                    return True, b"", "EOF"
                if attempt < max_retries:
                    logger.warning(
                        f"fread invalid response, retry {attempt + 1}/{max_retries}"
                    )
                    self.stats["other_errors"] += 1
                    continue
                return False, b"", f"Invalid response: {response}"

            nbytes = int(match.group(1))
            if nbytes == 0:
                return True, b"", "EOF"

            crc_str = match.group(2)
            b64_data = match.group(3)

            if not b64_data:
                if attempt < max_retries:
                    logger.warning(f"fread no data, retry {attempt + 1}/{max_retries}")
                    self.stats["other_errors"] += 1
                    continue
                return False, b"", "No data in response"

            try:
                data = base64.b64decode(b64_data)
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(
                        f"fread base64 error, retry {attempt + 1}/{max_retries}: {e}"
                    )
                    self.stats["other_errors"] += 1
                    continue
                return False, b"", f"Base64 decode error: {e}"

            # Verify CRC
            if crc_str:
                expected_crc = int(crc_str, 16)
                actual_crc = crc16(data)
                if expected_crc != actual_crc:
                    if attempt < max_retries:
                        log_msg = f"fread CRC mismatch: expected 0x{expected_crc:04X}, got 0x{actual_crc:04X}, at offset={current_offset}, len={len(data)}, retry {attempt + 1}/{max_retries}"
                        self._log("[TRANSFER] " + log_msg)
                        logger.warning(log_msg)
                        self.stats["crc_errors"] += 1
                        continue
                    return (
                        False,
                        b"",
                        f"CRC mismatch: expected 0x{expected_crc:04X}, got 0x{actual_crc:04X}",
                    )

            return True, data, f"Read {len(data)} bytes"

        return False, b"", "Max retries exceeded"

        return True, data, f"Read {len(data)} bytes"

    def fclose(self) -> Tuple[bool, str]:
        """
        Close open file on device.

        Returns:
            Tuple of (success, message)
        """
        return self._send_cmd("fl -c fclose")

    def fseek(self, offset: int, whence: int = 0) -> Tuple[bool, str]:
        """
        Seek to position in open file on device.

        Args:
            offset: Offset in bytes
            whence: 0=SEEK_SET (from start), 1=SEEK_CUR (from current), 2=SEEK_END (from end)

        Returns:
            Tuple of (success, message)
        """
        cmd = f"fl -c fseek -a {offset}"
        return self._send_cmd(cmd)

    def fstat(self, path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Get file status on device.

        Args:
            path: File path on device

        Returns:
            Tuple of (success, stat_dict)
            stat_dict contains: size, mtime, type
        """
        cmd = f'fl -c fstat --path "{path}"'
        success, response = self._send_cmd(cmd)

        if not success:
            return False, {"error": response}

        # Parse: [FLOK] FSTAT <path> size=<n> mtime=<t> type=<file|dir>
        match = re.search(
            r"FSTAT\s+\S+\s+size=(\d+)\s+mtime=(\d+)\s+type=(\w+)", response
        )
        if not match:
            return False, {"error": f"Invalid response: {response}"}

        return True, {
            "size": int(match.group(1)),
            "mtime": int(match.group(2)),
            "type": match.group(3),
        }

    def flist(self, path: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        List directory contents on device.

        Args:
            path: Directory path on device

        Returns:
            Tuple of (success, entries_list)
            Each entry contains: name, type, size
        """
        cmd = f'fl -c flist --path "{path}"'
        success, response = self._send_cmd(cmd, timeout=5.0)

        if not success:
            return False, []

        entries = []
        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()
            # Parse: D <name> or F <name> <size>
            if line.startswith("D "):
                name = line[2:].strip()
                entries.append({"name": name, "type": "dir", "size": 0})
            elif line.startswith("F "):
                parts = line[2:].strip().rsplit(" ", 1)
                if len(parts) == 2:
                    name, size_str = parts
                    try:
                        size = int(size_str)
                    except ValueError:
                        size = 0
                else:
                    name = parts[0]
                    size = 0
                entries.append({"name": name, "type": "file", "size": size})

        return True, entries

    def fremove(self, path: str) -> Tuple[bool, str]:
        """
        Remove a file on device.

        Args:
            path: File path to remove

        Returns:
            Tuple of (success, message)
        """
        cmd = f'fl -c fremove --path "{path}"'
        return self._send_cmd(cmd)

    def fmkdir(self, path: str) -> Tuple[bool, str]:
        """
        Create a directory on device.

        Args:
            path: Directory path to create

        Returns:
            Tuple of (success, message)
        """
        cmd = f'fl -c fmkdir --path "{path}"'
        return self._send_cmd(cmd)

    def frename(self, old_path: str, new_path: str) -> Tuple[bool, str]:
        """
        Rename a file or directory on device.

        Args:
            old_path: Current path
            new_path: New path

        Returns:
            Tuple of (success, message)
        """
        cmd = f'fl -c frename --path "{old_path}" --newpath "{new_path}"'
        return self._send_cmd(cmd)

    def upload(
        self,
        local_data: bytes,
        remote_path: str,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[bool, str]:
        """
        Upload data to a file on device.

        Args:
            local_data: Data bytes to upload
            remote_path: Destination path on device
            progress_cb: Optional callback(uploaded_bytes, total_bytes)

        Returns:
            Tuple of (success, message)
        """
        total_size = len(local_data)

        # Open file for writing
        success, msg = self.fopen(remote_path, "w")
        if not success:
            return False, f"Failed to open file: {msg}"

        try:
            uploaded = 0
            while uploaded < total_size:
                chunk = local_data[uploaded : uploaded + self.chunk_size]
                # Pass current offset for seek on retry
                success, msg = self.fwrite(chunk, current_offset=uploaded)
                if not success:
                    self.fclose()
                    return False, f"Write failed at offset {uploaded}: {msg}"

                uploaded += len(chunk)
                if progress_cb:
                    progress_cb(uploaded, total_size)

            # Close file
            success, msg = self.fclose()
            if not success:
                return False, f"Failed to close file: {msg}"

            return True, f"Uploaded {total_size} bytes to {remote_path}"

        except Exception as e:
            self.fclose()
            return False, f"Upload error: {e}"

    def download(
        self,
        remote_path: str,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[bool, bytes, str]:
        """
        Download a file from device.

        Args:
            remote_path: Source path on device
            progress_cb: Optional callback(downloaded_bytes, total_bytes)

        Returns:
            Tuple of (success, data_bytes, message)
        """
        # Get file size first
        success, stat = self.fstat(remote_path)
        if not success:
            return False, b"", f"Failed to stat file: {stat.get('error', 'unknown')}"

        total_size = stat.get("size", 0)
        if stat.get("type") == "dir":
            return False, b"", "Cannot download directory"

        # Open file for reading
        success, msg = self.fopen(remote_path, "r")
        if not success:
            return False, b"", f"Failed to open file: {msg}"

        try:
            data = b""
            current_offset = 0
            while True:
                # Pass current offset for seek on retry
                success, chunk, msg = self.fread(
                    self.chunk_size, current_offset=current_offset
                )
                if not success:
                    self.fclose()
                    return False, b"", f"Read failed: {msg}"

                if msg == "EOF" or len(chunk) == 0:
                    break

                data += chunk
                current_offset += len(chunk)
                if progress_cb:
                    progress_cb(len(data), total_size)

            # Close file
            self.fclose()

            return True, data, f"Downloaded {len(data)} bytes from {remote_path}"

        except Exception as e:
            self.fclose()
            return False, b"", f"Download error: {e}"
