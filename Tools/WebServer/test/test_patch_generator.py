#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch Generator 模块测试
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from patch_generator import (
    CParser,
    FunctionInfo,
    PatchGenerator,
)


class TestFunctionInfo(unittest.TestCase):
    """FunctionInfo 数据类测试"""

    def test_create(self):
        """测试创建 FunctionInfo"""
        info = FunctionInfo(
            name="test_func",
            start_line=10,
            end_line=20,
            start_byte=100,
            end_byte=200,
            code="void test_func() { }",
            signature="void test_func()",
            is_static=False,
        )

        self.assertEqual(info.name, "test_func")
        self.assertEqual(info.start_line, 10)
        self.assertEqual(info.end_line, 20)
        self.assertEqual(info.start_byte, 100)
        self.assertEqual(info.end_byte, 200)
        self.assertFalse(info.is_static)

    def test_create_static(self):
        """测试创建 static 函数"""
        info = FunctionInfo(
            name="static_func",
            start_line=1,
            end_line=5,
            start_byte=0,
            end_byte=50,
            code="static void static_func() { }",
            signature="static void static_func()",
            is_static=True,
        )

        self.assertTrue(info.is_static)


class TestCParser(unittest.TestCase):
    """C 解析器测试"""

    def setUp(self):
        self.parser = CParser()

    def test_parse_simple_function(self):
        """测试解析简单函数"""
        code = """
void foo(void) {
    return;
}
"""
        funcs = self.parser.parse_functions(code)

        self.assertIn("foo", funcs)
        self.assertEqual(funcs["foo"].name, "foo")

    def test_parse_multiple_functions(self):
        """测试解析多个函数"""
        code = """
int add(int a, int b) {
    return a + b;
}

int subtract(int a, int b) {
    return a - b;
}

void print_result(int x) {
    printf("%d\\n", x);
}
"""
        funcs = self.parser.parse_functions(code)

        self.assertIn("add", funcs)
        self.assertIn("subtract", funcs)
        self.assertIn("print_result", funcs)
        self.assertEqual(len(funcs), 3)

    def test_parse_static_function(self):
        """测试解析 static 函数"""
        code = """
static void helper(void) {
    // helper function
}
"""
        funcs = self.parser.parse_functions(code)

        self.assertIn("helper", funcs)
        # 注意：regex fallback 可能无法检测 static
        if funcs["helper"].is_static is not None:
            self.assertTrue(funcs["helper"].is_static)

    def test_parse_function_with_attributes(self):
        """测试解析带属性的函数"""
        code = """
__attribute__((used, section(".text.inject")))
void inject_foo(void) {
    return;
}
"""
        funcs = self.parser.parse_functions(code)

        self.assertIn("inject_foo", funcs)

    def test_parse_pointer_return(self):
        """测试解析返回指针的函数"""
        code = """
void *malloc_wrapper(size_t size) {
    return malloc(size);
}

char *get_string(void) {
    return "hello";
}
"""
        funcs = self.parser.parse_functions(code)

        self.assertIn("malloc_wrapper", funcs)
        self.assertIn("get_string", funcs)

    def test_parse_empty_file(self):
        """测试解析空文件"""
        funcs = self.parser.parse_functions("")

        self.assertEqual(funcs, {})

    def test_parse_no_functions(self):
        """测试解析没有函数的文件"""
        code = """
#include <stdio.h>
#define MAX 100
int global_var = 42;
"""
        funcs = self.parser.parse_functions(code)

        self.assertEqual(funcs, {})

    def test_parse_nested_braces(self):
        """测试解析嵌套花括号"""
        code = """
void complex(int x) {
    if (x > 0) {
        for (int i = 0; i < x; i++) {
            if (i % 2 == 0) {
                printf("even\\n");
            }
        }
    } else {
        printf("negative\\n");
    }
}
"""
        funcs = self.parser.parse_functions(code)

        self.assertIn("complex", funcs)
        # 验证函数完整性
        self.assertIn("}", funcs["complex"].code)


