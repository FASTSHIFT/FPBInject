#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Safe parser module tests.

Tests for robust string parsing, path handling, and FPB marker detection.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.safe_parser import (  # noqa: E402
    safe_shlex_split,
    quote_path,
    normalize_path,
    safe_path_join,
    path_matches_suffix,
    parse_dep_file_command,
    FPBMarkerParser,
    CommandBuilder,
    validate_source_content,
    sanitize_function_name,
)


class TestSafeShellParsing(unittest.TestCase):
    """Tests for safe shell command parsing."""

    def test_simple_command(self):
        """Test parsing simple command."""
        result = safe_shlex_split("gcc -c -o test.o test.c")
        self.assertEqual(result, ["gcc", "-c", "-o", "test.o", "test.c"])

    def test_quoted_path_with_spaces(self):
        """Test parsing command with quoted path containing spaces."""
        result = safe_shlex_split('gcc -I"/path/with spaces/include" -c test.c')
        self.assertEqual(result, ["gcc", "-I/path/with spaces/include", "-c", "test.c"])

    def test_unmatched_quote_fallback(self):
        """Test fallback when quotes are unmatched."""
        # This would fail with standard shlex
        result = safe_shlex_split('gcc -DSTRING="hello world -c test.c', fallback=True)
        self.assertIsNotNone(result)
        self.assertIn("gcc", result)

    def test_unmatched_quote_no_fallback(self):
        """Test returning None when fallback is disabled."""
        result = safe_shlex_split('gcc -DSTRING="hello world', fallback=False)
        self.assertIsNone(result)

    def test_empty_command(self):
        """Test parsing empty command."""
        result = safe_shlex_split("")
        self.assertEqual(result, [])

    def test_none_command(self):
        """Test parsing None command."""
        result = safe_shlex_split(None)
        self.assertEqual(result, [])

    def test_special_characters(self):
        """Test parsing command with special characters."""
        result = safe_shlex_split("gcc -DVERSION='1.0.0' -DNAME=\"test\" test.c")
        self.assertIn("gcc", result)
        self.assertIn("-DVERSION=1.0.0", result)

    def test_backslash_escape(self):
        """Test parsing command with backslash escapes."""
        result = safe_shlex_split(r"gcc -DPATH=\"/path\" test.c")
        self.assertIsNotNone(result)


class TestQuotePath(unittest.TestCase):
    """Tests for path quoting."""

    def test_simple_path(self):
        """Test quoting simple path."""
        result = quote_path("/usr/bin/gcc")
        self.assertEqual(result, "/usr/bin/gcc")

    def test_path_with_spaces(self):
        """Test quoting path with spaces."""
        result = quote_path("/path/with spaces/file.c")
        self.assertIn("'", result)  # Should be quoted

    def test_path_with_special_chars(self):
        """Test quoting path with special characters."""
        result = quote_path("/path/with$special;chars")
        # Should be quoted (shlex.quote wraps in single quotes)
        self.assertTrue(result.startswith("'") or result.startswith('"'))


class TestPathHandling(unittest.TestCase):
    """Tests for cross-platform path handling."""

    def test_normalize_path(self):
        """Test path normalization."""
        result = normalize_path("./test/../test/file.c")
        self.assertTrue(result.is_absolute())

    def test_safe_path_join(self):
        """Test safe path joining."""
        result = safe_path_join("/base", "sub", "file.c")
        self.assertEqual(result, Path("/base/sub/file.c"))

    def test_safe_path_join_empty(self):
        """Test safe path join with no arguments."""
        result = safe_path_join()
        self.assertEqual(result, Path("."))

    def test_path_matches_suffix_exact(self):
        """Test path suffix matching with exact match."""
        self.assertTrue(
            path_matches_suffix(
                "/home/user/project/src/main.c",
                "/other/path/project/src/main.c",
                min_depth=3,
            )
        )

    def test_path_matches_suffix_partial(self):
        """Test path suffix matching with partial match."""
        self.assertTrue(
            path_matches_suffix("/a/b/c/d/e.c", "/x/y/c/d/e.c", min_depth=3)
        )

    def test_path_matches_suffix_no_match(self):
        """Test path suffix matching with no match."""
        self.assertFalse(
            path_matches_suffix("/a/b/c/d/e.c", "/x/y/z/w/v.c", min_depth=3)
        )


