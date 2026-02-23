#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Linker script module tests.

Tests for linker script template generation.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.linker_script import (  # noqa: E402
    LinkerScriptConfig,
    LinkerScriptGenerator,
    create_linker_script,
    get_default_config,
)


class TestLinkerScriptConfig(unittest.TestCase):
    """Tests for LinkerScriptConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LinkerScriptConfig()
        self.assertEqual(config.text_section, ".text")
        self.assertEqual(config.bss_section, ".bss")
        self.assertEqual(config.fpb_text_section, ".fpb.text")
        self.assertEqual(config.section_alignment, 4)
        self.assertTrue(config.include_bss_in_binary)

    def test_from_dict(self):
        """Test creating config from dictionary."""
        config = LinkerScriptConfig.from_dict(
            {
                "text_section": ".custom_text",
                "bss_alignment": 8,
            }
        )
        self.assertEqual(config.text_section, ".custom_text")
        self.assertEqual(config.bss_alignment, 8)
        # Defaults should be preserved
        self.assertEqual(config.rodata_section, ".rodata")

    def test_from_dict_ignores_unknown(self):
        """Test that unknown keys are ignored."""
        config = LinkerScriptConfig.from_dict(
            {
                "unknown_key": "value",
                "text_section": ".text",
            }
        )
        self.assertEqual(config.text_section, ".text")


class TestLinkerScriptGenerator(unittest.TestCase):
    """Tests for LinkerScriptGenerator."""

    def test_generate_default(self):
        """Test generating linker script with defaults."""
        generator = LinkerScriptGenerator()
        content = generator.generate(0x20001000)

        self.assertIn("0x20001000", content)
        self.assertIn(".text", content)
        self.assertIn(".bss", content)
        self.assertIn(".fpb.text", content)
        self.assertIn("KEEP", content)

    def test_generate_custom_base_addr(self):
        """Test generating with custom base address."""
        generator = LinkerScriptGenerator()
        content = generator.generate(0x08010000)

        self.assertIn("0x08010000", content)

    def test_generate_custom_sections(self):
        """Test generating with custom section names."""
        config = LinkerScriptConfig(
            text_section=".custom_text",
            bss_section=".custom_bss",
        )
        generator = LinkerScriptGenerator(config=config)
        content = generator.generate(0x20001000)

        self.assertIn(".custom_text", content)
        self.assertIn(".custom_bss", content)

    def test_generate_without_bss_marker(self):
        """Test generating without BSS marker section."""
        config = LinkerScriptConfig(include_bss_in_binary=False)
        generator = LinkerScriptGenerator(config=config)
        content = generator.generate(0x20001000)

        self.assertNotIn(".fpb_end", content)

    def test_generate_with_extra_sections(self):
        """Test generating with extra sections."""
        config = LinkerScriptConfig(
            extra_sections={
                ".custom": "*(.custom .custom.*)",
            }
        )
        generator = LinkerScriptGenerator(config=config)
        content = generator.generate(0x20001000)

        self.assertIn(".custom", content)

    def test_save_to_file(self):
        """Test saving linker script to file."""
        generator = LinkerScriptGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.ld")
            result = generator.save_to_file(0x20001000, output_path)

            self.assertEqual(result, output_path)
            self.assertTrue(os.path.exists(output_path))

            content = Path(output_path).read_text()
            self.assertIn("0x20001000", content)

    def test_load_custom_template(self):
        """Test loading custom template from file."""
        custom_template = """
/* Custom template */
SECTIONS
{
    . = 0x${base_addr};
    .text : { *(.text) }
}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ld.in", delete=False) as f:
            f.write(custom_template)
            template_path = f.name

        try:
            generator = LinkerScriptGenerator(template_path=template_path)
            content = generator.generate(0x20001000)

            self.assertIn("Custom template", content)
            self.assertIn("0x20001000", content)
        finally:
            os.unlink(template_path)

    def test_fallback_on_missing_template(self):
        """Test fallback when template file is missing."""
        generator = LinkerScriptGenerator(template_path="/nonexistent/template.ld.in")
        content = generator.generate(0x20001000)

        # Should use default template
        self.assertIn("0x20001000", content)
        self.assertIn(".text", content)


class TestCreateLinkerScript(unittest.TestCase):
    """Tests for create_linker_script factory function."""

    def test_create_default(self):
        """Test creating linker script with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "inject.ld")
            result = create_linker_script(0x20001000, output_path)

            self.assertEqual(result, output_path)
            self.assertTrue(os.path.exists(output_path))

    def test_create_with_config(self):
        """Test creating linker script with custom config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "inject.ld")
            result = create_linker_script(
                0x20001000,
                output_path,
                config={"bss_alignment": 16},
            )

            content = Path(result).read_text()
            self.assertIn("ALIGN(16)", content)


class TestGetDefaultConfig(unittest.TestCase):
    """Tests for get_default_config function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        config = get_default_config()
        self.assertIsInstance(config, dict)

    def test_contains_expected_keys(self):
        """Test that config contains expected keys."""
        config = get_default_config()
        expected_keys = [
            "text_section",
            "rodata_section",
            "data_section",
            "bss_section",
            "fpb_text_section",
            "section_alignment",
            "bss_alignment",
            "include_bss_in_binary",
        ]
        for key in expected_keys:
            self.assertIn(key, config)


if __name__ == "__main__":
    unittest.main()
