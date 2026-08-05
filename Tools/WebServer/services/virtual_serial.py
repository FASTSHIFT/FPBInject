#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Virtual serial passthrough for FPBInject Web Server.

Creates a PTY (pseudo-terminal) whose slave end is a real device file
(e.g. /dev/pts/7) that external serial tools (minicom, pyserial, screen)
can open. Bytes are transparently forwarded to/from the physical serial
port, which remains exclusively owned by the DeviceWorker thread.

Full passthrough: the device->host stream is mirrored via a tee installed
on ThreadCheckedSerial, so it captures *all* traffic — including FPB
binary-protocol I/O (inject / mem / file transfer) that bypasses the
worker's RX polling path. The host->device stream (external input) is
polled from the PTY master in the worker loop and written to the port.

All PTY I/O is performed from the DeviceWorker thread (single owner), so
no additional locking is required and the physical-port single-owner
invariant (ThreadCheckedSerial) is preserved.
"""

import logging
import os

logger = logging.getLogger(__name__)


class VirtualSerialService:
    """PTY-backed virtual serial passthrough.

    Lifecycle and I/O are driven by the DeviceWorker thread. Only
    ``start``/``stop``/``status`` are safe to call from other threads.
    """

    def __init__(self, device_state):
        self.device = device_state
        self._master_fd = None
        self._slave_fd = None
        self._slave_name = None
        self._symlink_path = None
        self._enabled = False

    # ------------------------------------------------------------------
    # Lifecycle (may be called from request threads)
    # ------------------------------------------------------------------
    def start(self, symlink="/tmp/fpb-tty0", mute_policy=None):
        """Create the PTY and optional stable symlink.

        ``mute_policy`` is accepted for backward-compatible call sites but
        ignored: passthrough is now unconditional (full transparency).

        Returns (success: bool, error: str|None).
        """
        if self._enabled:
            return True, None

        if not hasattr(os, "openpty"):
            return False, "PTY not supported on this platform"

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

        self._enabled = True

        # Install a tee on the serial wrapper so ALL device->host bytes are
        # mirrored to the PTY, including protocol traffic that never reaches
        # the worker RX polling path.
        ser = getattr(self.device, "ser", None)
        if ser is not None and hasattr(ser, "set_tee"):
            ser.set_tee(rx=self.forward_rx)

        logger.info(
            f"Virtual serial started: {self._slave_name}"
            + (f" (-> {self._symlink_path})" if self._symlink_path else "")
        )
        return True, None

    def stop(self):
        """Tear down the PTY and remove the symlink."""
        if not self._enabled:
            return

        # Remove the tee from the serial wrapper.
        ser = getattr(self.device, "ser", None)
        if ser is not None and hasattr(ser, "set_tee"):
            ser.set_tee(rx=None, tx=None)

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
        logger.info("Virtual serial stopped")

    def is_enabled(self):
        return self._enabled

    def status(self):
        """Return a JSON-serializable status dict."""
        return {
            "enabled": self._enabled,
            "slave": self._slave_name,
            "symlink": self._symlink_path,
        }

    # ------------------------------------------------------------------
    # Data plane (worker thread only)
    # ------------------------------------------------------------------
    def forward_rx(self, data):
        """Forward device->host bytes to the PTY master (full passthrough).

        Called both from the worker RX path and from the ThreadCheckedSerial
        tee during protocol I/O, so external tools see the complete stream.
        """
        if not self._enabled or self._master_fd is None or not data:
            return
        try:
            os.write(self._master_fd, data)
        except BlockingIOError:
            pass  # External reader not draining; drop to avoid blocking worker
        except OSError as e:
            logger.debug(f"forward_rx write error: {e}")

    def poll_tx(self):
        """Read external (host->device) input from the PTY master.

        Non-blocking. Returns bytes to write to the physical port, or None.
        """
        if not self._enabled or self._master_fd is None:
            return None
        try:
            chunk = os.read(self._master_fd, 4096)
        except (BlockingIOError, InterruptedError):
            return None
        except OSError:
            return None
        return chunk or None
