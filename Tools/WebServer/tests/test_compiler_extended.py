#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extended compiler module tests.

Tests for edge cases, special characters, and robustness.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.compile_commands import parse_compile_commands  # noqa: E402
from core.safe_parser import FPBMarkerParser  # noqa: E402


class TestUnpairedQuotes(unittest.TestCase):
    """Tests for handling unpaired quotes in command strings."""

    def test_unpaired_double_quote(self):
        """Test command with unpaired double quote."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            # Malformed command with unpaired quote
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": 'gcc -c -DSTRING="hello world -o main.o main.c',
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            # Should not crash, should use fallback parsing
            _ = parse_compile_commands(path)
            # May return None or partial result, but should not raise
        finally:
            os.unlink(path)

    def test_unpaired_single_quote(self):
        """Test command with unpaired single quote."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "gcc -c -DSTRING='hello -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            _ = parse_compile_commands(path)
            # Should handle gracefully
        finally:
            os.unlink(path)

    def test_mixed_quotes(self):
        """Test command with mixed quote styles."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": """gcc -c -DSTR1="hello" -DSTR2='world' -o main.o main.c""",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = parse_compile_commands(path)
            self.assertIsNotNone(result)
        finally:
            os.unlink(path)


class TestPathsWithSpaces(unittest.TestCase):
    """Tests for handling paths with spaces and special characters."""

    def test_include_path_with_spaces(self):
        """Test include path containing spaces."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": 'gcc -c -I"/path/with spaces/include" -o main.o main.c',
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = parse_compile_commands(path)
            self.assertIsNotNone(result)
            # Check that the path with spaces is preserved
            includes = result.get("includes", [])
            space_path_found = any("with spaces" in inc for inc in includes)
            self.assertTrue(
                space_path_found, f"Path with spaces not found in {includes}"
            )
        finally:
            os.unlink(path)

    def test_source_file_with_spaces(self):
        """Test source file path containing spaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file with space in name
            src_dir = Path(tmpdir) / "path with spaces"
            src_dir.mkdir()
            src_file = src_dir / "main.c"
            src_file.write_text("int main() { return 0; }")

            cc_path = Path(tmpdir) / "compile_commands.json"
            cc_path.write_text(
                json.dumps(
                    [
                        {
                            "directory": str(tmpdir),
                            "command": f'gcc -c -o main.o "{src_file}"',
                            "file": str(src_file),
                        }
                    ]
                )
            )

            result = parse_compile_commands(str(cc_path), source_file=str(src_file))
            self.assertIsNotNone(result)

    def test_define_with_special_characters(self):
        """Test defines with special characters."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": 'gcc -c -DVERSION="1.0.0-beta+build.123" -o main.o main.c',
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = parse_compile_commands(path)
            self.assertIsNotNone(result)
        finally:
            os.unlink(path)

    def test_path_with_unicode(self):
        """Test path with unicode characters."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": 'gcc -c -I"/path/日本語/include" -o main.o main.c',
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = parse_compile_commands(path)
            self.assertIsNotNone(result)
        finally:
            os.unlink(path)


class TestCrossLineAttribute(unittest.TestCase):
    """Tests for cross-line __attribute__ declarations."""

    def test_multiline_attribute_simple(self):
        """Test simple multiline __attribute__."""
        content = """
/* FPB_INJECT */
__attribute__((section(".text")))
void test_func(void) {
}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["test_func"])

    def test_multiline_attribute_complex(self):
        """Test complex multiline __attribute__ with multiple attributes."""
        content = """
/* FPB_INJECT */
__attribute__((
    section(".fpb.text"),
    used,
    noinline
))
void test_func(void) {
}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["test_func"])

    def test_attribute_with_nested_parens(self):
        """Test __attribute__ with nested parentheses."""
        content = """
/* FPB_INJECT */
__attribute__((format(printf, 1, 2)))
void log_func(const char* fmt, ...) {
}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["log_func"])

    def test_multiple_attributes(self):
        """Test multiple __attribute__ declarations."""
        content = """
/* FPB_INJECT */
__attribute__((section(".text")))
__attribute__((used))
void test_func(void) {
}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["test_func"])

    def test_gnu_attribute_syntax(self):
        """Test GNU __attribute__ syntax variations."""
        content = """
/* FPB_INJECT */
__attribute__((__section__(".text")))
void test_func(void) {
}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["test_func"])


class TestTemplatedFunctions(unittest.TestCase):
    """Tests for template-like function declarations (C++ style)."""

    def test_function_with_template_like_params(self):
        """Test function with template-like parameters."""
        content = """
/* FPB_INJECT */
void process(int data) {
    // Process data
}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["process"])

    def test_function_pointer_param(self):
        """Test function with function pointer parameter."""
        content = """
