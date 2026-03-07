#!/usr/bin/env python3
"""Tests for core/watch_evaluator.py"""

import os
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.watch_evaluator import WatchEvaluator  # noqa: E402


class TestWatchEvaluator(unittest.TestCase):
    """Test WatchEvaluator core logic."""

    def setUp(self):
        self.gdb = Mock()
        self.evaluator = WatchEvaluator(self.gdb)

    def test_empty_expression(self):
        result = self.evaluator.evaluate("")
        self.assertIn("Empty", result["error"])

    def test_expression_too_long(self):
        result = self.evaluator.evaluate("x" * 300)
        self.assertIn("too long", result["error"])

    def test_blacklisted_command(self):
        result = self.evaluator.evaluate("set var x = 1")
        self.assertIn("Forbidden", result["error"])

    def test_blacklisted_call(self):
        result = self.evaluator.evaluate("call foo()")
        self.assertIn("Forbidden", result["error"])

    def test_simple_symbol(self):
        self.gdb.execute.side_effect = lambda cmd, **kw: {
            "whatis g_counter": "type = uint32_t",
            "print sizeof(g_counter)": "$1 = 4",
            "info address g_counter": 'Symbol "g_counter" is at address 0x20001000.',
        }.get(cmd)
        self.gdb._parse_address_from_info.return_value = 0x20001000

        result = self.evaluator.evaluate("g_counter")
        self.assertIsNone(result["error"])
        self.assertEqual(result["addr"], 0x20001000)
        self.assertEqual(result["size"], 4)
        self.assertEqual(result["type_name"], "uint32_t")
        self.assertFalse(result["is_pointer"])
        self.assertFalse(result["is_aggregate"])

    def test_cast_address(self):
        self.gdb.execute.side_effect = lambda cmd, **kw: {
            "whatis *(uint32_t *)0x40021000": "type = uint32_t",
            "print sizeof(*(uint32_t *)0x40021000)": "$1 = 4",
        }.get(cmd)

        result = self.evaluator.evaluate("*(uint32_t *)0x40021000")
        self.assertIsNone(result["error"])
        self.assertEqual(result["addr"], 0x40021000)
        self.assertEqual(result["size"], 4)
        self.assertFalse(result["is_pointer"])

    def test_struct_cast(self):
        self.gdb.execute.side_effect = lambda cmd, **kw: {
            "whatis *(struct uart_config *)0x20001000": "type = struct uart_config",
            "print sizeof(*(struct uart_config *)0x20001000)": "$1 = 24",
            "ptype /o struct uart_config": (
                "/* offset    |  size */\n"
                "/*    0      |     4 */    uint32_t baud;\n"
                "/*    4      |     1 */    uint8_t parity;\n"
            ),
        }.get(cmd)
        self.gdb._parse_ptype_output.return_value = [
            {"name": "baud", "offset": 0, "size": 4, "type_name": "uint32_t"},
            {"name": "parity", "offset": 4, "size": 1, "type_name": "uint8_t"},
        ]

        result = self.evaluator.evaluate("*(struct uart_config *)0x20001000")
        self.assertIsNone(result["error"])
        self.assertEqual(result["addr"], 0x20001000)
        self.assertTrue(result["is_aggregate"])
        self.assertIsNotNone(result["struct_layout"])
        self.assertEqual(len(result["struct_layout"]), 2)

    def test_pointer_type(self):
        self.gdb.execute.side_effect = lambda cmd, **kw: {
            "whatis g_ptr": "type = uint8_t *",
            "print sizeof(g_ptr)": "$1 = 4",
            "info address g_ptr": 'Symbol "g_ptr" is at address 0x20002000.',
        }.get(cmd)
        self.gdb._parse_address_from_info.return_value = 0x20002000

        result = self.evaluator.evaluate("g_ptr")
        self.assertIsNone(result["error"])
        self.assertTrue(result["is_pointer"])
        self.assertEqual(result["type_name"], "uint8_t *")

    def test_member_access(self):
        self.gdb.execute.side_effect = lambda cmd, **kw: {
            "whatis g_config.baud": "type = uint32_t",
            "print sizeof(g_config.baud)": "$1 = 4",
            "print &(g_config.baud)": "$2 = (uint32_t *) 0x20001234",
        }.get(cmd)

        result = self.evaluator.evaluate("g_config.baud")
        self.assertIsNone(result["error"])
        self.assertEqual(result["addr"], 0x20001234)
        self.assertEqual(result["size"], 4)

    def test_array_slice(self):
        self.gdb.execute.side_effect = lambda cmd, **kw: {
            "whatis ((float *)0x20002000)": "type = float *",
            "print sizeof(float)": "$1 = 4",
        }.get(cmd)

        result = self.evaluator.evaluate("((float *)0x20002000)[0:5]")
        self.assertIsNone(result["error"])
        self.assertEqual(result["addr"], 0x20002000)
        self.assertEqual(result["size"], 20)  # 5 * 4
        self.assertTrue(result["is_aggregate"])
        self.assertEqual(len(result["struct_layout"]), 5)
        self.assertEqual(result["struct_layout"][0]["name"], "[0]")
        self.assertEqual(result["struct_layout"][4]["name"], "[4]")

    def test_array_slice_with_offset(self):
        self.gdb.execute.side_effect = lambda cmd, **kw: {
            "whatis ((int *)0x20000000)": "type = int *",
            "print sizeof(int)": "$1 = 4",
        }.get(cmd)

        result = self.evaluator.evaluate("((int *)0x20000000)[3:2]")
        self.assertIsNone(result["error"])
        self.assertEqual(result["addr"], 0x20000000 + 3 * 4)
        self.assertEqual(result["size"], 8)
        self.assertEqual(result["struct_layout"][0]["name"], "[3]")
        self.assertEqual(result["struct_layout"][1]["name"], "[4]")

    def test_array_slice_count_too_large(self):
        result = self.evaluator.evaluate("((int *)0x20000000)[0:2000]")
        self.assertIn("limit", result["error"])

    def test_array_slice_non_pointer(self):
        self.gdb.execute.side_effect = lambda cmd, **kw: {
            "whatis g_val": "type = int",
        }.get(cmd)

        result = self.evaluator.evaluate("g_val[0:5]")
        self.assertIn("not a pointer", result["error"])

    def test_whatis_failure(self):
        self.gdb.execute.return_value = None
        result = self.evaluator.evaluate("nonexistent_var")
        self.assertIn("Cannot resolve type", result["error"])

    def test_address_resolution_failure(self):
        self.gdb.execute.side_effect = lambda cmd, **kw: {
            "whatis bad_sym": "type = int",
            "print sizeof(bad_sym)": "$1 = 4",
            "info address bad_sym": None,
            "print &(bad_sym)": None,
        }.get(cmd)
        self.gdb._parse_address_from_info.return_value = None

        result = self.evaluator.evaluate("bad_sym")
        self.assertIn("Cannot resolve address", result["error"])


