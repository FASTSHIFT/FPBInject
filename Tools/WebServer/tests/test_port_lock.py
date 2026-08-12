#!/usr/bin/env python3
"""
Test cases for utils/port_lock.py
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from fpbinject.utils.port_lock import (
    PortLock,
    PortLockError,
    _lock_path_for_port,
    _LOCK_DIR,
)


class TestLockPathForPort(unittest.TestCase):
    """Test _lock_path_for_port helper."""

    def test_deterministic(self):
        """Same port always produces the same lock path."""
        p1 = _lock_path_for_port("/dev/ttyACM0")
        p2 = _lock_path_for_port("/dev/ttyACM0")
        self.assertEqual(p1, p2)

    def test_different_ports_different_paths(self):
        """Different ports produce different lock paths."""
        p1 = _lock_path_for_port("/dev/ttyACM0")
        p2 = _lock_path_for_port("/dev/ttyACM1")
        self.assertNotEqual(p1, p2)

    def test_path_in_lock_dir(self):
        """Lock path is under the expected directory."""
        p = _lock_path_for_port("COM3")
        self.assertTrue(p.startswith(_LOCK_DIR))

    def test_path_has_prefix(self):
        """Lock file name starts with fpbinject-."""
        p = _lock_path_for_port("/dev/ttyUSB0")
        basename = os.path.basename(p)
        self.assertTrue(basename.startswith("fpbinject-"))
        self.assertTrue(basename.endswith(".lock"))


class TestPortLockAcquireRelease(unittest.TestCase):
    """Test PortLock acquire/release lifecycle."""

    def test_acquire_and_release(self):
        """Basic acquire then release."""
        lock = PortLock("/dev/test-port-1")
        self.assertTrue(lock.acquire())
        lock.release()

    def test_double_release_safe(self):
        """Releasing twice should not raise."""
        lock = PortLock("/dev/test-port-2")
        lock.acquire()
        lock.release()
        lock.release()  # Should not raise

    def test_acquire_blocks_second(self):
        """Second acquire on same port should fail."""
        lock1 = PortLock("/dev/test-port-3")
        lock2 = PortLock("/dev/test-port-3")
        self.assertTrue(lock1.acquire())
        self.assertFalse(lock2.acquire())
        lock1.release()

    def test_acquire_after_release(self):
        """After release, another lock can acquire."""
        lock1 = PortLock("/dev/test-port-4")
        lock2 = PortLock("/dev/test-port-4")
        self.assertTrue(lock1.acquire())
        lock1.release()
        self.assertTrue(lock2.acquire())
        lock2.release()

    def test_different_ports_independent(self):
        """Locks on different ports don't interfere."""
        lock1 = PortLock("/dev/test-port-5a")
        lock2 = PortLock("/dev/test-port-5b")
        self.assertTrue(lock1.acquire())
        self.assertTrue(lock2.acquire())
        lock1.release()
        lock2.release()

    def test_port_property(self):
        """Port property returns the port string."""
        lock = PortLock("/dev/ttyACM0")
        self.assertEqual(lock.port, "/dev/ttyACM0")


class TestPortLockOwner(unittest.TestCase):
    """Test owner PID tracking."""

    def test_owner_pid_written(self):
        """Lock file contains the owner PID."""
        lock = PortLock("/dev/test-port-owner")
        lock.acquire()
        owner = lock.get_owner_pid()
        self.assertEqual(owner, str(os.getpid()))
        lock.release()

    def test_owner_pid_no_file(self):
        """get_owner_pid returns 'unknown' when no lock file."""
        lock = PortLock("/dev/nonexistent-port-xyz")
        self.assertEqual(lock.get_owner_pid(), "unknown")


class TestPortLockIsLocked(unittest.TestCase):
    """Test is_locked() probe."""

    def test_not_locked(self):
        """is_locked returns False when no lock held."""
        lock = PortLock("/dev/test-port-probe-1")
        self.assertFalse(lock.is_locked())

    def test_locked_by_self(self):
        """is_locked returns True when lock is held."""
        lock1 = PortLock("/dev/test-port-probe-2")
        lock1.acquire()
        lock2 = PortLock("/dev/test-port-probe-2")
        self.assertTrue(lock2.is_locked())
        lock1.release()


class TestPortLockContextManager(unittest.TestCase):
    """Test context manager protocol."""

    def test_context_manager_success(self):
        """Context manager acquires and releases."""
        with PortLock("/dev/test-port-ctx-1") as lock:
            self.assertIsNotNone(lock)
        # After exit, should be releasable
        lock2 = PortLock("/dev/test-port-ctx-1")
        self.assertTrue(lock2.acquire())
        lock2.release()

    def test_context_manager_conflict(self):
        """Context manager raises PortLockError on conflict."""
        lock1 = PortLock("/dev/test-port-ctx-2")
        lock1.acquire()
        with self.assertRaises(PortLockError) as ctx:
            with PortLock("/dev/test-port-ctx-2"):
                pass  # Should not reach here
        self.assertIn("locked", str(ctx.exception).lower())
        lock1.release()


class TestPortLockError(unittest.TestCase):
    """Test PortLockError exception."""

    def test_is_exception(self):
        self.assertTrue(issubclass(PortLockError, Exception))

    def test_message(self):
        err = PortLockError("test message")
        self.assertEqual(str(err), "test message")


class TestPortLockEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_acquire_creates_lock_dir(self):
        """acquire() creates the lock directory if needed."""
        lock = PortLock("/dev/test-port-mkdir")
        self.assertTrue(lock.acquire())
        self.assertTrue(os.path.isdir(_LOCK_DIR))
        lock.release()

    @patch(
        "fpbinject.utils.port_lock.os.makedirs",
        side_effect=OSError("permission denied"),
    )
    def test_acquire_fails_open_on_dir_error(self, mock_makedirs):
        """If lock dir creation fails, acquire fails open (returns True)."""
        lock = PortLock("/dev/test-port-fail-open")
        # The open() call will also fail since dir doesn't exist,
        # but the function should handle it gracefully
        result = lock.acquire()
        # Should fail open (return True) to not block operations
        self.assertTrue(result)

    def test_del_releases(self):
        """__del__ releases the lock."""
        lock = PortLock("/dev/test-port-del")
        lock.acquire()
        del lock
        # After del, another lock should be acquirable
        lock2 = PortLock("/dev/test-port-del")
        self.assertTrue(lock2.acquire())
        lock2.release()


if __name__ == "__main__":
    unittest.main()
