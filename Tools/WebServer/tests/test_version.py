#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for version.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from version import (
    VERSION_MAJOR,
    VERSION_MINOR,
    VERSION_PATCH,
    VERSION_STRING,
    __version__,
)


class TestVersion(unittest.TestCase):
    """Tests for version module."""

    def test_version_major_is_int(self):
        """Test VERSION_MAJOR is an integer."""
        self.assertIsInstance(VERSION_MAJOR, int)

    def test_version_minor_is_int(self):
        """Test VERSION_MINOR is an integer."""
        self.assertIsInstance(VERSION_MINOR, int)

    def test_version_patch_is_int(self):
        """Test VERSION_PATCH is an integer."""
        self.assertIsInstance(VERSION_PATCH, int)

    def test_version_string_format(self):
        """Test VERSION_STRING has correct format."""
        self.assertTrue(VERSION_STRING.startswith("v"))
        self.assertEqual(
            VERSION_STRING, f"v{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
        )

    def test_dunder_version_format(self):
        """Test __version__ has correct format."""
        self.assertEqual(
            __version__, f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
        )


if __name__ == "__main__":
    unittest.main()