class TestWatchDeref(unittest.TestCase):
    """Test WatchEvaluator.get_deref_info."""

    def setUp(self):
        self.gdb = Mock()
        self.evaluator = WatchEvaluator(self.gdb)

    def test_deref_simple_pointer(self):
        self.gdb.execute.side_effect = lambda cmd, **kw: {
            "print sizeof(uint8_t)": "$1 = 1",
        }.get(cmd)

        result = self.evaluator.get_deref_info("uint8_t *")
        self.assertIsNone(result["error"])
        self.assertEqual(result["target_type"], "uint8_t")
        self.assertEqual(result["target_size"], 1)
        self.assertFalse(result["is_aggregate"])

    def test_deref_struct_pointer(self):
        self.gdb.execute.side_effect = lambda cmd, **kw: {
            "print sizeof(struct node)": "$1 = 12",
            "ptype /o struct node": "...",
        }.get(cmd)
        self.gdb._parse_ptype_output.return_value = [
            {"name": "val", "offset": 0, "size": 4, "type_name": "int"},
        ]

        result = self.evaluator.get_deref_info("struct node *")
        self.assertIsNone(result["error"])
        self.assertEqual(result["target_type"], "struct node")
        self.assertTrue(result["is_aggregate"])
        self.assertIsNotNone(result["struct_layout"])

    def test_deref_non_pointer(self):
        result = self.evaluator.get_deref_info("int")
        self.assertIn("Not a pointer", result["error"])

    def test_deref_empty(self):
        result = self.evaluator.get_deref_info("")
        self.assertIn("Not a pointer", result["error"])


class TestWatchEnumDisplay(unittest.TestCase):
    """Test WatchEvaluator.resolve_enum_display."""

    def setUp(self):
        self.gdb = Mock()
        self.evaluator = WatchEvaluator(self.gdb)

    def test_resolve_enum(self):
        self.gdb.execute.return_value = (
            "type = enum state_t {IDLE = 0, RUNNING = 1, ERROR = 2}"
        )
        result = self.evaluator.resolve_enum_display("enum state_t", 1)
        self.assertEqual(result, "RUNNING")

    def test_resolve_enum_not_found(self):
        self.gdb.execute.return_value = (
            "type = enum state_t {IDLE = 0, RUNNING = 1, ERROR = 2}"
        )
        result = self.evaluator.resolve_enum_display("enum state_t", 99)
        self.assertIsNone(result)

    def test_resolve_enum_gdb_failure(self):
        self.gdb.execute.return_value = None
        result = self.evaluator.resolve_enum_display("enum state_t", 0)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
