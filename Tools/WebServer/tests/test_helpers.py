#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper utilities tests
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helpers import build_slot_response
from core.state import DeviceState, AppState


class TestBuildSlotResponse(unittest.TestCase):
    """build_slot_response function tests"""

    def test_no_device_info(self):
        """Test with no device info"""
        device = DeviceState()
        device.device_info = None
        app_state = AppState()

        result = build_slot_response(device, app_state, Mock())

        self.assertIsNone(result)

    def test_empty_slots(self):
        """Test with empty slots"""
        device = DeviceState()
        device.device_info = {"slots": [], "base": 0x20000000, "size": 1024}
        app_state = AppState()

        mock_fpb = Mock()
        mock_fpb.get_symbols.return_value = {}

        result = build_slot_response(device, app_state, lambda: mock_fpb)

        self.assertIsNotNone(result)
        self.assertEqual(len(result["slots"]), 6)
        for slot in result["slots"]:
            self.assertFalse(slot["occupied"])

    def test_with_occupied_slots(self):
        """Test with occupied slots"""
        device = DeviceState()
        device.device_info = {
            "slots": [
                {
                    "id": 0,
                    "occupied": True,
                    "orig_addr": 0x08000100,
                    "target_addr": 0x20001000,
                    "code_size": 64,
                }
            ],
            "base": 0x20000000,
            "size": 1024,
        }
        app_state = AppState()
        app_state.symbols = {"main": 0x08000100}
        app_state.symbols_loaded = True

        mock_fpb = Mock()

        result = build_slot_response(device, app_state, lambda: mock_fpb)

        self.assertIsNotNone(result)
        self.assertTrue(result["slots"][0]["occupied"])
        self.assertEqual(result["slots"][0]["func"], "main")
        self.assertEqual(result["slots"][0]["code_size"], 64)

    def test_loads_symbols_if_needed(self):
        """Test that symbols are loaded if not already loaded"""
        device = DeviceState()
        device.device_info = {"slots": [], "base": 0x20000000}

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            device.elf_path = f.name

        try:
            app_state = AppState()
            app_state.symbols_loaded = False

            mock_fpb = Mock()
            mock_fpb.get_symbols.return_value = {"test": 0x08000000}

            result = build_slot_response(device, app_state, lambda: mock_fpb)

            self.assertIsNotNone(result)
            mock_fpb.get_symbols.assert_called_once()
            self.assertTrue(app_state.symbols_loaded)
        finally:
            os.unlink(device.elf_path)

    def test_thumb_address_lookup(self):
        """Test symbol lookup with Thumb bit cleared"""
        device = DeviceState()
        device.device_info = {
            "slots": [
                {
                    "id": 0,
                    "occupied": True,
                    "orig_addr": 0x08000101,  # Thumb address (bit 0 set)
                    "target_addr": 0x20001000,
                    "code_size": 32,
                }
            ],
        }
        app_state = AppState()
        # Symbol stored without Thumb bit
        app_state.symbols = {"thumb_func": 0x08000100}
        app_state.symbols_loaded = True

        mock_fpb = Mock()

        result = build_slot_response(device, app_state, lambda: mock_fpb)

        self.assertIsNotNone(result)
        # Should find function by clearing Thumb bit
        self.assertEqual(result["slots"][0]["func"], "thumb_func")

    def test_memory_info(self):
        """Test memory info in response"""
        device = DeviceState()
        device.device_info = {
            "slots": [],
            "used": 1024,
        }
        app_state = AppState()

        mock_fpb = Mock()
        mock_fpb.get_symbols.return_value = {}

        result = build_slot_response(device, app_state, lambda: mock_fpb)

        self.assertIsNotNone(result)
        self.assertEqual(result["memory"]["used"], 1024)


if __name__ == "__main__":
    unittest.main()