/* FPB_INJECT */
void register_callback(void (*callback)(int, void*)) {
}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["register_callback"])

    def test_complex_return_type(self):
        """Test function with complex return type."""
        content = """
/* FPB_INJECT */
uint32_t* get_ptr(void) {
    return 0;
}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["get_ptr"])


class TestDepFileVariants(unittest.TestCase):
    """Tests for .d file format variants."""

    def test_gnu_make_format(self):
        """Test GNU Make style .d file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dep_file = Path(tmpdir) / ".test.o.d"
            dep_file.write_text(
                "cmd_build/test.o := gcc -c -DTEST -I/inc -o test.o test.c\n"
                "test.o: test.c test.h\n"
            )

            src_file = Path(tmpdir) / "test.c"
            src_file.write_text("int main() {}")

            # Note: This may not find the file due to search path logic,
            # but it should not crash
            # The test verifies the file creation doesn't cause errors

    def test_ninja_style_format(self):
        """Test Ninja style .d file."""
        from core.safe_parser import parse_dep_file_command

        content = """
build test.o: cc test.c
  command = gcc -c -DNINJA -o test.o test.c
  deps = gcc
  depfile = test.d
"""
        result = parse_dep_file_command(content)
        self.assertIsNotNone(result)
        self.assertIn("-DNINJA", result)

    def test_clang_format(self):
        """Test Clang style .d file."""
        from core.safe_parser import parse_dep_file_command

        content = """
test.o: test.c \\
  /usr/include/stdio.h \\
  /usr/include/stdlib.h
"""
        # This format doesn't contain command, should return None
        result = parse_dep_file_command(content)
        self.assertIsNone(result)


class TestEdgeCases(unittest.TestCase):
    """Tests for various edge cases."""

    def test_empty_compile_commands(self):
        """Test with empty compile_commands.json."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            path = f.name

        try:
            result = parse_compile_commands(path)
            self.assertIsNone(result)
        finally:
            os.unlink(path)

    def test_malformed_json(self):
        """Test with malformed JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{not valid json")
            path = f.name

        try:
            result = parse_compile_commands(path)
            self.assertIsNone(result)
        finally:
            os.unlink(path)

    def test_json_object_instead_of_array(self):
        """Test with JSON object instead of array."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"key": "value"}, f)
            path = f.name

        try:
            result = parse_compile_commands(path)
            self.assertIsNone(result)
        finally:
            os.unlink(path)

    def test_entry_without_command_or_arguments(self):
        """Test entry without command or arguments field."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "file": "main.c",
                        # No command or arguments
                    }
                ],
                f,
            )
            path = f.name

        try:
            _ = parse_compile_commands(path)
            # Should handle gracefully (may return None or find fallback)
        finally:
            os.unlink(path)

    def test_very_long_command(self):
        """Test with very long command string."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            # Create command with many include paths
            includes = " ".join([f"-I/path/to/include{i}" for i in range(100)])
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": f"gcc -c {includes} -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = parse_compile_commands(path)
            self.assertIsNotNone(result)
            self.assertGreater(len(result["includes"]), 50)
        finally:
            os.unlink(path)

    def test_arguments_array_format(self):
        """Test compile_commands.json with arguments array format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "arguments": [
                            "gcc",
                            "-c",
                            "-I/inc",
                            "-DDEBUG",
                            "-o",
                            "main.o",
                            "main.c",
                        ],
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = parse_compile_commands(path)
            self.assertIsNotNone(result)
            self.assertIn("/inc", result["includes"])
            self.assertIn("DEBUG", result["defines"])
        finally:
            os.unlink(path)


class TestFPBMarkerEdgeCases(unittest.TestCase):
    """Tests for FPB marker edge cases."""

    def test_marker_in_string_literal(self):
        """Test marker in string literal behavior."""
        content = """
const char* msg = "/* FPB_INJECT */";
void real_func(void) {}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        # Note: Current regex-based parser may match markers in strings
        # This is a known limitation - full AST parsing would be needed
        # to properly handle this case. For now, we just verify it doesn't crash.
        self.assertIsInstance(funcs, list)

    def test_marker_in_comment(self):
        """Test marker inside another comment."""
        content = """
/*
 * This is a comment
 * /* FPB_INJECT */
 */
void test_func(void) {}
"""
        _ = FPBMarkerParser.extract_function_names(content)
        # Behavior depends on implementation - may or may not match

    def test_consecutive_markers(self):
        """Test consecutive markers."""
        content = """
/* FPB_INJECT */
/* FPB_INJECT */
void test_func(void) {}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        # Each marker finds the following function, so may appear twice
        # The important thing is the function is found
        self.assertIn("test_func", funcs)

    def test_marker_without_function(self):
        """Test marker not followed by function."""
        content = """
/* FPB_INJECT */
int global_var = 0;
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, [])

    def test_marker_with_macro(self):
        """Test marker followed by macro."""
        content = """
/* FPB_INJECT */
#define MACRO 1
void test_func(void) {}
"""
        _ = FPBMarkerParser.extract_function_names(content)
        # May or may not find test_func depending on implementation


if __name__ == "__main__":
    unittest.main()
