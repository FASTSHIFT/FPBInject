#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch Generator v2 (Marker Based) Module Tests
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.patch_generator import (
    PatchGenerator,
    check_dependencies,
    FPB_INJECT_MARKER,
    FPB_SECTION_ATTR,
)


class TestFindMarkedFunctions(unittest.TestCase):
    """Test finding FPB_INJECT markers"""

    def setUp(self):
        self.gen = PatchGenerator()

    def test_find_single_marker(self):
        """Test finding single marker"""
        content = """
#include <stdio.h>

/* FPB_INJECT */
void my_function(void) {
    printf("hello");
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["my_function"])

    def test_find_multiple_markers(self):
        """Test finding multiple markers"""
        content = """
/* FPB_INJECT */
int func1(int x) {
    return x + 1;
}

void untagged_func(void) {
    // not marked
}

/* FPB_INJECT */
void func2(void) {
    return;
}

/* FPB_INJECT */
static int func3(int a, int b) {
    return a + b;
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(len(marked), 3)
        self.assertIn("func1", marked)
        self.assertIn("func2", marked)
        self.assertIn("func3", marked)

    def test_marker_with_description(self):
        """Test marker with description"""
        content = """
/* FPB_INJECT: Fix memory leak issue */
void fix_memory_leak(void) {
    free(ptr);
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["fix_memory_leak"])

    def test_no_markers(self):
        """Test file with no markers"""
        content = """
void normal_func(void) {
    return;
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, [])

    def test_marker_with_static_inline(self):
        """Test function with static inline"""
        content = """
/* FPB_INJECT */
static inline int fast_func(int x) {
    return x * 2;
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["fast_func"])

    def test_marker_with_pointer_return(self):
        """Test function returning pointer"""
        content = """
/* FPB_INJECT */
void * allocate_memory(size_t size) {
    return malloc(size);
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["allocate_memory"])

    def test_marker_multiline_signature(self):
        """Test multiline signature"""
        content = """
/* FPB_INJECT */
int complex_function(
    int param1,
    int param2,
    void *data
) {
    return 0;
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["complex_function"])

    def test_marker_with_space_separator(self):
        """Test marker with space between fpb and inject"""
        content = """
/* fpb inject */
void spaced_func(void) {
    return;
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["spaced_func"])

    def test_marker_with_multiple_spaces(self):
        """Test marker with multiple spaces between fpb and inject"""
        content = """
/* fpb  inject  */
void multi_space_func(void) {
    return;
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["multi_space_func"])

    def test_marker_with_mixed_separators(self):
        """Test marker with mixed separators (space and underscore)"""
        content = """
/* FPB _INJECT */
void mixed_sep_func(void) {
    return;
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["mixed_sep_func"])

    def test_marker_no_separator(self):
        """Test marker with no separator (fpbinject)"""
        content = """
/*fpbinject*/
void no_sep_func(void) {
    return;
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["no_sep_func"])

    def test_marker_with_hyphen_separator(self):
        """Test marker with hyphen separator"""
        content = """
/* fpb-inject */
void hyphen_func(void) {
    return;
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["hyphen_func"])


class TestGeneratePatch(unittest.TestCase):
    """Test patch generation"""

    def setUp(self):
        self.gen = PatchGenerator()

    def test_generate_patch_adds_section_attribute(self):
        """Test that patch generation adds section attribute to marked functions"""
        content = """
#include <stdio.h>

/* FPB_INJECT */
void target_func(void) {
    printf("patched");
}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write(content)
            f.flush()

            patch_content, marked = self.gen.generate_patch(f.name)

            # Verify section attribute is added
            self.assertIn(FPB_SECTION_ATTR, patch_content)
            # Verify function name is NOT renamed (original name preserved)
            self.assertIn("void target_func(void)", patch_content)
            self.assertEqual(marked, ["target_func"])

            os.unlink(f.name)

    def test_generate_patch_preserves_other_code(self):
        """Test that patch preserves other code"""
        content = """
#include <stdio.h>
#include <stdlib.h>

#define MY_MACRO 42

struct MyStruct {
    int x;
    int y;
};

static int helper_func(int x) {
    return x * 2;
}

/* FPB_INJECT */
void target_func(void) {
    struct MyStruct s;
    s.x = MY_MACRO;
    s.y = helper_func(s.x);
}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write(content)
            f.flush()

            patch_content, marked = self.gen.generate_patch(f.name)

            # Verify other code is preserved
            self.assertIn("#include <stdio.h>", patch_content)
            self.assertIn("#include <stdlib.h>", patch_content)
            self.assertIn("#define MY_MACRO 42", patch_content)
            self.assertIn("struct MyStruct", patch_content)
            self.assertIn("helper_func", patch_content)
            # Function name preserved, section attribute added
            self.assertIn("target_func", patch_content)
            self.assertIn(FPB_SECTION_ATTR, patch_content)

            os.unlink(f.name)

    def test_generate_patch_no_markers(self):
        """Test returns empty when no markers"""
        content = """
void normal_func(void) {
    return;
}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write(content)
            f.flush()

            patch_content, marked = self.gen.generate_patch(f.name)

            self.assertEqual(patch_content, "")
            self.assertEqual(marked, [])

            os.unlink(f.name)

    def test_generate_patch_adds_header(self):
        """Test patch adds header comment"""
        content = """
/* FPB_INJECT */
void func(void) { }
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write(content)
            f.flush()

            patch_content, _ = self.gen.generate_patch(f.name)

            self.assertIn("Auto-generated patch file by FPBInject", patch_content)
            self.assertIn("Source:", patch_content)
            self.assertIn("Inject functions:", patch_content)

            os.unlink(f.name)

    def test_generate_patch_converts_include_paths(self):
        """Test relative include path conversion"""
        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create header file
            header_path = os.path.join(tmpdir, "my_header.h")
            with open(header_path, "w") as h:
                h.write("#define TEST 1\n")

            # Create source file
            source_path = os.path.join(tmpdir, "source.c")
            content = """
#include "my_header.h"

/* FPB_INJECT */
void func(void) { }
"""
            with open(source_path, "w") as s:
                s.write(content)

            patch_content, _ = self.gen.generate_patch(source_path)

            # Verify path is converted to absolute path
            self.assertIn(header_path, patch_content)


class TestSectionAttribute(unittest.TestCase):
    """Test section attribute functionality"""

    def setUp(self):
        self.gen = PatchGenerator()

    def test_section_attribute_value(self):
        """Test section attribute has correct value"""
        self.assertIn(".fpb.text", FPB_SECTION_ATTR)
        self.assertIn("used", FPB_SECTION_ATTR)

    def test_is_marker_line(self):
        """Test marker line detection"""
        # Block comment markers
        self.assertTrue(self.gen._is_marker_line("/* FPB_INJECT */"))
        self.assertTrue(self.gen._is_marker_line("/* fpb_inject */"))
        self.assertTrue(self.gen._is_marker_line("/* FPB-INJECT */"))
        self.assertTrue(self.gen._is_marker_line("/* fpb inject */"))
        self.assertTrue(self.gen._is_marker_line("/*fpbinject*/"))
        self.assertTrue(self.gen._is_marker_line("/* FPB_INJECT: description */"))

        # Line comment markers
        self.assertTrue(self.gen._is_marker_line("// FPB_INJECT"))
        self.assertTrue(self.gen._is_marker_line("// fpb_inject"))

        # Non-marker lines
        self.assertFalse(self.gen._is_marker_line("void foo(void) {"))
        self.assertFalse(self.gen._is_marker_line("// Some other comment"))
        self.assertFalse(self.gen._is_marker_line("/* Regular comment */"))

    def test_is_function_definition(self):
        """Test function definition detection"""
        marked_funcs = ["foo", "bar"]

        # Function definitions
        self.assertTrue(
            self.gen._is_function_definition("void foo(void) {", marked_funcs)
        )
        self.assertTrue(
            self.gen._is_function_definition("int bar(int x) {", marked_funcs)
        )
        self.assertTrue(
            self.gen._is_function_definition("static void foo(void)", marked_funcs)
        )

        # Non-matching functions
        self.assertFalse(
            self.gen._is_function_definition("void baz(void) {", marked_funcs)
        )
        self.assertFalse(self.gen._is_function_definition("int x = 5;", marked_funcs))

    def test_no_double_attribute(self):
        """Test that attribute is not added if already present"""
        content = (
            "/* FPB_INJECT */\n"
            '__attribute__((section(".fpb.text"), used))\n'
            "void func(void) { }\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write(content)
            f.flush()

            patch_content, marked = self.gen.generate_patch(f.name)

            # Function should be found
            self.assertEqual(marked, ["func"])
            # Count occurrences of section attribute - should only appear once
            count = patch_content.count(FPB_SECTION_ATTR)
            self.assertEqual(count, 1)

            os.unlink(f.name)


class TestConvertIncludePath(unittest.TestCase):
    """Test include path conversion"""

    def setUp(self):
        self.gen = PatchGenerator()

    def test_convert_relative_path(self):
        """Test converting relative path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create header file
            header = os.path.join(tmpdir, "header.h")
            with open(header, "w") as f:
                f.write("")

            line = '#include "header.h"'
            result = self.gen._convert_include_path(line, tmpdir)
            self.assertIn(header, result)

    def test_keep_system_include(self):
        """Test keeping system include"""
        line = "#include <stdio.h>"
        result = self.gen._convert_include_path(line, "/tmp")
        self.assertEqual(result, line)

    def test_keep_absolute_path(self):
        """Test keeping existing absolute path"""
        line = '#include "/abs/path/header.h"'
        result = self.gen._convert_include_path(line, "/tmp")
        self.assertEqual(result, line)

    def test_keep_nonexistent_relative(self):
        """Test keeping nonexistent relative path"""
        line = '#include "nonexistent.h"'
        result = self.gen._convert_include_path(line, "/tmp")
        self.assertEqual(result, line)


class TestGeneratePatchFromFile(unittest.TestCase):
    """Test advanced API"""

    def setUp(self):
        self.gen = PatchGenerator()

    def test_file_not_found(self):
        """Test file not found"""
        result, marked = self.gen.generate_patch_from_file("/nonexistent/file.c")
        self.assertIsNone(result)
        self.assertEqual(marked, [])

    def test_with_output_dir(self):
        """Test specifying output directory"""
        content = """
/* FPB_INJECT */
void func(void) { }
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.c")
            with open(source, "w") as f:
                f.write(content)

            output_dir = os.path.join(tmpdir, "output")
            os.makedirs(output_dir)

            result_path, marked = self.gen.generate_patch_from_file(source, output_dir)

            self.assertIsNotNone(result_path)
            self.assertTrue(os.path.exists(result_path))
            self.assertEqual(marked, ["func"])

            # Verify output filename
            self.assertIn("patch_source.c", result_path)


class TestCheckDependencies(unittest.TestCase):
    """Test dependency checking"""

    def test_check_dependencies(self):
        """Test dependency checking"""
        deps = check_dependencies()
        self.assertIn("git", deps)
        # git should be available
        self.assertTrue(deps["git"])


class TestMarkerConstant(unittest.TestCase):
    """Test marker constant"""

    def test_marker_value(self):
        """Test marker value"""
        self.assertEqual(FPB_INJECT_MARKER, "FPB_INJECT")


if __name__ == "__main__":
    unittest.main()
