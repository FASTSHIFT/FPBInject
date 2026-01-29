#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Tests for CRC utilities.
"""

import sys
import os
import unittest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.crc import crc16


class TestCRC16(unittest.TestCase):
    """Tests for CRC-16-CCITT calculation."""

    def test_empty_data(self):
        """Test CRC of empty data."""
        result = crc16(b"")
        self.assertEqual(result, 0xFFFF)

    def test_known_values(self):
        """Test CRC against known values."""
        # Test with simple data
        result = crc16(b"123456789")
        # CRC-16-CCITT of "123456789" with init 0xFFFF
        self.assertEqual(result, 0x29B1)

    def test_single_byte(self):
        """Test CRC of single byte."""
        result = crc16(b"\x00")
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 0xFFFF)

    def test_consistency(self):
        """Test that same input produces same output."""
        data = b"test data for crc"
        result1 = crc16(data)
        result2 = crc16(data)
        self.assertEqual(result1, result2)

    def test_different_data_different_crc(self):
        """Test that different data produces different CRC."""
        result1 = crc16(b"data1")
        result2 = crc16(b"data2")
        self.assertNotEqual(result1, result2)

    def test_binary_data(self):
        """Test CRC with binary data."""
        data = bytes(range(256))
        result = crc16(data)
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 0xFFFF)


if __name__ == "__main__":
    unittest.main()
