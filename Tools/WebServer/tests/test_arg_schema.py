#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for core.arg_schema: schema-driven argparse generation shared by the
server (main.py) and CLI (fpb_cli.py).
"""

import argparse
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpbinject.core import arg_schema  # noqa: E402
from fpbinject.core.config_schema import ConfigGroup  # noqa: E402


def _parser():
    p = argparse.ArgumentParser()
    arg_schema.add_connection_args(p)
    return p


class TestFlagGeneration(unittest.TestCase):
    """add_connection_args generates the expected flags."""

    def test_serial_port_and_baudrate_present(self):
        args = _parser().parse_args(["--port", "/dev/ttyACM0", "--baudrate", "9600"])
        self.assertEqual(args.port, "/dev/ttyACM0")
        self.assertEqual(args.baudrate, 9600)

    def test_short_options(self):
        """-p and -b short options map to port/baudrate."""
        args = _parser().parse_args(["-p", "/dev/ttyUSB0", "-b", "57600"])
        self.assertEqual(args.port, "/dev/ttyUSB0")
        self.assertEqual(args.baudrate, 57600)

    def test_all_flags_default_none(self):
        """Unset flags default to None (the override sentinel)."""
        args = _parser().parse_args([])
        for item in arg_schema.iter_cli_items():
            self.assertIsNone(
                getattr(args, item.key), f"{item.key} should default to None"
            )

    def test_key_to_flag_name_underscores_to_dashes(self):
        """serial_tx_fragment_size -> --serial-tx-fragment-size."""
        args = _parser().parse_args(["--serial-tx-fragment-size", "64"])
        self.assertEqual(args.serial_tx_fragment_size, 64)

    def test_float_flag_parsed_as_float(self):
        """serial_tx_fragment_delay parses as float."""
        args = _parser().parse_args(["--serial-tx-fragment-delay", "0.01"])
        self.assertEqual(args.serial_tx_fragment_delay, 0.01)
        self.assertIsInstance(args.serial_tx_fragment_delay, float)

    def test_int_flag_parsed_as_int(self):
        args = _parser().parse_args(["--data-bits", "7"])
        self.assertEqual(args.data_bits, 7)
        self.assertIsInstance(args.data_bits, int)


class TestSelectFlags(unittest.TestCase):
    """SELECT items become choice-constrained flags."""

    def test_parity_accepts_valid_choice(self):
        args = _parser().parse_args(["--parity", "even"])
        self.assertEqual(args.parity, "even")

    def test_parity_rejects_invalid_choice(self):
        with self.assertRaises(SystemExit):
            _parser().parse_args(["--parity", "bogus"])

    def test_flow_control_choices(self):
        args = _parser().parse_args(["--flow-control", "rtscts"])
        self.assertEqual(args.flow_control, "rtscts")


class TestBooleanFlags(unittest.TestCase):
    """BOOLEAN items become tri-state --flag / --no-flag."""

    def test_unset_is_none(self):
        args = _parser().parse_args([])
        self.assertIsNone(args.auto_connect)

    def test_flag_sets_true(self):
        args = _parser().parse_args(["--auto-connect"])
        self.assertIs(args.auto_connect, True)

    def test_no_flag_sets_false(self):
        args = _parser().parse_args(["--no-auto-connect"])
        self.assertIs(args.auto_connect, False)


class TestLegacyAliases(unittest.TestCase):
    """Renamed transfer flags keep their old names as aliases."""

    def test_tx_chunk_size_alias(self):
        args = _parser().parse_args(["--tx-chunk-size", "32"])
        self.assertEqual(args.serial_tx_fragment_size, 32)

    def test_tx_chunk_delay_alias(self):
        args = _parser().parse_args(["--tx-chunk-delay", "0.02"])
        self.assertEqual(args.serial_tx_fragment_delay, 0.02)

    def test_max_retries_alias(self):
        args = _parser().parse_args(["--max-retries", "5"])
        self.assertEqual(args.transfer_max_retries, 5)

    def test_new_name_and_alias_are_same_dest(self):
        args = _parser().parse_args(["--transfer-max-retries", "7"])
        self.assertEqual(args.transfer_max_retries, 7)


class TestConnectionOverrides(unittest.TestCase):
    """connection_overrides only reports flags the user set."""

    def test_empty_when_nothing_set(self):
        args = _parser().parse_args([])
        self.assertEqual(arg_schema.connection_overrides(args), {})

    def test_only_set_flags_returned(self):
        args = _parser().parse_args(["--port", "/dev/ttyACM0", "--baudrate", "9600"])
        overrides = arg_schema.connection_overrides(args)
        self.assertEqual(overrides, {"port": "/dev/ttyACM0", "baudrate": 9600})

    def test_false_boolean_is_reported(self):
        """--no-auto-connect (False) must still count as an explicit override."""
        args = _parser().parse_args(["--no-auto-connect"])
        overrides = arg_schema.connection_overrides(args)
        self.assertIn("auto_connect", overrides)
        self.assertIs(overrides["auto_connect"], False)


class TestApplyOverrides(unittest.TestCase):
    """apply_overrides writes onto a device-like object."""

    def test_setattr_applied(self):
        class Dev:
            port = None
            baudrate = 115200

        dev = Dev()
        arg_schema.apply_overrides(dev, {"port": "/dev/ttyACM0", "baudrate": 9600})
        self.assertEqual(dev.port, "/dev/ttyACM0")
        self.assertEqual(dev.baudrate, 9600)


class TestFillMissingDefaults(unittest.TestCase):
    """fill_missing_defaults turns unset flags into schema defaults (CLI use)."""

    def test_unset_filled_with_schema_default(self):
        args = _parser().parse_args([])
        arg_schema.fill_missing_defaults(args)
        self.assertEqual(args.baudrate, 115200)
        self.assertEqual(args.serial_tx_fragment_size, 0)
        self.assertEqual(args.transfer_max_retries, 10)
        self.assertEqual(args.parity, "none")

    def test_set_values_preserved(self):
        args = _parser().parse_args(["--baudrate", "9600"])
        arg_schema.fill_missing_defaults(args)
        self.assertEqual(args.baudrate, 9600)


class TestGroupFiltering(unittest.TestCase):
    """add_connection_args honors the groups filter."""

    def test_connection_only_excludes_transfer(self):
        p = argparse.ArgumentParser()
        arg_schema.add_connection_args(p, groups=(ConfigGroup.CONNECTION,))
        args = p.parse_args(["--port", "/dev/ttyACM0"])
        self.assertEqual(args.port, "/dev/ttyACM0")
        # Transfer flags should not exist in this parser.
        self.assertFalse(hasattr(args, "serial_tx_fragment_size"))


if __name__ == "__main__":
    unittest.main()