class TestDepFileParsing(unittest.TestCase):
    """Tests for dependency file parsing."""

    def test_gnu_make_format(self):
        """Test parsing GNU Make style .d file."""
        content = "cmd_path/test.o := gcc -c -DTEST -o test.o test.c\n"
        result = parse_dep_file_command(content, "test.c")
        self.assertIsNotNone(result)
        self.assertIn("gcc", result)
        self.assertIn("-DTEST", result)

    def test_ninja_format(self):
        """Test parsing Ninja style .d file."""
        content = "command = gcc -c -DNINJA -o test.o test.c\n"
        result = parse_dep_file_command(content)
        self.assertIsNotNone(result)
        self.assertIn("-DNINJA", result)

    def test_simple_format(self):
        """Test parsing simple assignment format."""
        content = "CC = gcc -c -DSIMPLE test.c\n"
        result = parse_dep_file_command(content)
        self.assertIsNotNone(result)

    def test_source_file_validation(self):
        """Test that source file must be in content."""
        content = "cmd_path/other.o := gcc -c other.c\n"
        result = parse_dep_file_command(content, "test.c")
        self.assertIsNone(result)

    def test_empty_content(self):
        """Test parsing empty content."""
        result = parse_dep_file_command("")
        self.assertIsNone(result)

    def test_no_command_found(self):
        """Test when no command pattern matches."""
        content = "test.o: test.c test.h\n"
        result = parse_dep_file_command(content)
        self.assertIsNone(result)


class TestFPBMarkerParser(unittest.TestCase):
    """Tests for FPB_INJECT marker parsing."""

    def test_simple_marker(self):
        """Test simple FPB_INJECT marker."""
        content = """
/* FPB_INJECT */
void test_func(void) {
}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["test_func"])

    def test_marker_with_attribute(self):
        """Test marker with __attribute__."""
        content = """
/* FPB_INJECT */
__attribute__((section(".text")))
void test_func(void) {
}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["test_func"])

    def test_multiline_attribute(self):
        """Test marker with multiline __attribute__."""
        content = """
/* FPB_INJECT */
__attribute__((
    section(".text"),
    used
))
void test_func(void) {
}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["test_func"])

    def test_case_insensitive(self):
        """Test case-insensitive marker detection."""
        content = """
/* fpb_inject */
void func1(void) {}

/* FPB-INJECT */
void func2(void) {}

/* Fpb Inject */
void func3(void) {}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertIn("func1", funcs)
        self.assertIn("func2", funcs)
        self.assertIn("func3", funcs)

    def test_line_comment_marker(self):
        """Test line comment marker."""
        content = """
// FPB_INJECT
void test_func(void) {}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["test_func"])

    def test_marker_with_description(self):
        """Test marker with description."""
        content = """
/* FPB_INJECT: This patches the main loop */
void main_loop(void) {}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["main_loop"])

    def test_multiple_functions(self):
        """Test multiple marked functions."""
        content = """
/* FPB_INJECT */
void func1(void) {}

void unmarked_func(void) {}

/* FPB_INJECT */
int func2(int x) { return x; }
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(len(funcs), 2)
        self.assertIn("func1", funcs)
        self.assertIn("func2", funcs)
        self.assertNotIn("unmarked_func", funcs)

    def test_complex_return_types(self):
        """Test functions with complex return types."""
        content = """
/* FPB_INJECT */
static inline uint32_t get_value(void) { return 0; }

/* FPB_INJECT */
const char* get_string(void) { return ""; }

