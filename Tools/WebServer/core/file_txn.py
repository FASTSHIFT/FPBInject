#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
File transaction guard for FPBInject Web Server.

The device exposes a single global file handle: any fopen silently closes a
previously open file, and fseek/fread/fwrite mutate shared state. A file
transfer is a multi-command sequence (fopen -> fwrite/fread x N -> fcrc ->
fclose), so a second file operation started mid-transfer can corrupt the one
in flight.

This module provides a process-wide, per-device transaction guard. Stateful
file operations acquire it non-blocking and fail fast (raising TransferBusy)
if another transaction already holds it, instead of interleaving on the wire
or queueing behind a long transfer.
"""

import threading
import time
import uuid
from contextlib import contextmanager
from typing import Optional


class TransferBusy(Exception):
    """Raised when a file operation cannot start because one is in progress."""

    def __init__(self, active: Optional[dict]):
        self.active = active or {}
        op = self.active.get("op", "operation")
        path = self.active.get("path", "")
        msg = f"Device busy: {op}"
        if path:
            msg += f" {path}"
        msg += " in progress"
        super().__init__(msg)


@contextmanager
def file_transaction(device, op: str, path: str = ""):
    """Acquire the device's file transaction guard for the duration of a block.

    Args:
        device: DeviceState carrying file_txn_lock / file_txn_active.
        op: Short operation name (e.g. "upload", "download", "delete").
        path: Target path, for diagnostics and the busy message.

    Yields:
        A cancel_event (threading.Event) scoped to this transaction. Long
        transfers should poll it to support cancellation without a global
        flag shared across concurrent transfers.

    Raises:
        TransferBusy: if another transaction currently holds the guard.
    """
    lock = device.file_txn_lock
    if not lock.acquire(blocking=False):
        raise TransferBusy(device.file_txn_active)

    cancel_event = threading.Event()
    device.file_txn_active = {
        "op": op,
        "path": path,
        "since": time.time(),
        "id": uuid.uuid4().hex,
        "cancel_event": cancel_event,
    }
    try:
        yield cancel_event
    finally:
        device.file_txn_active = None
        lock.release()


def begin_transaction(device, op: str, path: str = ""):
    """Acquire the guard for a transaction that outlives the current call.

    Used by streaming transfers (upload/download): the HTTP handler acquires
    the guard to fail fast, then hands ownership to a background thread which
    must call :func:`end_transaction` in a finally block.

    Args:
        device: DeviceState carrying file_txn_lock / file_txn_active.
        op: Short operation name.
        path: Target path, for diagnostics and the busy message.

    Returns:
        A cancel_event (threading.Event) scoped to this transaction.

    Raises:
        TransferBusy: if another transaction currently holds the guard.
    """
    lock = device.file_txn_lock
    if not lock.acquire(blocking=False):
        raise TransferBusy(device.file_txn_active)

    cancel_event = threading.Event()
    device.file_txn_active = {
        "op": op,
        "path": path,
        "since": time.time(),
        "id": uuid.uuid4().hex,
        "cancel_event": cancel_event,
    }
    return cancel_event


def end_transaction(device):
    """Release a guard acquired via :func:`begin_transaction`.

    Safe to call unconditionally in a finally block; releases only if the
    lock is currently held.
    """
    device.file_txn_active = None
    lock = device.file_txn_lock
    if lock.locked():
        try:
            lock.release()
        except RuntimeError:
            # Not held by this thread; ignore to keep cleanup idempotent.
            pass


def get_active_transaction(device) -> Optional[dict]:
    """Return a copy of the active transaction descriptor, or None."""
    active = device.file_txn_active
    if not active:
        return None
    return {k: v for k, v in active.items() if k != "cancel_event"}


def request_cancel(device) -> bool:
    """Signal cancellation to the in-flight transaction, if any.

    Returns True if a transaction was active and got signalled.
    """
    active = device.file_txn_active
    if not active:
        return False
    ev = active.get("cancel_event")
    if ev is not None:
        ev.set()
        return True
    return False
