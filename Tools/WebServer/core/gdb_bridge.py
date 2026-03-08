#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
GDB RSP Bridge for FPBInject Web Server.

Implements a minimal GDB Remote Serial Protocol (RSP) server that bridges
GDB memory read/write requests to the device's fl serial commands.

This allows GDB to connect and use its native ELF/DWARF parsing capabilities
(symbol lookup, type resolution, struct layout).
"""

import logging
import socket
import threading
from typing import Callable, Optional, Tuple

logger = logging.getLogger(__name__)

# ARM Cortex-M has 16 core registers (R0-R12, SP, LR, PC) + xPSR = 17
# Each register is 4 bytes = 8 hex chars
ARM_NUM_REGS = 17
ARM_REG_SIZE = 4  # bytes


def _checksum(data: str) -> int:
    """Calculate GDB RSP checksum (sum of bytes mod 256)."""
    return sum(ord(c) for c in data) & 0xFF


def _encode_packet(data: str) -> bytes:
    """Encode a GDB RSP packet: $<data>#<checksum>."""
    cs = _checksum(data)
    return f"${data}#{cs:02x}".encode("ascii")


def _parse_packet(raw: bytes) -> Optional[str]:
    """Parse a GDB RSP packet, return data string or None."""
    text = raw.decode("ascii", errors="replace")
    # Find $ ... # xx
    start = text.find("$")
    if start < 0:
        return None
    end = text.find("#", start)
    if end < 0:
        return None
    return text[start + 1 : end]