/* FPB_INJECT */
int get_data(void) { return 0; }
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertIn("get_value", funcs)
        self.assertIn("get_string", funcs)
        self.assertIn("get_data", funcs)

    def test_extern_c(self):
        """Test extern "C" functions."""
        content = """
/* FPB_INJECT */
extern "C" void c_func(void) {}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["c_func"])

    def test_skip_keywords(self):
        """Test that keywords are not matched as function names."""
        content = """
/* FPB_INJECT */
if (condition) {}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, [])

    def test_template_function(self):
        """Test that template-like patterns don't break parsing."""
        content = """
/* FPB_INJECT */
void process_data(int data) {
    if (data > 0) {
        return;
    }
}
"""
        funcs = FPBMarkerParser.extract_function_names(content)
        self.assertEqual(funcs, ["process_data"])


class TestCommandBuilder(unittest.TestCase):
    """Tests for command builder."""

    def test_simple_command(self):
        """Test building simple command."""
        cmd = CommandBuilder("gcc").add_flag("-c").add_source("test.c").build()
        self.assertEqual(cmd, ["gcc", "-c", "test.c"])

    def test_include_and_define(self):
        """Test adding includes and defines."""
        cmd = (
            CommandBuilder("gcc")
            .add_include("/usr/include")
            .add_define("DEBUG")
            .add_define("VERSION", "1.0")
            .build()
        )
        self.assertIn("-I", cmd)
        self.assertIn("/usr/include", cmd)
        self.assertIn("-DDEBUG", cmd)
        self.assertIn("-DVERSION=1.0", cmd)

    def test_output_file(self):
        """Test adding output file."""
        cmd = CommandBuilder("gcc").add_output("test.o").build()
        self.assertEqual(cmd, ["gcc", "-o", "test.o"])

    def test_build_string(self):
        """Test building command as string."""
        cmd_str = (
            CommandBuilder("gcc").add_flag("-c").add_source("test.c").build_string()
        )
        self.assertIn("gcc", cmd_str)
        self.assertIn("-c", cmd_str)


class TestValidation(unittest.TestCase):
    """Tests for validation utilities."""

    def test_valid_source(self):
        """Test validating valid source."""
        content = "void test() { int x = 0; }"
        valid, error = validate_source_content(content)
        self.assertTrue(valid)
        self.assertEqual(error, "")

    def test_empty_source(self):
        """Test validating empty source."""
        valid, error = validate_source_content("")
        self.assertFalse(valid)
        self.assertIn("Empty", error)

    def test_unbalanced_braces(self):
        """Test detecting unbalanced braces."""
        content = "void test() { int x = 0; "
        valid, error = validate_source_content(content)
        self.assertFalse(valid)
        self.assertIn("brace", error.lower())

    def test_unbalanced_parens(self):
        """Test detecting unbalanced parentheses."""
        content = "void test( { }"
        valid, error = validate_source_content(content)
        self.assertFalse(valid)
        self.assertIn("parenthes", error.lower())

    def test_sanitize_function_name(self):
        """Test function name sanitization."""
        self.assertEqual(sanitize_function_name("test_func"), "test_func")
        self.assertEqual(sanitize_function_name("123func"), "_123func")
        self.assertEqual(sanitize_function_name("func-name"), "funcname")


class TestCaching(unittest.TestCase):
    """Tests for caching functionality."""

    def test_cached_parse_decorator(self):
        """Test that cached_parse decorator works."""
        from core.safe_parser import cached_parse

        call_count = [0]

        @cached_parse(maxsize=2)
        def parse_file(path):
            call_count[0] += 1
            return f"parsed:{path}"

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("test content")
            path = f.name

        try:
            # First call should execute function
            result1 = parse_file(path)
            self.assertEqual(call_count[0], 1)

            # Second call should use cache
            result2 = parse_file(path)
            self.assertEqual(call_count[0], 1)  # Still 1
            self.assertEqual(result1, result2)

            # Clear cache
            parse_file.cache_clear()

            # Third call should execute function again
            _ = parse_file(path)
            self.assertEqual(call_count[0], 2)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
