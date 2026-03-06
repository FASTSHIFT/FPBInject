#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ELF utilities tests
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import elf_utils  # noqa: E402
from elftools.elf.sections import SymbolTableSection  # noqa: E402


class TestGetToolPath(unittest.TestCase):
    """get_tool_path function tests"""

    def test_no_toolchain_path(self):
        """Test without toolchain path"""
        result = elf_utils.get_tool_path("arm-none-eabi-gcc")
        self.assertEqual(result, "arm-none-eabi-gcc")

    def test_with_toolchain_path(self):
        """Test with toolchain path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_path = os.path.join(tmpdir, "arm-none-eabi-gcc")
            with open(tool_path, "w") as f:
                f.write("#!/bin/bash\n")

            result = elf_utils.get_tool_path("arm-none-eabi-gcc", tmpdir)
            self.assertEqual(result, tool_path)

    def test_tool_not_in_toolchain(self):
        """Test when tool not found in toolchain path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = elf_utils.get_tool_path("arm-none-eabi-gcc", tmpdir)
            self.assertEqual(result, "arm-none-eabi-gcc")


class TestGetSubprocessEnv(unittest.TestCase):
    """get_subprocess_env function tests"""

    def test_no_toolchain_path(self):
        """Test without toolchain path"""
        env = elf_utils.get_subprocess_env()
        self.assertIn("PATH", env)

    def test_with_toolchain_path(self):
        """Test with toolchain path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = elf_utils.get_subprocess_env(tmpdir)
            self.assertTrue(env["PATH"].startswith(tmpdir + ":"))

    def test_invalid_toolchain_path(self):
        """Test with invalid toolchain path"""
        env = elf_utils.get_subprocess_env("/nonexistent/path")
        # Should not modify PATH for non-existent directory
        self.assertNotIn("/nonexistent/path", env["PATH"])


class TestGetElfBuildTime(unittest.TestCase):
    """get_elf_build_time function tests"""

    def test_no_elf_path(self):
        """Test with no ELF path"""
        result = elf_utils.get_elf_build_time("")
        self.assertIsNone(result)

    def test_nonexistent_elf(self):
        """Test with nonexistent ELF"""
        result = elf_utils.get_elf_build_time("/nonexistent/file.elf")
        self.assertIsNone(result)

    @patch("subprocess.run")
    def test_strings_failure(self, mock_run):
        """Test when strings command fails"""
        mock_run.return_value = Mock(returncode=1, stdout="")

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.get_elf_build_time(elf_path)
            self.assertIsNone(result)
        finally:
            os.unlink(elf_path)

    @patch("subprocess.run")
    def test_build_time_found_with_marker(self, mock_run):
        """Test finding build time with FPBInject marker"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="FPBInject v1.0\nJan 15 2025\n10:30:45\nother data",
        )

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.get_elf_build_time(elf_path)
            self.assertIsNotNone(result)
            self.assertIn("Jan", result)
            self.assertIn("2025", result)
        finally:
            os.unlink(elf_path)

    @patch("subprocess.run")
    def test_build_time_found_consecutive(self, mock_run):
        """Test finding build time with consecutive date/time strings"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="some data\nFeb 20 2025\n14:22:33\nmore data",
        )

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.get_elf_build_time(elf_path)
            self.assertIsNotNone(result)
            self.assertIn("Feb", result)
        finally:
            os.unlink(elf_path)


class TestClassifySymbol(unittest.TestCase):
    """_classify_symbol function tests"""

    def test_function_type(self):
        self.assertEqual(elf_utils._classify_symbol("STT_FUNC", ".text"), "function")

    def test_variable_data(self):
        self.assertEqual(elf_utils._classify_symbol("STT_OBJECT", ".data"), "variable")

    def test_variable_bss(self):
        self.assertEqual(elf_utils._classify_symbol("STT_OBJECT", ".bss"), "variable")

    def test_const_rodata(self):
        self.assertEqual(elf_utils._classify_symbol("STT_OBJECT", ".rodata"), "const")

    def test_const_rodata_str(self):
        self.assertEqual(elf_utils._classify_symbol("STT_OBJECT", ".rodata.str1.1"), "const")

    def test_other_type(self):
        self.assertEqual(elf_utils._classify_symbol("STT_NOTYPE", ".text"), "other")

    def test_unknown_section_object(self):
        """STT_OBJECT in unknown section defaults to variable"""
        self.assertEqual(elf_utils._classify_symbol("STT_OBJECT", ".custom"), "variable")


def _make_mock_elf(symbols_data):
    """Create a mock ELFFile with given symbol data.

    symbols_data: list of (name, addr, size, type_str, shndx, section_name)
    """
    mock_elf = MagicMock()

    # Build sections dict
    sections = {}
    for _, _, _, _, shndx, sec_name in symbols_data:
        if isinstance(shndx, int) and shndx not in sections:
            sec = MagicMock()
            sec.name = sec_name
            sections[shndx] = sec

    def get_section(idx):
        return sections.get(idx)

    mock_elf.get_section = get_section

    # Build symtab — use spec to pass isinstance check
    mock_symtab = MagicMock(spec=SymbolTableSection)

    mock_symbols = []
    for name, addr, size, type_str, shndx, _ in symbols_data:
        sym = MagicMock()
        sym.name = name
        sym.__getitem__ = lambda self, key, _a=addr, _s=size, _t=type_str, _sh=shndx: {
            "st_value": _a,
            "st_size": _s,
            "st_info": {"type": _t},
            "st_shndx": _sh,
        }[key]
        mock_symbols.append(sym)

    mock_symtab.iter_symbols.return_value = mock_symbols
    mock_elf.get_section_by_name.return_value = mock_symtab

    return mock_elf


class TestGetSymbols(unittest.TestCase):
    """get_symbols function tests (pyelftools-based)"""

    @patch("core.elf_utils.subprocess.run")
    @patch("core.elf_utils.ELFFile")
    @patch("builtins.open", create=True)
    def test_get_symbols_success(self, mock_open, mock_elffile_cls, mock_run):
        """Test getting symbols with pyelftools"""
        mock_elf = _make_mock_elf([
            ("main", 0x08000000, 100, "STT_FUNC", 1, ".text"),
            ("g_var", 0x20000000, 4, "STT_OBJECT", 2, ".data"),
            ("k_const", 0x08010000, 8, "STT_OBJECT", 3, ".rodata"),
        ])
        mock_elffile_cls.return_value = mock_elf
        mock_open.return_value.__enter__ = lambda s: MagicMock()
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        # nm -C for demangling pass (returns empty — no C++ symbols)
        mock_run.return_value = Mock(returncode=0, stdout="")

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            symbols = elf_utils.get_symbols(elf_path)

            self.assertIn("main", symbols)
            self.assertEqual(symbols["main"]["addr"], 0x08000000)
            self.assertEqual(symbols["main"]["type"], "function")
            self.assertEqual(symbols["main"]["size"], 100)

            self.assertIn("g_var", symbols)
            self.assertEqual(symbols["g_var"]["type"], "variable")

            self.assertIn("k_const", symbols)
            self.assertEqual(symbols["k_const"]["type"], "const")
        finally:
            os.unlink(elf_path)

    @patch("core.elf_utils.ELFFile")
    @patch("builtins.open", create=True)
    def test_get_symbols_skips_undefined(self, mock_open, mock_elffile_cls):
        """Test that undefined and zero-size symbols are skipped"""
        mock_elf = _make_mock_elf([
            ("undef_sym", 0, 0, "STT_FUNC", "SHN_UNDEF", ""),
            ("zero_size", 0x08000000, 0, "STT_FUNC", 1, ".text"),
            ("valid", 0x08000100, 10, "STT_FUNC", 1, ".text"),
        ])
        mock_elffile_cls.return_value = mock_elf
        mock_open.return_value.__enter__ = lambda s: MagicMock()
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            symbols = elf_utils.get_symbols(elf_path)
            self.assertNotIn("undef_sym", symbols)
            self.assertNotIn("zero_size", symbols)
            self.assertIn("valid", symbols)
        finally:
            os.unlink(elf_path)

    def test_get_symbols_nonexistent_file(self):
        """Test with nonexistent ELF file"""
        symbols = elf_utils.get_symbols("/nonexistent/file.elf")
        self.assertEqual(symbols, {})

    def test_get_symbols_empty_path(self):
        """Test with empty path"""
        symbols = elf_utils.get_symbols("")
        self.assertEqual(symbols, {})

    @patch("core.elf_utils.ELFFile")
    @patch("builtins.open", create=True)
    def test_get_symbols_exception(self, mock_open, mock_elffile_cls):
        """Test getting symbols when pyelftools raises exception"""
        mock_elffile_cls.side_effect = Exception("Invalid ELF")
        mock_open.return_value.__enter__ = lambda s: MagicMock()
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            symbols = elf_utils.get_symbols(elf_path)
            self.assertEqual(symbols, {})
        finally:
            os.unlink(elf_path)


class TestReadSymbolValue(unittest.TestCase):
    """read_symbol_value function tests"""

    def test_nonexistent_file(self):
        result = elf_utils.read_symbol_value("/nonexistent.elf", "sym")
        self.assertIsNone(result)

    def test_empty_path(self):
        result = elf_utils.read_symbol_value("", "sym")
        self.assertIsNone(result)

    @patch("core.elf_utils.ELFFile")
    @patch("builtins.open", create=True)
    def test_read_rodata_value(self, mock_open, mock_elffile_cls):
        """Test reading a .rodata symbol value"""
        mock_elf = MagicMock()
        mock_symtab = MagicMock(spec=SymbolTableSection)

        # Create a symbol at addr 0x08010004, size 4, in section starting at 0x08010000
        sym = MagicMock()
        sym.name = "my_const"
        sym.__getitem__ = lambda self, key: {
            "st_size": 4,
            "st_value": 0x08010004,
            "st_shndx": 1,
        }[key]

        section = MagicMock()
        section.name = ".rodata"
        section.__getitem__ = lambda self, key: {
            "sh_addr": 0x08010000,
            "sh_type": "SHT_PROGBITS",
        }[key]
        section.data.return_value = b"\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06"

        mock_symtab.iter_symbols.return_value = [sym]
        mock_elf.get_section_by_name.return_value = mock_symtab
        mock_elf.get_section.return_value = section
        mock_elffile_cls.return_value = mock_elf
        mock_open.return_value.__enter__ = lambda s: MagicMock()
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.read_symbol_value(elf_path, "my_const")
            self.assertEqual(result, b"\x01\x02\x03\x04")
        finally:
            os.unlink(elf_path)

    @patch("core.elf_utils.ELFFile")
    @patch("builtins.open", create=True)
    def test_read_bss_returns_none(self, mock_open, mock_elffile_cls):
        """Test that .bss symbols return None"""
        mock_elf = MagicMock()
        mock_symtab = MagicMock(spec=SymbolTableSection)

        sym = MagicMock()
        sym.name = "bss_var"
        sym.__getitem__ = lambda self, key: {
            "st_size": 4,
            "st_value": 0x20000000,
            "st_shndx": 2,
        }[key]

        section = MagicMock()
        section.name = ".bss"
        section.__getitem__ = lambda self, key: {
            "sh_addr": 0x20000000,
            "sh_type": "SHT_NOBITS",
        }[key]

        mock_symtab.iter_symbols.return_value = [sym]
        mock_elf.get_section_by_name.return_value = mock_symtab
        mock_elf.get_section.return_value = section
        mock_elffile_cls.return_value = mock_elf
        mock_open.return_value.__enter__ = lambda s: MagicMock()
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.read_symbol_value(elf_path, "bss_var")
            self.assertIsNone(result)
        finally:
            os.unlink(elf_path)

    @patch("core.elf_utils.ELFFile")
    @patch("builtins.open", create=True)
    def test_read_symbol_not_found(self, mock_open, mock_elffile_cls):
        """Test reading a symbol that doesn't exist"""
        mock_elf = MagicMock()
        mock_symtab = MagicMock(spec=SymbolTableSection)
        mock_symtab.iter_symbols.return_value = []
        mock_elf.get_section_by_name.return_value = mock_symtab
        mock_elffile_cls.return_value = mock_elf
        mock_open.return_value.__enter__ = lambda s: MagicMock()
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.read_symbol_value(elf_path, "nonexistent")
            self.assertIsNone(result)
        finally:
            os.unlink(elf_path)


