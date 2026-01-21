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

from patch_generator import PatchGenerator, check_dependencies, FPB_INJECT_MARKER


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


class TestGeneratePatch(unittest.TestCase):
    """Test patch generation"""

    def setUp(self):
        self.gen = PatchGenerator()

    def test_generate_patch_renames_function(self):
        """Test that patch generation renames marked functions"""
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

            # Verify function is renamed
            self.assertIn("inject_target_func", patch_content)
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
            self.assertIn("inject_target_func", patch_content)

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


class TestRenameFunctions(unittest.TestCase):
    """Test function renaming"""

    def setUp(self):
        self.gen = PatchGenerator()

    def test_rename_simple(self):
        """Test simple function renaming"""
        line = "void my_func(void) {"
        result = self.gen._rename_function(line, "my_func")
        self.assertEqual(result, "void inject_my_func(void) {")

    def test_rename_with_pointer(self):
        """Test renaming function that returns pointer"""
        line = "void *my_func(size_t size) {"
        result = self.gen._rename_function(line, "my_func")
        self.assertIn("inject_my_func", result)

    def test_rename_static(self):
        """Test static function renaming"""
        line = "static int my_func(int x) {"
        result = self.gen._rename_function(line, "my_func")
        self.assertEqual(result, "static int inject_my_func(int x) {")

    def test_no_double_rename(self):
        """Test no double renaming"""
        line = "void inject_my_func(void) {"
        result = self.gen._rename_function(line, "my_func")
        # Already has inject_ prefix, should not rename again
        self.assertEqual(result, "void inject_my_func(void) {")

    def test_rename_function_call(self):
        """Test function call is also renamed (marked functions may call each other)"""
        line = "    my_func();"  # Function call
        result = self.gen._rename_function(line, "my_func")
        # Call should also be renamed
        self.assertIn("inject_my_func", result)


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
