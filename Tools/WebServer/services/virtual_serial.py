#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Virtual serial passthrough for FPBInject Web Server.

Creates a PTY (pseudo-terminal) whose slave end is a real device file
(e.g. /dev/pts/7) that external serial tools (minicom, pyserial, screen)
can open. Bytes are transparently forwarded to/from the physical serial
port, which remains exclusively owned by the DeviceWorker thread.

All PTY I/O is performed from the DeviceWorker thread (single owner),
so no additional locking is required and the physical-port single-owner
invariant (ThreadCheckedSerial) is preserved.

During FPB binary-protocol operations (inject / mem / file transfer) the
passthrough is *muted* by the worker so external bytes cannot corrupt
protocol frames.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Upper bound for buffered external input while muted (bytes).
_MAX_MUTE_BUFFER = 4096


class VirtualSerialService:
    """PTY-backed virtual serial passthrough.

    Lifecycle and I/O are driven by the DeviceWorker thread. Only
    ``start``/``stop``/``status`` are safe to call from other threads.
    """

    def __init__(self, device_state):
        self.device = device_state
        self._master_fd = None
        self._slave_name = None
        self._symlink_path = None
        self._enabled = False
        self._muted = False
        self._mute_policy = "buffer"  # "buffer" | "drop"
        self._mute_buffer = bytearray()

    # ------------------------------------------------------------------
    # Lifecycle (may be called from request threads)
    # ------------------------------------------------------------------
    def start(self, symlink="/tmp/fpb-tty0", mute_policy="buffer"):
        """Create the PTY and optional stable symlink.

        Returns (success: bool, error: str|None).
        """
        if self._enabled:
            return True, None

        if not hasattr(os, "openpty"):
            return False, "PTY not supported on this platform"

        self._mute_policy = (
            mute_policy if mute_policy in ("buffer", "drop") else "buffer"
        )

        try:
            master_fd, slave_fd = os.openpty()
        except OSError as e:
            return False, f"openpty failed: {e}"

        # Configure raw mode on both ends for transparent byte passthrough.
        try:
            import tty

            tty.setraw(master_fd)
            tty.setraw(slave_fd)
        except Exception as e:  # termios may be missing; non-fatal
            logger.debug(f"Could not set raw mode: {e}")

        # Master is polled non-blocking from the worker loop.
        os.set_blocking(master_fd, False)

        self._slave_name = os.ttyname(slave_fd)
        # The slave fd is only needed to materialize /dev/pts/N; the external
        # program opens it by name. Keep it open so the pts node persists.
        self._slave_fd = slave_fd
        self._master_fd = master_fd

        # Create stable symlink alias.
        self._symlink_path = None
        if symlink:
            try:
                if os.path.islink(symlink) or os.path.exists(symlink):
                    os.unlink(symlink)
                os.symlink(self._slave_name, symlink)
                self._symlink_path = symlink
            except OSError as e:
                logger.warning(f"Could not create symlink {symlink}: {e}")

        self._muted = False
        self._mute_buffer = bytearray()
        self._enabled = True
        logger.info(
            f"Virtual serial started: {self._slave_name}"
            + (f" (-> {self._symlink_path})" if self._symlink_path else "")
        )
        return True, None

    def stop(self):
        """Tear down the PTY and remove the symlink."""
        if not self._enabled:
            return

        if self._symlink_path:
            try:
                if os.path.islink(self._symlink_path):
                    os.unlink(self._symlink_path)
            except OSError:
                pass

        for fd_attr in ("_master_fd", "_slave_fd"):
            fd = getattr(self, fd_attr, None)
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
                setattr(self, fd_attr, None)

        self._enabled = False
        self._muted = False
        self._mute_buffer = bytearray()
        logger.info("Virtual serial stopped")

    def is_enabled(self):
        return self._enabled

    def status(self):
        """Return a JSON-serializable status dict."""
        return {
            "enabled": self._enabled,
            "slave": self._slave_name,
            "symlink": self._symlink_path,
            "muted": self._muted,
            "mute_policy": self._mute_policy,
        }

    # ------------------------------------------------------------------
    # Gate control (worker thread)
    # ------------------------------------------------------------------
    def mute(self):
        """Close the passthrough gate (during FPB protocol operations)."""
        self._muted = True

    def unmute(self):
        """Reopen the gate and flush any buffered external input."""
        self._muted = False

    # ------------------------------------------------------------------
    # Data plane (worker thread only)
    # ------------------------------------------------------------------
    def forward_rx(self, data):
        """Forward physical-serial RX bytes to the PTY master.

        Skipped while muted so binary protocol frames don't reach the
        user's terminal as garbage.
        """
        if not self._enabled or self._master_fd is None:
            return
        if self._muted or not data:
            return
        try:
            os.write(self._master_fd, data)
        except BlockingIOError:
            pass  # External reader not draining; drop to avoid blocking worker
        except OSError as e:
            logger.debug(f"forward_rx write error: {e}")

    def poll_tx(self):
        """Read external input from the PTY master (non-blocking).

        Returns bytes to write to the physical port, or None. While muted,
        input is buffered (bounded) or dropped per policy; the buffer is
        flushed on the first poll after unmute.
        """
        if not self._enabled or self._master_fd is None:
            return None

        chunk = None
        try:
            chunk = os.read(self._master_fd, 4096)
        except (BlockingIOError, InterruptedError):
            chunk = None
        except OSError:
            chunk = None

        if self._muted:
            if chunk and self._mute_policy == "buffer":
                room = _MAX_MUTE_BUFFER - len(self._mute_buffer)
                if room > 0:
                    self._mute_buffer.extend(chunk[:room])
            return None

        # Not muted: flush any buffered input first, then current chunk.
        out = bytearray()
        if self._mute_buffer:
            out.extend(self._mute_buffer)
            self._mute_buffer = bytearray()
        if chunk:
            out.extend(chunk)
        return bytes(out) if out else None