class TestGetStructLayout(unittest.TestCase):
    """get_struct_layout function tests"""

    def test_nonexistent_file(self):
        result = elf_utils.get_struct_layout("/nonexistent.elf", "sym")
        self.assertIsNone(result)

    @patch("core.elf_utils.ELFFile")
    @patch("builtins.open", create=True)
    def test_no_dwarf_info(self, mock_open, mock_elffile_cls):
        """Test when ELF has no DWARF info"""
        mock_elf = MagicMock()
        mock_elf.has_dwarf_info.return_value = False
        mock_elffile_cls.return_value = mock_elf
        mock_open.return_value.__enter__ = lambda s: MagicMock()
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.get_struct_layout(elf_path, "my_struct")
            self.assertIsNone(result)
        finally:
            os.unlink(elf_path)

    @patch("core.elf_utils.ELFFile")
    @patch("builtins.open", create=True)
    def test_variable_not_found(self, mock_open, mock_elffile_cls):
        """Test when variable not found in DWARF"""
        mock_elf = MagicMock()
        mock_elf.has_dwarf_info.return_value = True
        mock_dwarf = MagicMock()
        mock_cu = MagicMock()
        mock_cu.iter_DIEs.return_value = []
        mock_dwarf.iter_CUs.return_value = [mock_cu]
        mock_elf.get_dwarf_info.return_value = mock_dwarf
        mock_elffile_cls.return_value = mock_elf
        mock_open.return_value.__enter__ = lambda s: MagicMock()
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.get_struct_layout(elf_path, "nonexistent")
            self.assertIsNone(result)
        finally:
            os.unlink(elf_path)


