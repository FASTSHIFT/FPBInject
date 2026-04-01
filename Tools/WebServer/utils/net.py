#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Network utility functions for FPBInject.
"""

import logging
import os
import signal
import socket
import subprocess
import time

logger = logging.getLogger(__name__)


def is_port_available(port, host="127.0.0.1"):
    """Check if a TCP port is available by attempting to connect.

    Returns True if the port is free, False if something is listening.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex(("127.0.0.1", port))
        return result != 0
    except Exception:
        return True
    finally:
        sock.close()


def get_port_owner(port):
    """Get info about the process occupying a TCP port.

    Returns dict with pid, name, cmdline, or None if not found.
    Uses /proc on Linux, lsof as fallback.
    """
    # Try /proc/net/tcp (no external tools needed)
    try:
        hex_port = f"{port:04X}"
        with open("/proc/net/tcp", "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 10:
                    continue
                local = parts[1]
                if local.endswith(f":{hex_port}") and parts[3] == "0A":
                    inode = parts[9]
                    for entry in os.listdir("/proc"):
                        if not entry.isdigit():
                            continue
                        fd_dir = f"/proc/{entry}/fd"
                        try:
                            for fd in os.listdir(fd_dir):
                                link = os.readlink(f"{fd_dir}/{fd}")
                                if f"socket:[{inode}]" in link:
                                    pid = int(entry)
                                    cmdline = (
                                        open(f"/proc/{pid}/cmdline", "r")
                                        .read()
                                        .replace("\x00", " ")
                                        .strip()
                                    )
                                    comm = open(f"/proc/{pid}/comm", "r").read().strip()
                                    return {
                                        "pid": pid,
                                        "name": comm,
                                        "cmdline": cmdline,
                                    }
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
    except Exception:
        pass

    # Fallback: lsof
    try:
        out = subprocess.check_output(
            ["lsof", "-ti", f":{port}"], stderr=subprocess.DEVNULL, timeout=3
        ).decode()
        for line in out.strip().split("\n"):
            pid = int(line.strip())
            try:
                cmdline = (
                    open(f"/proc/{pid}/cmdline", "r")
                    .read()
                    .replace("\x00", " ")
                    .strip()
                )
                comm = open(f"/proc/{pid}/comm", "r").read().strip()
                return {"pid": pid, "name": comm, "cmdline": cmdline}
            except Exception:
                return {"pid": pid, "name": "unknown", "cmdline": "unknown"}
    except Exception:
        pass

    return None


def kill_port_owner(port, timeout=1.0):
    """Kill the process occupying a TCP port.

    Args:
        port: TCP port number
        timeout: Max seconds to wait for process to exit

    Returns:
        True if the port was freed, False otherwise.
    """
    owner = get_port_owner(port)
    if not owner:
        return False

    pid = owner["pid"]
    if pid == os.getpid():
        return False

    logger.warning(f"Port {port} occupied by {owner['name']} (PID {pid}), killing...")
    try:
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                logger.info(f"Killed stale process PID {pid} on port {port}")
                return True
            time.sleep(0.1)
        logger.error(f"PID {pid} did not exit within {timeout}s")
        return False
    except OSError as e:
        logger.error(f"Failed to kill PID {pid}: {e}")
        return False


def check_and_free_port(port, host="127.0.0.1"):
    """Check if a TCP port is available; if not, kill the occupying process.

    Returns True if the port is available (or was freed), False if still occupied.
    """
    if is_port_available(port, host):
        return True
    return kill_port_owner(port)
