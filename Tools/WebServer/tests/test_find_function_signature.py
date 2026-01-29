#!/usr/bin/env python3
"""
Unit tests for patch_generator module.
"""

import sys
import os
import unittest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.patch_generator import find_function_signature


class TestFindFunctionSignature(unittest.TestCase):
    """Test cases for find_function_signature function."""

    def test_void_pointer_return_type(self):
        """Test parsing function with void * return type."""
        code = """
void * lv_malloc(size_t size)
{
    return malloc(size);
}
"""
        sig = find_function_signature(code, "lv_malloc")
        self.assertEqual(sig, "void * lv_malloc(size_t size)")

    def test_void_return_type(self):
        """Test parsing function with void return type."""
        code = """
void lv_free(void * data)
{
    free(data);
}
"""
        sig = find_function_signature(code, "lv_free")
        self.assertEqual(sig, "void lv_free(void * data)")

    def test_static_function(self):
        """Test parsing static function."""
        code = """
static int my_func(int a, int b)
{
    return a + b;
}
"""
        sig = find_function_signature(code, "my_func")
        self.assertEqual(sig, "static int my_func(int a, int b)")

    def test_inline_function(self):
        """Test parsing inline function."""
        code = """
inline void fast_func(void)
{
    // do something
}
"""
        sig = find_function_signature(code, "fast_func")
        self.assertEqual(sig, "inline void fast_func(void)")

    def test_static_inline_function(self):
        """Test parsing static inline function."""
        code = """
static inline int add(int x, int y)
{
    return x + y;
}
"""
        sig = find_function_signature(code, "add")
        self.assertEqual(sig, "static inline int add(int x, int y)")

    def test_double_pointer_return(self):
        """Test parsing function with double pointer return type."""
        code = """
char ** get_strings(int count)
{
    return NULL;
}
"""
        sig = find_function_signature(code, "get_strings")
        self.assertEqual(sig, "char ** get_strings(int count)")

    def test_const_pointer_parameter(self):
        """Test parsing function with const pointer parameter."""
        code = """
int strcmp_safe(const char * s1, const char * s2)
{
    return 0;
}
"""
        sig = find_function_signature(code, "strcmp_safe")
        self.assertEqual(sig, "int strcmp_safe(const char * s1, const char * s2)")

    def test_multiline_signature(self):
        """Test parsing multiline function signature."""
        code = """
void *
lv_realloc(void * data, size_t size)
{
    return realloc(data, size);
}
"""
        sig = find_function_signature(code, "lv_realloc")
        self.assertEqual(sig, "void * lv_realloc(void * data, size_t size)")

    def test_macro_prefix(self):
        """Test parsing function with macro prefix (like LV_ATTRIBUTE_FAST_MEM)."""
        code = """
LV_ATTRIBUTE_FAST_MEM void * lv_malloc(size_t size)
{
    return malloc(size);
}
"""
        sig = find_function_signature(code, "lv_malloc")
        self.assertEqual(sig, "LV_ATTRIBUTE_FAST_MEM void * lv_malloc(size_t size)")

    def test_function_declaration(self):
        """Test parsing function declaration (with semicolon)."""
        code = """
extern void * lv_malloc(size_t size);
"""
        sig = find_function_signature(code, "lv_malloc")
        self.assertEqual(sig, "extern void * lv_malloc(size_t size)")

    def test_skip_function_call_assignment(self):
        """Test that function calls with assignment are skipped."""
        code = """
void test_func(void)
{
    void * new = lv_realloc(data_p, new_size);
}

void * lv_realloc(void * data_p, size_t new_size)
{
    return realloc(data_p, new_size);
}
"""
        sig = find_function_signature(code, "lv_realloc")
        self.assertEqual(sig, "void * lv_realloc(void * data_p, size_t new_size)")

    def test_skip_return_statement(self):
        """Test that return statements are skipped."""
        code = """
void * wrapper(size_t size)
{
    return lv_malloc(size);
}

void * lv_malloc(size_t size)
{
    return malloc(size);
}
"""
        sig = find_function_signature(code, "lv_malloc")
        self.assertEqual(sig, "void * lv_malloc(size_t size)")

    def test_typedef_return_type(self):
        """Test parsing function with typedef return type."""
        code = """
lv_obj_t * lv_obj_create(lv_obj_t * parent)
{
    return NULL;
}
"""
        sig = find_function_signature(code, "lv_obj_create")
        self.assertEqual(sig, "lv_obj_t * lv_obj_create(lv_obj_t * parent)")

    def test_unsigned_return_type(self):
        """Test parsing function with unsigned return type."""
        code = """
unsigned int get_count(void)
{
    return 0;
}
"""
        sig = find_function_signature(code, "get_count")
        self.assertEqual(sig, "unsigned int get_count(void)")

    def test_long_long_return_type(self):
        """Test parsing function with long long return type."""
        code = """
long long get_timestamp(void)
{
    return 0;
}
"""
        sig = find_function_signature(code, "get_timestamp")
        self.assertEqual(sig, "long long get_timestamp(void)")

    def test_struct_return_type(self):
        """Test parsing function with struct return type."""
        code = """
struct point get_origin(void)
{
    struct point p = {0, 0};
    return p;
}
"""
        sig = find_function_signature(code, "get_origin")
        self.assertEqual(sig, "struct point get_origin(void)")

    def test_function_not_found(self):
        """Test that None is returned when function is not found."""
        code = """
void other_func(void)
{
}
"""
        sig = find_function_signature(code, "nonexistent_func")
        self.assertIsNone(sig)

    def test_function_pointer_parameter(self):
        """Test parsing function with function pointer parameter."""
        code = """
void register_callback(void (*callback)(int, int))
{
}
"""
        sig = find_function_signature(code, "register_callback")
        self.assertEqual(sig, "void register_callback(void (*callback)(int, int))")

    def test_no_parameters(self):
        """Test parsing function with no parameters (empty parens)."""
        code = """
int get_value()
{
    return 42;
}
"""
        sig = find_function_signature(code, "get_value")
        self.assertEqual(sig, "int get_value()")

    def test_complex_real_world_case(self):
        """Test with realistic LVGL-style code."""
        code = """
/**
 * Allocate a memory dynamically
 * @param size size of the memory to allocate in bytes
 * @return pointer to the allocated memory
 */
void * lv_malloc(size_t size)
{
    LV_ASSERT(size > 0);
    void * p = malloc(size);
    return p;
}
"""
        sig = find_function_signature(code, "lv_malloc")
        self.assertEqual(sig, "void * lv_malloc(size_t size)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
