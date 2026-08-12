#!/usr/bin/env python3
"""Tests for the connection-plan data model.

These tests pin the contract: ConnectionPlan is frozen, the enums name
exactly the modes/policies the rest of the code is allowed to use, and
the default field values match what the resolver assumes when it omits
optional arguments.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fpbinject.cli.connection_plan import (  # noqa: E402
    CommandPolicy,
    ConnectionMode,
    ConnectionPlan,
)


class TestCommandPolicy(unittest.TestCase):
    def test_exactly_three_policies(self):
        # Adding a 4th policy without updating the resolver/dispatcher is a
        # bug; pin the count to force review.
        self.assertEqual(
            {p.name for p in CommandPolicy},
            {"OFFLINE", "DEVICE", "SERVER_ADMIN"},
        )


class TestConnectionMode(unittest.TestCase):
    def test_exactly_four_modes(self):
        self.assertEqual(
            {m.name for m in ConnectionMode},
            {"OFFLINE", "LOCAL_PROXY", "REMOTE_PROXY", "DIRECT"},
        )


class TestConnectionPlan(unittest.TestCase):
    def test_frozen(self):
        plan = ConnectionPlan(mode=ConnectionMode.OFFLINE)
        with self.assertRaises(Exception):
            plan.mode = ConnectionMode.DIRECT  # type: ignore[misc]

    def test_defaults(self):
        plan = ConnectionPlan(mode=ConnectionMode.OFFLINE)
        self.assertIsNone(plan.server_url)
        self.assertIsNone(plan.token)
        self.assertIsNone(plan.serial_port)
        self.assertEqual(plan.baudrate, 115200)
        self.assertFalse(plan.allow_launch)
        self.assertFalse(plan.allow_direct_fallback)
        self.assertEqual(plan.source, "")

    def test_full_construction(self):
        plan = ConnectionPlan(
            mode=ConnectionMode.LOCAL_PROXY,
            server_url="http://127.0.0.1:5500",
            token="abc",
            serial_port="/dev/ttyACM0",
            baudrate=921600,
            allow_launch=True,
            allow_direct_fallback=True,
            source="localhost-default",
        )
        self.assertEqual(plan.mode, ConnectionMode.LOCAL_PROXY)
        self.assertEqual(plan.server_url, "http://127.0.0.1:5500")
        self.assertEqual(plan.token, "abc")
        self.assertEqual(plan.serial_port, "/dev/ttyACM0")
        self.assertEqual(plan.baudrate, 921600)
        self.assertTrue(plan.allow_launch)
        self.assertTrue(plan.allow_direct_fallback)
        self.assertEqual(plan.source, "localhost-default")


if __name__ == "__main__":
    unittest.main()
