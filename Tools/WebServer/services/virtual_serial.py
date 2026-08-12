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
import tempfile

logger = logging.getLogger(__name__)

# Directory for the stable virtual-serial symlinks. PTY passthrough is
# POSIX-only, but resolve the temp dir portably rather than hardcoding /tmp.
_SYMLINK_DIR = tempfile.gettempdir()

# Legacy hard-coded default from earlier versions. Existing config.json files
# may still carry this value; treat it as "auto" so they derive per-device
# names instead of colliding on a single fixed path.
_LEGACY_DEFAULT_SYMLINK = "/tmp/fpb-tty0"


def default_symlink_for_port(port):
    """Derive a stable, per-device symlink path from the physical port.

    Examples:
        /dev/ttyACM0      -> /tmp/fpb-ttyACM0
        /dev/ttyUSB1      -> /tmp/fpb-ttyUSB1
        /dev/serial/by-id/usb-...-if00 -> /tmp/fpb-usb-...-if00
        None / ""         -> /tmp/fpb-tty0   (fallback)

    Using the physical device basename keeps the alias recognizable and
    unique across multiple devices on one host, so several WebServer
    instances don't fight over a single hard-coded path.
    """
    if not port:
        return f"{_SYMLINK_DIR}/fpb-tty0"
    base = os.path.basename(str(port).rstrip("/")) or "tty0"
    # Sanitize to a safe filename (device names are usually clean already).
    safe = "".join(c if (c.isalnum() or c in "-._") else "_" for c in base)
    return f"{_SYMLINK_DIR}/fpb-{safe}"


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
    def start(self, symlink=None, mute_policy=None):
        """Create the PTY and a stable symlink.

        ``symlink`` selects the stable device-file alias:
          * a non-empty path  -> used as-is (user override);
          * ``None`` / "auto" / the legacy "/tmp/fpb-tty0" default
            -> derived from the physical port name, e.g. ``/dev/ttyACM0``
            -> ``/tmp/fpb-ttyACM0`` (multi-device friendly, no collisions
            between different physical ports);
          * "" (empty string) -> no symlink (only /dev/pts/N is exposed).

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

        # Resolve the stable symlink path. Empty string disables the symlink;
        # None/"auto" derives it from the physical port name so multiple
        # devices on one host each get a distinct, recognizable alias.
        # The legacy hard-coded default "/tmp/fpb-tty0" is also treated as
        # "auto" so pre-existing config.json values still derive per-device
        # names without a manual edit.
        if symlink in (None, "auto", _LEGACY_DEFAULT_SYMLINK):
            port = getattr(self.device, "port", None)
            symlink = default_symlink_for_port(port)

        self._symlink_path = None
        if symlink:
            chosen = self._reserve_symlink(symlink)
            if chosen:
                self._symlink_path = chosen

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

    def _reserve_symlink(self, base_path):
        """Point ``base_path`` at our slave, avoiding live-instance clashes.

        Behavior:
          * path free, or a dangling link (crashed instance) -> claim it;
          * path links to a *live* pts (another running instance) -> try
            ``base_path-1``, ``-2`` ... up to a small bound;
          * on any OS error -> log and give up (PTY still usable by /dev/pts).

        Returns the path actually created, or None on failure.
        """

        def _is_dangling_or_ours(p):
            # True if p is absent, or a symlink whose target no longer exists
            # (stale). A link to an existing pts is considered "in use".
            if not os.path.islink(p) and not os.path.exists(p):
                return True
            if os.path.islink(p):
                target = os.path.realpath(p)
                return not os.path.exists(target)
            return False

        candidates = [base_path] + [f"{base_path}-{i}" for i in range(1, 10)]
        for path in candidates:
            try:
                if _is_dangling_or_ours(path):
                    if os.path.islink(path) or os.path.exists(path):
                        os.unlink(path)
                    os.symlink(self._slave_name, path)
                    return path
            except OSError as e:
                logger.warning(f"Could not create symlink {path}: {e}")
                continue
        logger.warning(
            f"All virtual-serial symlink candidates for {base_path} are in use; "
            f"external tools can still open {self._slave_name} directly"
        )
        return None

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
