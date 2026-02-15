#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Unit tests for log file recorder service.
"""

import os
import tempfile
import unittest

from services.log_recorder import LogFileRecorder


class TestLogFileRecorder(unittest.TestCase):
    """Test cases for LogFileRecorder."""

    def setUp(self):
        """Set up test fixtures."""
        self.recorder = LogFileRecorder()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        if self.recorder.enabled:
            self.recorder.stop()

        # Clean up temp files
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_start_recording(self):
        """Test starting log recording."""
        log_path = os.path.join(self.temp_dir, "test.log")

        success, error = self.recorder.start(log_path)

        self.assertTrue(success)
        self.assertEqual(error, "")
        self.assertTrue(self.recorder.enabled)
        self.assertEqual(self.recorder.path, log_path)
        self.assertTrue(os.path.exists(log_path))

    def test_start_recording_creates_directory(self):
        """Test that start creates parent directory if not exists."""
        log_path = os.path.join(self.temp_dir, "subdir", "test.log")

        success, error = self.recorder.start(log_path)

        self.assertTrue(success)
        self.assertTrue(os.path.exists(log_path))

    def test_start_recording_already_started(self):
        """Test starting recording when already started."""
        log_path = os.path.join(self.temp_dir, "test.log")

        self.recorder.start(log_path)
        success, error = self.recorder.start(log_path)

        self.assertFalse(success)
        self.assertIn("Already recording", error)

    def test_stop_recording(self):
        """Test stopping log recording."""
        log_path = os.path.join(self.temp_dir, "test.log")

        self.recorder.start(log_path)
        success, error = self.recorder.stop()

        self.assertTrue(success)
        self.assertEqual(error, "")
        self.assertFalse(self.recorder.enabled)
        self.assertEqual(self.recorder.path, "")

    def test_stop_recording_not_started(self):
        """Test stopping recording when not started."""
        success, error = self.recorder.stop()

        self.assertFalse(success)
        self.assertIn("Not recording", error)

    def test_write_message(self):
        """Test writing messages to log file."""
        log_path = os.path.join(self.temp_dir, "test.log")

        self.recorder.start(log_path)
        self.recorder.write("Test message 1")
        self.recorder.write("Test message 2")
        self.recorder.stop()

        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Test message 1", content)
        self.assertIn("Test message 2", content)

    def test_write_message_not_enabled(self):
        """Test writing message when recording is not enabled."""
        # Should not raise exception
        self.recorder.write("Test message")

    def test_write_message_with_timestamp(self):
        """Test that messages include timestamp."""
        log_path = os.path.join(self.temp_dir, "test.log")

        self.recorder.start(log_path)
        self.recorder.write("Test message")
        self.recorder.stop()

        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for timestamp pattern [YYYY-MM-DD HH:MM:SS.mmm]
        import re

        pattern = r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\]"
        self.assertTrue(re.search(pattern, content))

    def test_concurrent_writes(self):
        """Test concurrent writes from multiple threads."""
        import threading

        log_path = os.path.join(self.temp_dir, "test.log")
        self.recorder.start(log_path)

        def write_messages(thread_id):
            for i in range(10):
                self.recorder.write(f"Thread {thread_id} message {i}")

        threads = []
        for i in range(5):
            t = threading.Thread(target=write_messages, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.recorder.stop()

        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check that all messages are present
        for i in range(5):
            for j in range(10):
                self.assertIn(f"Thread {i} message {j}", content)

    def test_properties(self):
        """Test enabled and path properties."""
        log_path = os.path.join(self.temp_dir, "test.log")

        self.assertFalse(self.recorder.enabled)
        self.assertEqual(self.recorder.path, "")

        self.recorder.start(log_path)

        self.assertTrue(self.recorder.enabled)
        self.assertEqual(self.recorder.path, log_path)

        self.recorder.stop()

        self.assertFalse(self.recorder.enabled)
        self.assertEqual(self.recorder.path, "")

    def test_append_mode(self):
        """Test that recorder appends to existing file."""
        log_path = os.path.join(self.temp_dir, "test.log")

        # First session
        self.recorder.start(log_path)
        self.recorder.write("First session")
        self.recorder.stop()

        # Second session
        recorder2 = LogFileRecorder()
        recorder2.start(log_path)
        recorder2.write("Second session")
        recorder2.stop()

        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("First session", content)
        self.assertIn("Second session", content)

    def test_serial_log_integration(self):
        """Test that serial logs are recorded."""
        log_path = os.path.join(self.temp_dir, "serial.log")

        self.recorder.start(log_path)

        # Simulate serial data
        self.recorder.write("RX: Hello from device")
        self.recorder.write("TX: Command sent")
        self.recorder.write("RX: Response received")

        self.recorder.stop()

        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Hello from device", content)
        self.assertIn("Command sent", content)
        self.assertIn("Response received", content)


if __name__ == "__main__":
    unittest.main()
