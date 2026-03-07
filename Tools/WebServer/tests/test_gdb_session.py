#!/usr/bin/env python3

"""Tests for GDB Session manager (core/gdb_session.py)."""

import unittest
from unittest.mock import MagicMock, patch

from core.gdb_session import (
    GDBSession,
    _extract_name_from_decl,
    _split_type_and_name,
    _decl_is_const,
)


class TestDeclIsConst(unittest.TestCase):
    """Test const qualifier detection from C declarations."""

    def test_const_prefix(self):
        self.assertTrue(_decl_is_const("const lv_font_t lv_font_montserrat_14"))

    def test_static_const(self):
        self.assertTrue(_decl_is_const("static const int foo"))

    def test_const_pointer(self):
        self.assertTrue(_decl_is_const("const char *baz"))

    def test_no_const(self):
        self.assertFalse(_decl_is_const("int bar"))

    def test_no_const_static(self):
        self.assertFalse(_decl_is_const("static int bar"))

    def test_empty(self):
        self.assertFalse(_decl_is_const(""))


class TestExtractNameFromDecl(unittest.TestCase):
    """Test C declaration name extraction."""

    def test_function_decl(self):
        self.assertEqual(_extract_name_from_decl("void foo(int, int)"), "foo")

    def test_function_with_return_type(self):
        self.assertEqual(_extract_name_from_decl("int bar(void)"), "bar")

    def test_static_function(self):
        self.assertEqual(_extract_name_from_decl("static void baz(int x)"), "baz")

    def test_pointer_return(self):
        self.assertEqual(_extract_name_from_decl("char *get_name(void)"), "get_name")

    def test_variable_decl(self):
        self.assertEqual(_extract_name_from_decl("int counter"), "counter")

    def test_static_variable(self):
        self.assertEqual(_extract_name_from_decl("static int bar"), "bar")

    def test_const_variable(self):
        self.assertEqual(_extract_name_from_decl("const char *baz"), "baz")

    def test_pointer_variable(self):
        self.assertEqual(_extract_name_from_decl("int *ptr"), "ptr")

    def test_type_keyword_only(self):
        self.assertIsNone(_extract_name_from_decl("int"))

    def test_empty(self):
        self.assertIsNone(_extract_name_from_decl(""))


class TestSplitTypeAndName(unittest.TestCase):
    """Test C declaration splitting into type and name."""

    def test_simple(self):
        self.assertEqual(_split_type_and_name("int x"), ("int", "x"))

    def test_pointer(self):
        t, n = _split_type_and_name("int *ptr")
        self.assertEqual(n, "ptr")
        self.assertIn("int", t)
        self.assertIn("*", t)

    def test_array(self):
        t, n = _split_type_and_name("char buf[64]")
        self.assertEqual(n, "buf")
        self.assertIn("[64]", t)

    def test_struct_member(self):
        self.assertEqual(_split_type_and_name("struct foo bar"), ("struct foo", "bar"))

    def test_single_word(self):
        t, n = _split_type_and_name("unknown")
        # Single word - returned as-is
        self.assertIsNotNone(t)

    def test_bitfield(self):
        t, n = _split_type_and_name("unsigned int flags : 3")
        self.assertEqual(n, "flags")

    def test_function_pointer(self):
        """Function pointer: void (*name)(args)"""
        t, n = _split_type_and_name(
            "void (*draw_ctx_init)(_lv_disp_t *, lv_draw_ctx_t *)"
        )
        self.assertEqual(n, "draw_ctx_init")
        self.assertIn("void", t)
        self.assertIn("(*)", t)

    def test_function_pointer_with_return(self):
        """Function pointer with non-void return."""
        t, n = _split_type_and_name("int (*callback)(int, int)")
        self.assertEqual(n, "callback")
        self.assertIn("int", t)
        self.assertIn("(*)", t)

    def test_function_pointer_no_args(self):
        """Function pointer with void args."""
        t, n = _split_type_and_name("void (*handler)(void)")
        self.assertEqual(n, "handler")
        self.assertIn("void", t)

    def test_function_pointer_single_arg(self):
        """Function pointer: void (*wait_cb)(_lv_disp_t *)"""
        t, n = _split_type_and_name("void (*wait_cb)(_lv_disp_t *)")
        self.assertEqual(n, "wait_cb")
        self.assertIn("(*)", t)