class TestDisassembleFunction(unittest.TestCase):
    """disassemble_function tests"""

    @patch("subprocess.run")
    def test_disassemble_success(self, mock_run):
        """Test successful disassembly"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="08000000 <main>:\n 8000000: push {r7, lr}\n 8000002: mov r7, sp\n",
        )

        success, result = elf_utils.disassemble_function("/path/to/elf", "main")

        self.assertTrue(success)
        self.assertIn("main", result)

    @patch("subprocess.run")
    def test_disassemble_function_not_found(self, mock_run):
        """Test disassembly when function not found"""
        mock_run.return_value = Mock(returncode=0, stdout="")

        success, result = elf_utils.disassemble_function("/path/to/elf", "nonexistent")

        self.assertFalse(success)
        self.assertIn("not found", result)

    @patch("subprocess.run")
    def test_disassemble_timeout(self, mock_run):
        """Test disassembly timeout"""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("objdump", 30)

        success, result = elf_utils.disassemble_function("/path/to/elf", "main")

        self.assertFalse(success)
        self.assertIn("timed out", result)

    @patch("subprocess.run")
    def test_disassemble_tool_not_found(self, mock_run):
        """Test disassembly when tool not found"""
        mock_run.side_effect = FileNotFoundError("objdump not found")

        success, result = elf_utils.disassemble_function("/path/to/elf", "main")

        self.assertFalse(success)
        self.assertIn("not found", result)


class TestDecompileFunction(unittest.TestCase):
    """decompile_function tests"""

    def setUp(self):
        """Clear cache before each test"""
        elf_utils.clear_ghidra_cache()

    def tearDown(self):
        """Clear cache after each test"""
        elf_utils.clear_ghidra_cache()

    def test_decompile_ghidra_not_configured(self):
        """Test decompile when Ghidra is not configured"""
        # Without ghidra_path, should return GHIDRA_NOT_CONFIGURED
        success, result = elf_utils.decompile_function("/path/to/elf", "main", None)

        self.assertFalse(success)
        self.assertEqual(result, "GHIDRA_NOT_CONFIGURED")

    def test_decompile_ghidra_path_empty_string(self):
        """Test decompile when ghidra_path is empty string"""
        success, result = elf_utils.decompile_function("/path/to/elf", "main", "")

        self.assertFalse(success)
        self.assertEqual(result, "GHIDRA_NOT_CONFIGURED")

    def test_decompile_ghidra_path_invalid(self):
        """Test decompile when ghidra_path is invalid directory"""
        success, result = elf_utils.decompile_function(
            "/path/to/elf", "main", "/nonexistent/ghidra/path"
        )

        self.assertFalse(success)
        self.assertEqual(result, "GHIDRA_NOT_CONFIGURED")

    def test_decompile_elf_not_found(self):
        """Test decompile when ELF file doesn't exist"""
        import tempfile
        import os

        # Create a temp dir to use as ghidra_path, but no analyzeHeadless
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create support directory with a fake analyzeHeadless
            support_dir = os.path.join(temp_dir, "support")
            os.makedirs(support_dir)
            analyze_headless = os.path.join(support_dir, "analyzeHeadless")
            with open(analyze_headless, "w") as f:
                f.write("#!/bin/bash\nexit 0\n")
            os.chmod(analyze_headless, 0o755)

            success, result = elf_utils.decompile_function(
                "/nonexistent/file.elf", "main", temp_dir
            )

            self.assertFalse(success)
            self.assertIn("not found", result.lower())


