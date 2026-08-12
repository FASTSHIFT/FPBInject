#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for version.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re

from fpbinject.version import (
    VERSION_MAJOR,
    VERSION_MINOR,
    VERSION_PATCH,
    VERSION_PRERELEASE,
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

    def test_prerelease_is_str(self):
        """Test VERSION_PRERELEASE is a string (empty for stable releases)."""
        self.assertIsInstance(VERSION_PRERELEASE, str)

    def test_prerelease_format(self):
        """Pre-release suffix, when present, must be PEP 440 (a|b|rc + N)."""
        if VERSION_PRERELEASE:
            self.assertRegex(VERSION_PRERELEASE, r"^(a|b|rc)\d+$")

    def test_dunder_version_format(self):
        """__version__ is MAJOR.MINOR.PATCH plus the optional pre-release."""
        base = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
        self.assertEqual(__version__, f"{base}{VERSION_PRERELEASE}")

    def test_dunder_version_is_pep440(self):
        """__version__ must be a valid PEP 440 release / pre-release string."""
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?$")
        # Base release portion always matches the three integer fields.
        base = re.match(r"^\d+\.\d+\.\d+", __version__).group(0)
        self.assertEqual(base, f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}")


if __name__ == "__main__":
    unittest.main()