class TestGDBSessionParseHelpers(unittest.TestCase):
    """Test GDB output parsing static methods."""

    def test_parse_address_from_info(self):
        output = 'Symbol "foo" is at address 0x20001234.'
        addr = GDBSession._parse_address_from_info(output)
        self.assertEqual(addr, 0x20001234)

    def test_parse_address_static(self):
        output = 'Symbol "bar" is static storage at address 0x8001000.'
        addr = GDBSession._parse_address_from_info(output)
        self.assertEqual(addr, 0x8001000)

    def test_parse_address_not_found(self):
        output = 'No symbol "baz" in current context.'
        addr = GDBSession._parse_address_from_info(output)
        self.assertIsNone(addr)

    def test_parse_info_symbol(self):
        output = "foo + 0 in section .text"
        results = GDBSession._parse_info_symbol(output, 0x08001000)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "foo")
        self.assertEqual(results[0]["type"], "function")
        self.assertEqual(results[0]["section"], ".text")

    def test_parse_info_symbol_with_offset(self):
        output = "bar + 16 in section .data"
        results = GDBSession._parse_info_symbol(output, 0x20001010)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "bar")
        self.assertEqual(results[0]["addr"], "0x20001000")

    def test_parse_info_symbol_rodata(self):
        output = "my_const + 0 in section .rodata"
        results = GDBSession._parse_info_symbol(output, 0x08002000)
        self.assertEqual(results[0]["type"], "const")

    def test_parse_info_symbol_no_match(self):
        output = "No symbol matches 0x12345678."
        results = GDBSession._parse_info_symbol(output, 0x12345678)
        self.assertEqual(len(results), 0)

    def test_parse_info_functions_non_debug(self):
        output = """Non-debugging symbols:
0x08001000  foo
0x08001100  bar"""
        results = GDBSession._parse_info_functions(output, "function")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "foo")
        self.assertEqual(results[0]["addr"], "0x08001000")
        self.assertEqual(results[1]["name"], "bar")

    def test_parse_info_functions_debug(self):
        output = """File src/main.c:
42:	void foo(int);
100:	static int bar;"""
        results = GDBSession._parse_info_functions(output, "function")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "foo")
        self.assertEqual(results[1]["name"], "bar")

    def test_parse_info_functions_empty(self):
        results = GDBSession._parse_info_functions("", "function")
        self.assertEqual(len(results), 0)

    def test_parse_info_functions_skip_headers(self):
        output = """All defined functions:

File src/main.c:
42:	void foo(int);"""
        results = GDBSession._parse_info_functions(output, "function")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "foo")

    def test_parse_ptype_output(self):
        output = """type = struct point {
/*    0      |     4 */    int x;
/*    4      |     4 */    int y;
/*    8      |     8 */    double z;

                           /* total size (bytes):   16 */
                         }"""
        members = GDBSession._parse_ptype_output(output)
        self.assertIsNotNone(members)
        self.assertEqual(len(members), 3)
        self.assertEqual(members[0]["name"], "x")
        self.assertEqual(members[0]["offset"], 0)
        self.assertEqual(members[0]["size"], 4)
        self.assertIn("int", members[0]["type_name"])
        self.assertEqual(members[1]["name"], "y")
        self.assertEqual(members[1]["offset"], 4)
        self.assertEqual(members[2]["name"], "z")
        self.assertEqual(members[2]["offset"], 8)
        self.assertEqual(members[2]["size"], 8)

    def test_parse_ptype_output_not_struct(self):
        output = "type = int"
        members = GDBSession._parse_ptype_output(output)
        self.assertIsNone(members)

    def test_parse_ptype_output_with_pointer(self):
        output = """type = struct node {
/*    0      |     4 */    int value;
/*    4      |     4 */    struct node *next;

                           /* total size (bytes):    8 */
                         }"""
        members = GDBSession._parse_ptype_output(output)
        self.assertIsNotNone(members)
        self.assertEqual(len(members), 2)
        self.assertEqual(members[1]["name"], "next")

    def test_parse_ptype_output_function_pointer(self):
        """Function pointer members: void (*name)(args) — from real lv_disp_t."""
        output = """type = struct _lv_disp_t {
/*      0      |       4 */    lv_coord_t hor_res;
/*      4      |       4 */    lv_coord_t ver_res;
/*     44      |       4 */    lv_disp_flush_cb_t flush_cb;
/*    612      |       4 */    lv_draw_ctx_t *draw_ctx;
/*    616      |       4 */    void (*draw_ctx_init)(_lv_disp_t *, lv_draw_ctx_t *);
/*    620      |       4 */    void (*draw_ctx_deinit)(_lv_disp_t *, lv_draw_ctx_t *);
/*    624      |       4 */    size_t draw_ctx_size;
/*    696      |       4 */    void (*wait_cb)(_lv_disp_t *);

                               /* total size (bytes):  704 */
                             }"""
        members = GDBSession._parse_ptype_output(output)
        self.assertIsNotNone(members)
        names = {m["name"] for m in members}
        # Function pointer members must be parsed correctly
        self.assertIn("draw_ctx_init", names)
        self.assertIn("draw_ctx_deinit", names)
        self.assertIn("wait_cb", names)
        # Must NOT have ")" as a name
        self.assertNotIn(")", names)
        # Regular members still work
        self.assertIn("hor_res", names)
        self.assertIn("draw_ctx", names)
        self.assertIn("draw_ctx_size", names)
        # Check offsets
        init_member = next(m for m in members if m["name"] == "draw_ctx_init")
        self.assertEqual(init_member["offset"], 616)
        self.assertEqual(init_member["size"], 4)
        # Check type contains function pointer syntax
        self.assertIn("(*)", init_member["type_name"])

    def test_extract_console_output(self):
        responses = [
            {"type": "console", "payload": "hello world\n", "message": None},
            {"type": "console", "payload": "second line\n", "message": None},
            {"type": "result", "payload": None, "message": "done"},
        ]
        output = GDBSession._extract_console_output(responses)
        self.assertIn("hello world", output)
        self.assertIn("second line", output)

    def test_extract_console_output_escaped(self):
        responses = [
            {"type": "console", "payload": "type = struct foo {\n", "message": None},
            {"type": "console", "payload": "  int x;\n", "message": None},
            {"type": "console", "payload": "}\n", "message": None},
            {"type": "result", "payload": None, "message": "done"},
        ]
        output = GDBSession._extract_console_output(responses)
        self.assertIn("struct foo", output)
        self.assertIn("int x", output)

    def test_extract_console_output_empty(self):
        responses = [
            {"type": "result", "payload": None, "message": "done"},
        ]
        output = GDBSession._extract_console_output(responses)
        self.assertEqual(output, "")