class TestGhidraProjectCache(unittest.TestCase):
    """Tests for Ghidra project caching functionality"""

    def setUp(self):
        """Clear cache before each test"""
        elf_utils.clear_ghidra_cache()

    def tearDown(self):
        """Clear cache after each test"""
        elf_utils.clear_ghidra_cache()

    def test_clear_ghidra_cache(self):
        """Test clearing the Ghidra cache"""
        # Set up some cache state
        cache = elf_utils._ghidra_project_cache
        cache["elf_path"] = "/some/path.elf"
        cache["elf_mtime"] = 12345

        elf_utils.clear_ghidra_cache()

        self.assertIsNone(cache["elf_path"])
        self.assertIsNone(cache["elf_mtime"])
        self.assertIsNone(cache["project_dir"])

    def test_get_cached_ghidra_project_new(self):
        """Test getting a new Ghidra project"""
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name
            f.write(b"test")

        try:
            project_dir, project_name, is_new = elf_utils._get_cached_ghidra_project(
                elf_path, None
            )

            self.assertTrue(is_new)
            self.assertEqual(project_name, "fpb_decompile")
            self.assertTrue(os.path.exists(project_dir))
        finally:
            os.unlink(elf_path)

    def test_get_cached_ghidra_project_reuse(self):
        """Test reusing a cached Ghidra project"""
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name
            f.write(b"test")

        try:
            # First call creates new project
            project_dir1, _, is_new1 = elf_utils._get_cached_ghidra_project(
                elf_path, None
            )
            self.assertTrue(is_new1)

            # Second call should reuse
            project_dir2, _, is_new2 = elf_utils._get_cached_ghidra_project(
                elf_path, None
            )
            self.assertFalse(is_new2)
            self.assertEqual(project_dir1, project_dir2)
        finally:
            os.unlink(elf_path)

    def test_get_cached_ghidra_project_different_elf(self):
        """Test that different ELF files get different projects"""
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f1:
            elf_path1 = f1.name
            f1.write(b"test1")

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f2:
            elf_path2 = f2.name
            f2.write(b"test2")

        try:
            # First ELF
            project_dir1, _, is_new1 = elf_utils._get_cached_ghidra_project(
                elf_path1, None
            )
            self.assertTrue(is_new1)

            # Different ELF should create new project
            project_dir2, _, is_new2 = elf_utils._get_cached_ghidra_project(
                elf_path2, None
            )
            self.assertTrue(is_new2)
            self.assertNotEqual(project_dir1, project_dir2)
        finally:
            os.unlink(elf_path1)
            os.unlink(elf_path2)

    def test_get_cached_ghidra_project_modified_elf(self):
        """Test that modified ELF file invalidates cache"""
        import time

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name
            f.write(b"test")

        try:
            # First call
            project_dir1, _, is_new1 = elf_utils._get_cached_ghidra_project(
                elf_path, None
            )
            self.assertTrue(is_new1)

            # Modify the file
            time.sleep(0.1)  # Ensure mtime changes
            with open(elf_path, "wb") as f:
                f.write(b"modified")

            # Should create new project due to mtime change
            project_dir2, _, is_new2 = elf_utils._get_cached_ghidra_project(
                elf_path, None
            )
            self.assertTrue(is_new2)
        finally:
            os.unlink(elf_path)


