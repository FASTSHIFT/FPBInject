#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch Generator v2 (Marker Based) 模块测试
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from patch_generator import PatchGenerator, check_dependencies, FPB_INJECT_MARKER


class TestFindMarkedFunctions(unittest.TestCase):
    """测试查找 FPB_INJECT 标记"""

    def setUp(self):
        self.gen = PatchGenerator()

    def test_find_single_marker(self):
        """测试查找单个标记"""
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
        """测试查找多个标记"""
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
        """测试带描述的标记"""
        content = """
/* FPB_INJECT: 修复内存泄漏问题 */
void fix_memory_leak(void) {
    free(ptr);
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["fix_memory_leak"])

    def test_no_markers(self):
        """测试没有标记的文件"""
        content = """
void normal_func(void) {
    return;
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, [])

    def test_marker_with_static_inline(self):
        """测试带 static inline 的函数"""
        content = """
/* FPB_INJECT */
static inline int fast_func(int x) {
    return x * 2;
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["fast_func"])

    def test_marker_with_pointer_return(self):
        """测试返回指针的函数"""
        content = """
/* FPB_INJECT */
void * allocate_memory(size_t size) {
    return malloc(size);
}
"""
        marked = self.gen.find_marked_functions(content)
        self.assertEqual(marked, ["allocate_memory"])

    def test_marker_multiline_signature(self):
        """测试多行签名"""
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
    """测试 patch 生成"""

    def setUp(self):
        self.gen = PatchGenerator()

    def test_generate_patch_renames_function(self):
        """测试 patch 生成会重命名标记的函数"""
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

            # 验证函数被重命名
            self.assertIn("inject_target_func", patch_content)
            self.assertEqual(marked, ["target_func"])

            os.unlink(f.name)

    def test_generate_patch_preserves_other_code(self):
        """测试 patch 保留其他代码"""
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

            # 验证其他代码被保留
            self.assertIn("#include <stdio.h>", patch_content)
            self.assertIn("#include <stdlib.h>", patch_content)
            self.assertIn("#define MY_MACRO 42", patch_content)
            self.assertIn("struct MyStruct", patch_content)
            self.assertIn("helper_func", patch_content)
            self.assertIn("inject_target_func", patch_content)

            os.unlink(f.name)

    def test_generate_patch_no_markers(self):
        """测试没有标记时返回空"""
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
        """测试 patch 添加头部注释"""
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
        """测试相对 include 路径转换"""
        # 创建一个临时目录结构
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建头文件
            header_path = os.path.join(tmpdir, "my_header.h")
            with open(header_path, "w") as h:
                h.write("#define TEST 1\n")

            # 创建源文件
            source_path = os.path.join(tmpdir, "source.c")
            content = """
#include "my_header.h"

/* FPB_INJECT */
void func(void) { }
"""
            with open(source_path, "w") as s:
                s.write(content)

            patch_content, _ = self.gen.generate_patch(source_path)

            # 验证路径被转换为绝对路径
            self.assertIn(header_path, patch_content)


class TestRenameFunctions(unittest.TestCase):
    """测试函数重命名"""

    def setUp(self):
        self.gen = PatchGenerator()

    def test_rename_simple(self):
        """测试简单函数重命名"""
        line = "void my_func(void) {"
        result = self.gen._rename_function(line, "my_func")
        self.assertEqual(result, "void inject_my_func(void) {")

    def test_rename_with_pointer(self):
        """测试返回指针的函数重命名"""
        line = "void *my_func(size_t size) {"
        result = self.gen._rename_function(line, "my_func")
        self.assertIn("inject_my_func", result)

    def test_rename_static(self):
        """测试 static 函数重命名"""
        line = "static int my_func(int x) {"
        result = self.gen._rename_function(line, "my_func")
        self.assertEqual(result, "static int inject_my_func(int x) {")

    def test_no_double_rename(self):
        """测试不重复重命名"""
        line = "void inject_my_func(void) {"
        result = self.gen._rename_function(line, "my_func")
        # 已经有 inject_ 前缀，不应再次重命名
        self.assertEqual(result, "void inject_my_func(void) {")

    def test_rename_function_call(self):
        """测试函数调用也会被重命名（因为标记函数可能互相调用）"""
        line = "    my_func();"  # 函数调用
        result = self.gen._rename_function(line, "my_func")
        # 调用也应该被重命名
        self.assertIn("inject_my_func", result)


class TestConvertIncludePath(unittest.TestCase):
    """测试 include 路径转换"""

    def setUp(self):
        self.gen = PatchGenerator()

    def test_convert_relative_path(self):
        """测试转换相对路径"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建头文件
            header = os.path.join(tmpdir, "header.h")
            with open(header, "w") as f:
                f.write("")

            line = '#include "header.h"'
            result = self.gen._convert_include_path(line, tmpdir)
            self.assertIn(header, result)

    def test_keep_system_include(self):
        """测试保留系统 include"""
        line = "#include <stdio.h>"
        result = self.gen._convert_include_path(line, "/tmp")
        self.assertEqual(result, line)

    def test_keep_absolute_path(self):
        """测试保留已有的绝对路径"""
        line = '#include "/abs/path/header.h"'
        result = self.gen._convert_include_path(line, "/tmp")
        self.assertEqual(result, line)

    def test_keep_nonexistent_relative(self):
        """测试保留不存在的相对路径"""
        line = '#include "nonexistent.h"'
        result = self.gen._convert_include_path(line, "/tmp")
        self.assertEqual(result, line)


class TestGeneratePatchFromFile(unittest.TestCase):
    """测试高级 API"""

    def setUp(self):
        self.gen = PatchGenerator()

    def test_file_not_found(self):
        """测试文件不存在"""
        result, marked = self.gen.generate_patch_from_file("/nonexistent/file.c")
        self.assertIsNone(result)
        self.assertEqual(marked, [])

    def test_with_output_dir(self):
        """测试指定输出目录"""
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

            # 验证输出文件名
            self.assertIn("patch_source.c", result_path)


class TestCheckDependencies(unittest.TestCase):
    """测试依赖检查"""

    def test_check_dependencies(self):
        """测试依赖检查"""
        deps = check_dependencies()
        self.assertIn("git", deps)
        # git 应该可用
        self.assertTrue(deps["git"])


class TestMarkerConstant(unittest.TestCase):
    """测试标记常量"""

    def test_marker_value(self):
        """测试标记值"""
        self.assertEqual(FPB_INJECT_MARKER, "FPB_INJECT")


if __name__ == "__main__":
    unittest.main()