class TestGDBSessionLifecycle(unittest.TestCase):
    """Test GDB session start/stop (mocked subprocess)."""

    def test_is_alive_not_started(self):
        session = GDBSession("/fake/elf")
        self.assertFalse(session.is_alive)

    def test_elf_path_property(self):
        session = GDBSession("/path/to/elf")
        self.assertEqual(session.elf_path, "/path/to/elf")

    @patch("core.gdb_session.subprocess.Popen")
    @patch("core.gdb_session.os.path.exists", return_value=True)
    def test_start_gdb_not_found(self, mock_exists, mock_popen):
        mock_popen.side_effect = FileNotFoundError("gdb not found")
        session = GDBSession("/fake/elf")
        result = session.start(rsp_port=3333)
        self.assertFalse(result)
        self.assertFalse(session.is_alive)

    def test_stop_when_not_started(self):
        session = GDBSession("/fake/elf")
        # Should not raise
        session.stop()
        self.assertFalse(session.is_alive)

    def test_execute_when_not_alive(self):
        session = GDBSession("/fake/elf")
        result = session.execute("info address foo")
        self.assertIsNone(result)

    def test_lookup_symbol_when_not_alive(self):
        session = GDBSession("/fake/elf")
        result = session.lookup_symbol("foo")
        self.assertIsNone(result)

    def test_search_symbols_when_not_alive(self):
        session = GDBSession("/fake/elf")
        results, total = session.search_symbols("foo")
        self.assertEqual(results, [])
        self.assertEqual(total, 0)

    def test_get_struct_layout_when_not_alive(self):
        session = GDBSession("/fake/elf")
        result = session.get_struct_layout("my_var")
        self.assertIsNone(result)

    def test_get_symbols_when_not_alive(self):
        session = GDBSession("/fake/elf")
        result = session.get_symbols()
        self.assertEqual(result, {})

    @patch("core.gdb_session.os.path.exists", return_value=False)
    def test_start_elf_not_found(self, mock_exists):
        session = GDBSession("/nonexistent/elf")
        result = session.start(rsp_port=3333)
        self.assertFalse(result)

    def test_start_already_alive(self):
        session = GDBSession("/fake/elf")
        session._alive = True
        session._proc = MagicMock()
        session._proc.poll.return_value = None
        result = session.start(rsp_port=3333)
        self.assertTrue(result)

    @patch("core.gdb_session.subprocess.Popen")
    @patch("core.gdb_session.os.path.exists", return_value=True)
    def test_start_file_cmd_fails(self, mock_exists, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        session = GDBSession("/fake/elf")
        # _write_mi returns None → file command fails → start returns False
        with patch.object(session, "_write_mi", return_value=None), patch(
            "core.gdb_session.IoManager"
        ):
            result = session.start(rsp_port=3333)
        self.assertFalse(result)

    @patch("core.gdb_session.subprocess.Popen")
    @patch("core.gdb_session.os.path.exists", return_value=True)
    def test_start_generic_exception(self, mock_exists, mock_popen):
        mock_popen.side_effect = RuntimeError("unexpected")
        session = GDBSession("/fake/elf")
        result = session.start(rsp_port=3333)
        self.assertFalse(result)

    def test_stop_with_proc(self):
        session = GDBSession("/fake/elf")
        session._alive = True
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        session._proc = mock_proc
        session.stop()
        self.assertFalse(session._alive)
        self.assertIsNone(session._proc)
        mock_proc.terminate.assert_called_once()

    def test_stop_proc_terminate_fails(self):
        session = GDBSession("/fake/elf")
        session._alive = True
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdin.write.side_effect = BrokenPipeError()
        mock_proc.terminate.side_effect = OSError()
        mock_proc.kill.return_value = None
        session._proc = mock_proc
        session.stop()
        self.assertIsNone(session._proc)

    def test_execute_delegates_to_cli(self):
        session = GDBSession("/fake/elf")
        session._alive = True
        session._proc = MagicMock()
        session._proc.poll.return_value = None
        with patch.object(session, "_execute_cli", return_value="output") as mock_cli:
            result = session.execute("info address foo")
            self.assertEqual(result, "output")
            mock_cli.assert_called_once_with("info address foo", 10.0)


class TestGDBSessionLookupImpl(unittest.TestCase):
    """Test lookup_symbol internal logic with mocked execute."""

    def setUp(self):
        self.session = GDBSession("/fake/elf")
        self.session._alive = True
        self.session._proc = MagicMock()
        self.session._proc.poll.return_value = None  # process alive

    def test_lookup_found(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                # info address
                'Symbol "my_var" is static storage at address 0x20001000.',
                # sizeof
                "$1 = 16",
                # info symbol (section fallback)
                "my_var in section .data",
                # ptype (non-const)
                "type = int",
                # whatis (pointer detection)
                "type = int",
            ]
            result = self.session.lookup_symbol("my_var")
            self.assertIsNotNone(result)
            self.assertEqual(result["addr"], 0x20001000)
            self.assertEqual(result["size"], 16)
            self.assertEqual(result["type"], "variable")
            self.assertEqual(result["section"], ".data")

    def test_lookup_function(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                'Symbol "main" is a function at address 0x08001000.',
                "$1 = 128",
            ]
            result = self.session.lookup_symbol("main")
            self.assertIsNotNone(result)
            self.assertEqual(result["type"], "function")
            self.assertEqual(result["section"], ".text")

    def test_lookup_not_found(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.return_value = 'No symbol "xyz" in current context.'
            result = self.session.lookup_symbol("xyz")
            self.assertIsNone(result)

    def test_lookup_const(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                'Symbol "my_const" is static storage at address 0x08002000 in .rodata.',
                "$1 = 4",
                # whatis (pointer detection)
                "type = const uint32_t",
            ]
            result = self.session.lookup_symbol("my_const")
            self.assertIsNotNone(result)
            self.assertEqual(result["type"], "const")

    def test_lookup_const_via_ptype(self):
        """Const detected via ptype when section is not .rodata."""
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                'Symbol "my_const" is static storage at address 0x08002000.',
                "$1 = 4",
                # info symbol (section fallback)
                "my_const in section .data",
                # ptype returns const qualifier
                "type = const lv_font_t",
                # whatis (pointer detection) — const already detected, but whatis still called
                "type = const lv_font_t",
            ]
            result = self.session.lookup_symbol("my_const")
            self.assertIsNotNone(result)
            self.assertEqual(result["type"], "const")

    def test_lookup_no_address_parsed(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.return_value = 'Symbol "foo" is optimized out.'
            result = self.session.lookup_symbol("foo")
            self.assertIsNone(result)

    def test_lookup_output_none(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.return_value = None
            result = self.session.lookup_symbol("foo")
            self.assertIsNone(result)

    def test_lookup_bss_section(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                'Symbol "bss_var" is static storage at address 0x20002000 in .bss.',
                "$1 = 4",
                # ptype (non-const)
                "type = int",
                # whatis (pointer detection)
                "type = int",
            ]
            result = self.session.lookup_symbol("bss_var")
            self.assertIsNotNone(result)
            self.assertEqual(result["section"], ".bss")
            self.assertEqual(result["type"], "variable")

    def test_lookup_data_section(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                'Symbol "data_var" is static storage at address 0x20003000 in .data.',
                "$1 = 8",
                # ptype (non-const)
                "type = int",
                # whatis (pointer detection)
                "type = int",
            ]
            result = self.session.lookup_symbol("data_var")
            self.assertIsNotNone(result)
            self.assertEqual(result["section"], ".data")

    def test_sizeof_no_match(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                'Symbol "x" is at address 0x1000.',
                "No symbol in current context",  # sizeof fails
                "No symbol matches",  # _resolve_linker_name (info symbol)
                # info symbol (section fallback) — same addr, may find section
                "x in section .bss",
                # ptype (non-const)
                "type = int",
                # whatis (pointer detection)
                "type = int",
            ]
            result = self.session.lookup_symbol("x")
            self.assertIsNotNone(result)
            self.assertEqual(result["size"], 0)
            self.assertEqual(result["section"], ".bss")

    def test_sizeof_output_none(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                'Symbol "x" is at address 0x1000.',
                None,  # sizeof returns None
                "No symbol matches",  # _resolve_linker_name (info symbol)
                # info symbol (section fallback)
                "x in section .bss",
                # ptype (non-const)
                "type = int",
                # whatis (pointer detection)
                "type = int",
            ]
            result = self.session.lookup_symbol("x")
            self.assertIsNotNone(result)
            self.assertEqual(result["size"], 0)


class TestGDBSessionStructLayout(unittest.TestCase):
    """Test get_struct_layout with mocked execute."""

    def setUp(self):
        self.session = GDBSession("/fake/elf")
        self.session._alive = True
        self.session._proc = MagicMock()
        self.session._proc.poll.return_value = None

    def test_struct_layout(self):
        ptype_output = """type = struct point {
/*    0      |     4 */    int x;
/*    4      |     4 */    int y;

                           /* total size (bytes):    8 */
                         }"""
        with patch.object(self.session, "_execute_cli", return_value=ptype_output):
            result = self.session.get_struct_layout("my_point")
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["name"], "x")
            self.assertEqual(result[1]["name"], "y")

    def test_not_a_struct(self):
        with patch.object(self.session, "_execute_cli", return_value="type = int"):
            result = self.session.get_struct_layout("my_int")
            self.assertIsNone(result)

    def test_execute_returns_none(self):
        with patch.object(self.session, "_execute_cli", return_value=None):
            result = self.session.get_struct_layout("my_var")
            self.assertIsNone(result)

    def test_union_layout(self):
        ptype_output = """type = union data {
/*                 4 */    int i;
/*                 4 */    float f;

                           /* total size (bytes):    4 */
                         }"""
        with patch.object(self.session, "_execute_cli", return_value=ptype_output):
            result = self.session.get_struct_layout("my_union")
            # union doesn't have offset|size format, so may return None
            # The important thing is it doesn't crash
            self.assertTrue(result is None or isinstance(result, list))


class TestGDBSessionSearchImpl(unittest.TestCase):
    """Test search_symbols internal logic with mocked execute."""

    def setUp(self):
        self.session = GDBSession("/fake/elf")
        self.session._alive = True
        self.session._proc = MagicMock()
        self.session._proc.poll.return_value = None

    def test_search_by_name(self):
        func_output = """Non-debugging symbols:
0x08001000  foo_init
0x08001100  foo_deinit"""
        var_output = """Non-debugging symbols:
0x20001000  foo_counter"""
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [func_output, var_output]
            results, total = self.session.search_symbols("foo")
            self.assertEqual(total, 3)
            names = [r["name"] for r in results]
            self.assertIn("foo_init", names)
            self.assertIn("foo_counter", names)

    def test_search_by_address(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.return_value = "my_func + 0 in section .text"
            results, total = self.session.search_symbols("0x08001000")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["name"], "my_func")

    def test_search_by_hex_no_prefix(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.return_value = "my_func + 0 in section .text"
            results, total = self.session.search_symbols("08001000")
            self.assertEqual(len(results), 1)

    def test_search_address_no_symbol(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.return_value = "No symbol matches 0x12345678."
            results, total = self.session.search_symbols("0x12345678")
            self.assertEqual(results, [])

    def test_search_address_value_error(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.return_value = ""
            results, total = self.session.search_symbols("0xZZZZ")
            self.assertEqual(results, [])

    def test_search_empty_results(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.return_value = ""
            results, total = self.session.search_symbols("nonexistent")
            self.assertEqual(results, [])
            self.assertEqual(total, 0)

    def test_search_deduplicates(self):
        # Same symbol appears in both functions and variables output
        output = """Non-debugging symbols:
0x08001000  foo"""
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [output, output]
            results, total = self.session.search_symbols("foo")
            self.assertEqual(total, 1)  # deduplicated

    def test_search_with_limit(self):
        output = """Non-debugging symbols:
0x08001000  aaa
0x08001100  bbb
0x08001200  ccc"""
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [output, ""]
            results, total = self.session.search_symbols("", limit=2)
            self.assertLessEqual(len(results), 2)

    def test_search_none_output(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.return_value = None
            results, total = self.session.search_symbols("foo")
            self.assertEqual(results, [])


class TestGDBSessionGetSymbolsImpl(unittest.TestCase):
    """Test get_symbols internal logic with mocked execute."""

    def setUp(self):
        self.session = GDBSession("/fake/elf")
        self.session._alive = True
        self.session._proc = MagicMock()
        self.session._proc.poll.return_value = None

    def test_get_symbols(self):
        func_output = """Non-debugging symbols:
0x08001000  main
0x08001100  init"""
        var_output = """Non-debugging symbols:
0x20001000  counter"""
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [func_output, var_output]
            symbols = self.session.get_symbols()
            self.assertIn("main", symbols)
            self.assertIn("counter", symbols)
            self.assertEqual(symbols["main"]["type"], "function")
            self.assertEqual(symbols["counter"]["type"], "variable")

    def test_get_symbols_no_output(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.return_value = None
            symbols = self.session.get_symbols()
            self.assertEqual(symbols, {})

    def test_get_symbols_dedup_vars(self):
        """Variables already in functions dict should not be overwritten."""
        func_output = """Non-debugging symbols:
0x08001000  foo"""
        var_output = """Non-debugging symbols:
0x20001000  foo"""
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [func_output, var_output]
            symbols = self.session.get_symbols()
            # foo from functions should win (first)
            self.assertEqual(symbols["foo"]["type"], "function")


class TestGDBSessionMICommunication(unittest.TestCase):
    """Test GDB/MI communication methods (pygdbmi-based)."""

    def setUp(self):
        self.session = GDBSession("/fake/elf")
        self.session._proc = MagicMock()
        self.session._proc.stdin = MagicMock()
        self.session._proc.stdout = MagicMock()
        self.session._io = MagicMock()

    def test_write_mi_no_io(self):
        self.session._io = None
        result = self.session._write_mi("test")
        self.assertIsNone(result)

    def test_write_mi_exception(self):
        self.session._io.write.side_effect = BrokenPipeError()
        result = self.session._write_mi("test")
        self.assertIsNone(result)

    def test_write_mi_empty_response(self):
        self.session._io.write.return_value = []
        result = self.session._write_mi("test")
        self.assertIsNone(result)

    def test_write_mi_error_response(self):
        self.session._io.write.return_value = [
            {"type": "result", "message": "error", "payload": {"msg": "No symbol"}}
        ]
        result = self.session._write_mi("test")
        self.assertIsNotNone(result)  # Still returns responses for caller inspection

    def test_execute_cli_returns_none_on_mi_failure(self):
        with patch.object(self.session, "_write_mi", return_value=None):
            result = self.session._execute_cli("test")
            self.assertIsNone(result)

    def test_execute_cli_extracts_output(self):
        responses = [
            {"type": "console", "payload": "hello\n", "message": None},
            {"type": "result", "payload": None, "message": "done"},
        ]
        with patch.object(self.session, "_write_mi", return_value=responses):
            result = self.session._execute_cli("test")
            self.assertIn("hello", result)

    def test_get_symbol_section_text(self):
        self.assertEqual(GDBSession._get_symbol_section("in .text section"), ".text")

    def test_get_symbol_section_function(self):
        self.assertEqual(GDBSession._get_symbol_section("is a function"), ".text")

    def test_get_symbol_section_rodata(self):
        self.assertEqual(GDBSession._get_symbol_section("in .rodata"), ".rodata")

    def test_get_symbol_section_bss(self):
        self.assertEqual(GDBSession._get_symbol_section("in .bss"), ".bss")

    def test_get_symbol_section_data(self):
        self.assertEqual(GDBSession._get_symbol_section("in .data"), ".data")

    def test_get_symbol_section_unknown(self):
        self.assertEqual(GDBSession._get_symbol_section("something else"), "")


class TestParseStructValuesImpl(unittest.TestCase):
    """Test _parse_struct_values_impl with mocked GDB commands."""

    def setUp(self):
        self.session = GDBSession("/fake/elf")
        self.session._alive = True
        self.session._proc = MagicMock()
        self.session._proc.poll.return_value = None

    def test_json_print_direct_symbol(self):
        """First tries json-print with symbol name directly."""
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                # json-print "my_var" 2 — direct symbol name
                '{"x": 1, "y": 2}',
            ]
            result = self.session._parse_struct_values_impl("my_var", 0x20001000)
            self.assertIsNotNone(result)
            self.assertEqual(result["x"], 1)
            self.assertEqual(result["y"], 2)
            calls = [c[0][0] for c in mock_cli.call_args_list]
            self.assertIn("json-print", calls[0])
            self.assertIn("my_var", calls[0])

    def test_json_print_fallback_to_pointer_cast(self):
        """Falls back to pointer cast when direct symbol fails."""
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                # json-print "disp_ptr" — fails (e.g. pointer type)
                '{"_kind": "error", "_msg": "not a struct"}',
                # whatis disp_ptr
                "type = lv_disp_t *",
                # json-print "*((struct lv_disp_t *)0x20003000)" 2
                '{"width": 240, "height": 320}',
            ]
            result = self.session._parse_struct_values_impl("disp_ptr", 0x20003000)
            self.assertIsNotNone(result)
            self.assertEqual(result["width"], 240)

    def test_json_print_fallback_no_struct_prefix(self):
        """Falls back to type without 'struct' prefix."""
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                # json-print "drv" — fails
                '{"_kind": "error", "_msg": "not found"}',
                # whatis drv
                "type = lv_disp_drv_t",
                # json-print "*((struct lv_disp_drv_t *)0x20002000)" — fails
                '{"_kind": "error", "_msg": "No struct type named lv_disp_drv_t."}',
                # json-print "*((lv_disp_drv_t *)0x20002000)" — works
                '{"hor_res": 240}',
            ]
            result = self.session._parse_struct_values_impl("drv", 0x20002000)
            self.assertIsNotNone(result)
            self.assertEqual(result["hor_res"], 240)

    def test_json_print_returns_none_on_all_errors(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                # json-print "bad" — fails
                '{"_kind": "error", "_msg": "err0"}',
                # whatis bad
                "type = bad_type",
                # json-print "*((struct bad_type *)0x20001000)" — fails
                '{"_kind": "error", "_msg": "err1"}',
                # json-print "*((bad_type *)0x20001000)" — fails
                '{"_kind": "error", "_msg": "err2"}',
            ]
            result = self.session._parse_struct_values_impl("bad", 0x20001000)
            self.assertIsNone(result)

    def test_returns_none_when_all_fields_error(self):
        """Returns None when json-print returns all error fields (no target)."""
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                # json-print "my_var" — all fields are errors
                '{"x": {"_kind": "error", "_msg": "Cannot access memory"}, '
                '"y": {"_kind": "error", "_msg": "Cannot access memory"}}',
                # whatis my_var
                "type = my_struct_t",
                # pointer cast also fails
                '{"_kind": "error", "_msg": "err"}',
                '{"_kind": "error", "_msg": "err"}',
            ]
            result = self.session._parse_struct_values_impl("my_var", 0x20001000)
            self.assertIsNone(result)

    def test_returns_none_when_direct_fails_and_whatis_fails(self):
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                # json-print "bad_sym" — fails
                None,
                # whatis bad_sym — also fails
                None,
            ]
            result = self.session._parse_struct_values_impl("bad_sym", 0x20001000)
            self.assertIsNone(result)

    def test_returns_none_when_json_not_struct(self):
        """Returns None when json-print output is not a struct."""
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                # json-print "int_var" — not JSON object
                "42",
                # whatis int_var
                "type = int",
                # pointer cast also not JSON
                "42",
                "42",
            ]
            result = self.session._parse_struct_values_impl("int_var", 0x20001000)
            self.assertIsNone(result)

    def test_json_print_handles_complex_struct(self):
        """Handles nested structs, arrays, func ptrs in JSON output."""
        json_output = (
            '{"hor_res": 240, "flush_cb": {"_kind": "func_ptr", '
            '"_addr": "0x08001234", "_sig": "void (*)(int)"}, '
            '"mode": {"_kind": "enum", "_val": 0, "_name": "MODE_PARTIAL"}, '
            '"pos": {"x": 10, "y": 20}, "data": [1, 2, 3]}'
        )
        with patch.object(self.session, "_execute_cli") as mock_cli:
            mock_cli.side_effect = [
                # json-print "obj" — works directly
                json_output,
            ]
            result = self.session._parse_struct_values_impl("obj", 0x20001000)
            self.assertIsNotNone(result)
            self.assertEqual(result["hor_res"], 240)
            self.assertEqual(result["flush_cb"]["_kind"], "func_ptr")
            self.assertEqual(result["flush_cb"]["_addr"], "0x08001234")
            self.assertEqual(result["mode"]["_name"], "MODE_PARTIAL")
            self.assertEqual(result["pos"]["x"], 10)
            self.assertEqual(result["data"], [1, 2, 3])


class TestMIQuoteEscaping(unittest.TestCase):
    """Test that _write_mi properly escapes double quotes in commands."""

    def setUp(self):
        self.session = GDBSession("/fake/elf")
        self.session._proc = MagicMock()
        self.session._io = MagicMock()

    def test_quotes_escaped_in_mi_command(self):
        """Inner double quotes are escaped for MI transport."""
        self.session._io.write.return_value = [
            {"type": "result", "message": "done", "payload": None}
        ]
        self.session._write_mi('json-print "*((struct foo *)0x1000)" 2')
        call_args = self.session._io.write.call_args
        mi_cmd = call_args[0][0]
        # The inner quotes should be escaped as \"
        self.assertIn('\\"', mi_cmd)
        # Verify the full MI command structure
        expected = (
            '-interpreter-exec console "json-print \\"*((struct foo *)0x1000)\\" 2"'
        )
        self.assertEqual(mi_cmd, expected)

    def test_no_quotes_no_escaping(self):
        """Commands without quotes pass through unchanged."""
        self.session._io.write.return_value = [
            {"type": "result", "message": "done", "payload": None}
        ]
        self.session._write_mi("info address foo")
        call_args = self.session._io.write.call_args
        mi_cmd = call_args[0][0]
        self.assertEqual(mi_cmd, '-interpreter-exec console "info address foo"')


if __name__ == "__main__":
    unittest.main()