class TestGetSignature(unittest.TestCase):
    """get_signature function tests"""

    @patch("subprocess.run")
    def test_get_signature_with_params(self, mock_run):
        """Test getting signature with parameters"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="08000000 T test_func(int, char*)\n",
        )

        result = elf_utils.get_signature("/path/to/elf", "test_func")

        self.assertIsNotNone(result)
        self.assertIn("test_func", result)

    @patch("subprocess.run")
    def test_get_signature_simple(self, mock_run):
        """Test getting simple signature"""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="08000000 T main\n"),
            Mock(returncode=0, stdout=""),
        ]

        result = elf_utils.get_signature("/path/to/elf", "main")

        self.assertEqual(result, "main")

    @patch("subprocess.run")
    def test_get_signature_error(self, mock_run):
        """Test getting signature with error"""
        mock_run.side_effect = Exception("nm failed")

        result = elf_utils.get_signature("/path/to/elf", "test_func")

        self.assertEqual(result, "test_func")


if __name__ == "__main__":
    unittest.main()


class TestDisassembleFunctionExtended(unittest.TestCase):
    """Extended disassemble_function tests"""

    @patch("subprocess.run")
    def test_disassemble_fallback_without_demangling(self, mock_run):
        """Test disassembly fallback without demangling"""
        # First call with -C returns empty, second without -C returns result
        mock_run.side_effect = [
            Mock(returncode=0, stdout=""),
            Mock(
                returncode=0,
                stdout="08000000 <_Z4mainv>:\n 8000000: push {r7, lr}\n",
            ),
        ]

        success, result = elf_utils.disassemble_function("/path/to/elf", "_Z4mainv")

        self.assertTrue(success)
        self.assertIn("_Z4mainv", result)

    @patch("subprocess.run")
    def test_disassemble_extracts_function_only(self, mock_run):
        """Test disassembly extracts only the target function"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