class GDBRSPBridge:
    """Minimal GDB RSP server bridging memory access to fl serial commands.

    Only implements the subset of RSP needed for:
    - Connection handshake (?, qSupported, qAttached, Hg, Hc)
    - Memory read (m addr,length)
    - Memory write (M addr,length:data)
    - Register read (g) - returns fake data
    - Disconnect (k)

    Args:
        read_memory_fn: Callable(addr, length) -> (bytes|None, str)
        write_memory_fn: Callable(addr, bytes) -> (bool, str)
        listen_port: TCP port to listen on (default 3333)
    """

    def __init__(
        self,
        read_memory_fn: Callable[[int, int], Tuple[Optional[bytes], str]],
        write_memory_fn: Callable[[int, bytes], Tuple[bool, str]],
        listen_port: int = 3333,
    ):
        self._read_memory = read_memory_fn
        self._write_memory = write_memory_fn
        self._port = listen_port
        self._server: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._client: Optional[socket.socket] = None
        self._actual_port: Optional[int] = None

    @property
    def port(self) -> int:
        """Return the actual listening port (may differ if 0 was requested)."""
        return self._actual_port or self._port

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> int:
        """Start the RSP server. Returns the actual port number."""
        if self._running:
            return self.port

        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.settimeout(1.0)
        self._server.bind(("127.0.0.1", self._port))
        self._server.listen(1)
        self._actual_port = self._server.getsockname()[1]
        self._running = True

        self._thread = threading.Thread(
            target=self._accept_loop, name="gdb-rsp", daemon=True
        )
        self._thread.start()
        logger.info(f"GDB RSP bridge listening on 127.0.0.1:{self.port}")
        return self.port

    def stop(self):
        """Stop the RSP server and close all connections."""
        self._running = False
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        if self._server:
            try:
                self._server.close()
            except Exception:
                pass
            self._server = None
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("GDB RSP bridge stopped")

    def _accept_loop(self):
        """Accept loop: wait for GDB connections."""
        while self._running:
            try:
                client, addr = self._server.accept()
                logger.info(f"GDB connected from {addr}")
                self._client = client
                self._handle_client(client)
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    logger.debug("RSP server socket closed")
                break
            except Exception as e:
                if self._running:
                    logger.error(f"RSP accept error: {e}")
                break

    def _handle_client(self, client: socket.socket):
        """Handle a single GDB client connection."""
        client.settimeout(2.0)
        buf = b""

        while self._running:
            try:
                chunk = client.recv(4096)
                if not chunk:
                    break
                buf += chunk
            except socket.timeout:
                continue
            except OSError:
                break

            # Process all complete packets in buffer
            while buf:
                # Handle ACK/NACK
                if buf[0:1] == b"+":
                    buf = buf[1:]
                    continue
                if buf[0:1] == b"-":
                    buf = buf[1:]
                    continue

                # Handle interrupt (Ctrl-C)
                if buf[0:1] == b"\x03":
                    buf = buf[1:]
                    self._send(client, "S05")
                    continue

                # Find complete packet
                start = buf.find(b"$")
                if start < 0:
                    buf = b""
                    break
                end = buf.find(b"#", start)
                if end < 0:
                    break  # incomplete packet
                if end + 2 >= len(buf):
                    break  # checksum not yet received

                packet_raw = buf[start : end + 3]
                buf = buf[end + 3 :]

                data = _parse_packet(packet_raw)
                if data is None:
                    client.sendall(b"-")
                    continue

                # ACK
                client.sendall(b"+")

                # Handle packet
                response = self._handle_packet(data)
                if response is None:
                    # 'k' (kill) returns None to signal disconnect
                    client.close()
                    self._client = None
                    logger.info("GDB disconnected (kill)")
                    return

                self._send(client, response)

        try:
            client.close()
        except Exception:
            pass
        self._client = None
        logger.info("GDB disconnected")

    def _send(self, client: socket.socket, data: str):
        """Send an RSP packet to the client."""
        try:
            client.sendall(_encode_packet(data))
        except Exception as e:
            logger.debug(f"RSP send error: {e}")

    def _handle_packet(self, data: str) -> Optional[str]:
        """Route a GDB RSP packet to the appropriate handler.

        Returns response string, or None for disconnect.
        """
        if not data:
            return ""

        cmd = data[0]

        # Connection handshake
        if data == "?":
            return "S05"  # SIGTRAP - target is "stopped"

        if data.startswith("qSupported"):
            return "PacketSize=4096;QStartNoAckMode+"

        if data == "QStartNoAckMode":
            return "OK"

        if data == "qAttached":
            return "1"  # Attached to existing process

        if data.startswith("qTStatus"):
            return ""  # No tracepoints

        if data.startswith("qfThreadInfo"):
            return "m1"  # One thread with id 1

        if data.startswith("qsThreadInfo"):
            return "l"  # End of thread list

        if data.startswith("qC"):
            return "QC1"  # Current thread is 1

        if data.startswith("Hg") or data.startswith("Hc"):
            return "OK"  # Set thread - always OK

        # Register read (fake - all zeros)
        if cmd == "g":
            return "0" * (ARM_NUM_REGS * ARM_REG_SIZE * 2)

        # Register write (ignore)
        if cmd == "G":
            return "OK"

        # Single register read
        if cmd == "p":
            return "0" * (ARM_REG_SIZE * 2)

        # Memory read: m addr,length
        if cmd == "m":
            return self._handle_read(data[1:])

        # Memory write: M addr,length:XX..
        if cmd == "M":
            return self._handle_write(data[1:])

        # Binary memory write: X addr,length:data
        if cmd == "X":
            # We don't support binary protocol, return error
            return ""

        # Continue / Step (fake - immediately "stop" again)
        if cmd in ("c", "s", "C", "S"):
            return "S05"

        # vCont
        if data.startswith("vCont?"):
            return "vCont;c;s"
        if data.startswith("vCont"):
            return "S05"

        # Kill
        if cmd == "k":
            return None

        # Detach
        if cmd == "D":
            return "OK"

        # Unknown - empty response means "not supported"
        return ""

    def _handle_read(self, params: str) -> str:
        """Handle memory read: m addr,length -> hex bytes or Exx."""
        try:
            addr_str, len_str = params.split(",")
            addr = int(addr_str, 16)
            length = int(len_str, 16)
        except (ValueError, IndexError):
            return "E01"

        if length == 0:
            return ""

        # Cap single read to reasonable size
        if length > 4096:
            length = 4096

        try:
            data, msg = self._read_memory(addr, length)
            if data is not None:
                return data.hex()
            else:
                logger.debug(f"RSP read 0x{addr:08X}+{length} failed: {msg}")
                return "E01"
        except Exception as e:
            logger.error(f"RSP read error: {e}")
            return "E01"

    def _handle_write(self, params: str) -> str:
        """Handle memory write: M addr,length:XX.. -> OK or Exx."""
        try:
            header, hex_data = params.split(":", 1)
            addr_str, len_str = header.split(",")
            addr = int(addr_str, 16)
            length = int(len_str, 16)
            write_data = bytes.fromhex(hex_data)
        except (ValueError, IndexError):
            return "E01"

        if len(write_data) != length:
            return "E01"

        try:
            ok, msg = self._write_memory(addr, write_data)
            if ok:
                return "OK"
            else:
                logger.debug(f"RSP write 0x{addr:08X}+{length} failed: {msg}")
                return "E01"
        except Exception as e:
            logger.error(f"RSP write error: {e}")
            return "E01"