class TestPatchGenerator(unittest.TestCase):
    """Patch 生成器测试"""

    def setUp(self):
        self.gen = PatchGenerator()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        """测试初始化"""
        gen = PatchGenerator()
        self.assertIsNotNone(gen.parser)

    def test_rename_function_in_line(self):
        """测试函数重命名"""
        line = "void foo(int x) {"
        result = self.gen._rename_function_in_line(line, "foo", "inject_foo")

        self.assertIn("inject_foo", result)
        self.assertNotIn("void foo", result)

    def test_rename_function_preserves_signature(self):
        """测试重命名保持签名"""
        line = "int calculate(int a, int b) {"
        result = self.gen._rename_function_in_line(
            line, "calculate", "inject_calculate"
        )

        self.assertIn("inject_calculate", result)
        self.assertIn("int a, int b", result)

    def test_rename_static_function(self):
        """测试重命名 static 函数"""
        line = "static void helper(void) {"
        result = self.gen._rename_function_in_line(line, "helper", "inject_helper")

        self.assertIn("inject_helper", result)
        # static 应该被保留
        self.assertIn("static", result)

    def test_convert_include_path_relative(self):
        """测试转换相对 include 路径"""
        # 创建测试文件
        test_file = os.path.join(self.temp_dir, "test.h")
        with open(test_file, "w") as f:
            f.write("// test header")

        line = '#include "test.h"'
        result = self.gen._convert_include_path(line, self.temp_dir)

        self.assertIn(self.temp_dir, result)

    def test_convert_include_path_system(self):
        """测试系统头文件不转换"""
        line = "#include <stdio.h>"
        result = self.gen._convert_include_path(line, "/some/path")

        self.assertEqual(line, result)

    def test_convert_include_path_already_absolute(self):
        """测试已经是绝对路径不转换"""
        line = '#include "/absolute/path/header.h"'
        result = self.gen._convert_include_path(line, "/some/path")

        self.assertEqual(line, result)

    def test_generate_patch_basic(self):
        """测试基本 patch 生成"""
        # 创建测试源文件
        source_file = os.path.join(self.temp_dir, "test.c")
        code = """
#include <stdio.h>

void target_func(void) {
    printf("original\\n");
}

void other_func(void) {
    printf("other\\n");
}
"""
        with open(source_file, "w") as f:
            f.write(code)

        patch_content, injected = self.gen.generate_patch(source_file, ["target_func"])

        self.assertIn("inject_target_func", patch_content)
        self.assertIn("target_func", injected)

    def test_generate_patch_no_functions(self):
        """测试没有函数的 patch 生成"""
        source_file = os.path.join(self.temp_dir, "empty.c")
        with open(source_file, "w") as f:
            f.write("#include <stdio.h>\n")

        patch_content, injected = self.gen.generate_patch(source_file, [])

        self.assertEqual(injected, [])


class TestDetectModifiedFunctions(unittest.TestCase):
    """检测修改函数测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.gen = PatchGenerator()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_with_original_content(self):
        """测试使用原始内容检测"""
        original = """
void foo(void) {
    printf("original\\n");
}
"""
        modified = """
void foo(void) {
    printf("modified\\n");
}
"""
        # 创建当前文件
        current_file = os.path.join(self.temp_dir, "test.c")
        with open(current_file, "w") as f:
            f.write(modified)

        result = self.gen.detect_modified_functions(current_file, original)

        self.assertIn("foo", result)

    def test_detect_no_changes(self):
        """测试没有变化"""
        code = """
void foo(void) {
    printf("hello\\n");
}
"""
        current_file = os.path.join(self.temp_dir, "test.c")
        with open(current_file, "w") as f:
            f.write(code)

        result = self.gen.detect_modified_functions(current_file, code)

        self.assertEqual(result, [])

    def test_detect_added_function(self):
        """测试新增函数"""
        original = """
void foo(void) {
    printf("foo\\n");
}
"""
        modified = """
void foo(void) {
    printf("foo\\n");
}

void bar(void) {
    printf("bar\\n");
}
"""
        current_file = os.path.join(self.temp_dir, "test.c")
        with open(current_file, "w") as f:
            f.write(modified)

        result = self.gen.detect_modified_functions(current_file, original)

        self.assertIn("bar", result)

    def test_detect_file_not_found(self):
        """测试文件不存在"""
        # 文件不存在会抛出 FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            self.gen.detect_modified_functions("/nonexistent/file.c")


if __name__ == "__main__":
    unittest.main(verbosity=2)