08000000 <main>:
 8000000: push {r7, lr}
 8000002: mov r7, sp

08000010 <other_func>:
 8000010: bx lr
""",
        )

        success, result = elf_utils.disassemble_function("/path/to/elf", "main")

        self.assertTrue(success)
        self.assertIn("main", result)
        # Should stop before other_func
        self.assertNotIn("other_func", result)


class TestGetElfBuildTimeExtended(unittest.TestCase):
    """Extended get_elf_build_time tests"""

    @patch("subprocess.run")
    def test_build_time_no_match(self, mock_run):
        """Test when no build time pattern found"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="random data\nno date here\njust text",
        )

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.get_elf_build_time(elf_path)
            self.assertIsNone(result)
        finally:
            os.unlink(elf_path)

    @patch("subprocess.run")
    def test_build_time_exception(self, mock_run):
        """Test when exception occurs"""
        mock_run.side_effect = Exception("strings failed")

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.get_elf_build_time(elf_path)
            self.assertIsNone(result)
        finally:
            os.unlink(elf_path)


class TestGetTypeHelpers(unittest.TestCase):
    """Tests for DWARF type helper functions"""

    def test_get_type_name_none(self):
        self.assertEqual(elf_utils._get_type_name(None), "unknown")

    def test_get_type_name_max_depth(self):
        self.assertEqual(elf_utils._get_type_name(MagicMock(), max_depth=0), "unknown")

    def test_get_type_size_with_byte_size(self):
        die = MagicMock()
        die.attributes = {"DW_AT_byte_size": MagicMock(value=4)}
        self.assertEqual(elf_utils._get_type_size(die), 4)


if __name__ == "__main__":
    unittest.main()
