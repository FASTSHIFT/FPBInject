#!/usr/bin/env python3
"""
Integration tests for the ELF symbol pipeline.

Uses the pre-built test_symbols.elf fixture to test the full chain:
  nm (get_symbols) -> GDB (lookup_symbol) -> struct_layout -> read_symbol_value

These tests require:
  - arm-none-eabi-nm (for nm-based symbol extraction)
  - gdb-multiarch (for GDB-based symbol queries)

If either tool is missing the tests are skipped automatically.

Fixture rebuild:
  cd tests/fixtures && bash build_test_elf.sh
"""

import shutil
import subprocess
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.elf_utils import get_symbols, _NM_TYPE_MAP

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_ELF = FIXTURES_DIR / "test_symbols.elf"
TEST_CPP_ELF = FIXTURES_DIR / "test_symbols_cpp.elf"

HAS_NM = shutil.which("arm-none-eabi-nm") is not None
HAS_GDB = shutil.which("gdb-multiarch") is not None


def _need_rebuild():
    """Check if any ELF needs rebuilding (source newer than binary)."""
    pairs = [
        (FIXTURES_DIR / "test_symbols.c", TEST_ELF),
        (FIXTURES_DIR / "test_symbols_cpp.cpp", TEST_CPP_ELF),
    ]
    for src, elf in pairs:
        if not elf.exists():
            return True
        if src.exists() and src.stat().st_mtime > elf.stat().st_mtime:
            return True
    return False


def setUpModule():
    """Rebuild test ELF if source is newer."""
    if _need_rebuild() and HAS_NM:
        script = FIXTURES_DIR / "build_test_elf.sh"
        if script.exists():
            subprocess.run(
                ["bash", str(script)],
                capture_output=True,
                timeout=30,
            )


# ── Helper: start a GDB session on the fixture ELF ──────────────────


def _make_gdb_session():
    """Create a GDBSession connected to the test ELF (no RSP)."""
    from core.gdb_session import GDBSession
    from pygdbmi.IoManager import IoManager
    from utils.toolchain import get_subprocess_env

    gdb = GDBSession(str(TEST_ELF))
    gdb_path, is_multiarch = gdb._find_gdb()
    if not gdb_path:
        return None

    env = get_subprocess_env(None)
    proc = subprocess.Popen(
        [gdb_path, "--interpreter=mi3", "--nx", "-q"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        bufsize=0,
    )
    gdb._proc = proc
    gdb._io = IoManager(
        proc.stdin,
        proc.stdout,
        proc.stderr,
        time_to_check_for_additional_output_sec=0.3,
    )
    gdb._io.get_gdb_response(timeout_sec=5.0, raise_error_on_timeout=False)

    if is_multiarch:
        gdb._write_mi("set architecture arm", timeout=5.0)

    resp = gdb._write_mi(f"file {TEST_ELF}", timeout=30.0)
    if resp is None:
        proc.terminate()
        return None

    gdb._alive = True
    return gdb


# ═══════════════════════════════════════════════════════════════════
# Test 1: nm symbol extraction
# ═══════════════════════════════════════════════════════════════════


@unittest.skipUnless(HAS_NM, "arm-none-eabi-nm not found")
@unittest.skipUnless(TEST_ELF.exists(), "test_symbols.elf not built")
class TestNmSymbolExtraction(unittest.TestCase):
    """Test get_symbols() nm-based extraction against the fixture ELF."""

    @classmethod
    def setUpClass(cls):
        cls.symbols = get_symbols(str(TEST_ELF))

    def test_symbols_not_empty(self):
        self.assertGreater(len(self.symbols), 0)

    def test_returns_dict_format(self):
        """Every value must be {"addr": int, "sym_type": str}."""
        for name, info in self.symbols.items():
            self.assertIsInstance(info, dict, f"Symbol '{name}' is not dict")
            self.assertIn("addr", info, f"Symbol '{name}' missing 'addr'")
            self.assertIn("sym_type", info, f"Symbol '{name}' missing 'sym_type'")
            self.assertIsInstance(info["addr"], int)
            self.assertIn(
                info["sym_type"],
                ("function", "variable", "const", "other"),
                f"Symbol '{name}' has invalid sym_type: {info['sym_type']}",
            )

    def test_known_functions(self):
        """Known global functions should be present with type=function."""
        for name in [
            "global_func",
            "add_values",
            "make_point",
            "sum_array",
            "get_call_count",
            "weak_handler",
        ]:
            self.assertIn(name, self.symbols, f"Function '{name}' not found")
            self.assertEqual(self.symbols[name]["sym_type"], "function")

    def test_static_function(self):
        """Static function should be present with type=function."""
        self.assertIn("static_helper", self.symbols)
        self.assertEqual(self.symbols["static_helper"]["sym_type"], "function")

    def test_known_variables(self):
        """Known global variables should be present with type=variable."""
        for name in [
            "g_counter",
            "g_point",
            "g_rect",
            "g_padded",
            "g_nested",
            "g_union",
            "g_signed_var",
        ]:
            self.assertIn(name, self.symbols, f"Variable '{name}' not found")
            self.assertEqual(self.symbols[name]["sym_type"], "variable")

    def test_bss_variables(self):
        """BSS variables should be present with type=variable."""
        for name in ["g_bss_var", "g_bss_point", "g_bss_array"]:
            self.assertIn(name, self.symbols, f"BSS var '{name}' not found")
            self.assertEqual(self.symbols[name]["sym_type"], "variable")

    def test_known_constants(self):
        """Known const data should be present with type=const."""
        for name in [
            "g_const_value",
            "g_const_point",
            "g_const_string",
            "g_const_table",
            "g_pin_map",
        ]:
            self.assertIn(name, self.symbols, f"Const '{name}' not found")
            self.assertEqual(self.symbols[name]["sym_type"], "const")

    def test_static_const(self):
        """Static const should be present with type=const."""
        self.assertIn("s_static_const", self.symbols)
        self.assertEqual(self.symbols["s_static_const"]["sym_type"], "const")

    def test_static_variable(self):
        """Static variable should be present with type=variable."""
        self.assertIn("s_static_var", self.symbols)
        self.assertEqual(self.symbols["s_static_var"]["sym_type"], "variable")

    def test_local_static_with_dot_suffix(self):
        """Local static 'call_count.0' should be present."""
        dot_syms = [n for n in self.symbols if n.startswith("call_count.")]
        self.assertGreater(len(dot_syms), 0, "No call_count.N symbol found")
        info = self.symbols[dot_syms[0]]
        self.assertEqual(info["sym_type"], "variable")

    def test_addresses_nonzero(self):
        """User-defined symbols should have non-zero addresses."""
        for name in ["global_func", "g_counter", "g_const_value"]:
            self.assertGreater(self.symbols[name]["addr"], 0)

    def test_text_vs_data_address_ranges(self):
        """Functions should be in flash (0x08xxxxxx), variables in RAM (0x20xxxxxx)."""
        func_addr = self.symbols["global_func"]["addr"]
        var_addr = self.symbols["g_counter"]["addr"]
        self.assertTrue(
            0x08000000 <= func_addr < 0x09000000,
            f"Function addr 0x{func_addr:08X} not in flash range",
        )
        self.assertTrue(
            0x20000000 <= var_addr < 0x21000000,
            f"Variable addr 0x{var_addr:08X} not in RAM range",
        )

    def test_nm_type_map_covers_all_codes(self):
        """All single-letter nm type codes in the ELF should be mapped."""
        result = subprocess.run(
            ["arm-none-eabi-nm", str(TEST_ELF)],
            capture_output=True,
            text=True,
        )
        codes = set()
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                codes.add(parts[1])
        unmapped = {c for c in codes if c not in _NM_TYPE_MAP}
        # 'A' (absolute) is now mapped to 'other'
        self.assertEqual(
            unmapped,
            set(),
            f"Unmapped nm type codes: {unmapped}",
        )


# ═══════════════════════════════════════════════════════════════════
# Test 2: GDB symbol lookup
# ═══════════════════════════════════════════════════════════════════


@unittest.skipUnless(HAS_NM and HAS_GDB, "arm-none-eabi-nm or gdb-multiarch not found")
@unittest.skipUnless(TEST_ELF.exists(), "test_symbols.elf not built")
class TestGdbLookupSymbol(unittest.TestCase):
    """Test GDB lookup_symbol against the fixture ELF."""

    @classmethod
    def setUpClass(cls):
        cls.gdb = _make_gdb_session()
        if cls.gdb is None:
            raise unittest.SkipTest("Failed to start GDB session")

    @classmethod
    def tearDownClass(cls):
        if cls.gdb:
            try:
                cls.gdb.stop()
            except Exception:
                pass

    def test_global_function(self):
        info = self.gdb.lookup_symbol("global_func")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "function")
        self.assertEqual(info["section"], ".text")
        self.assertGreater(info["addr"], 0)

    def test_global_variable_data(self):
        info = self.gdb.lookup_symbol("g_counter")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "variable")
        self.assertGreater(info["size"], 0)
        self.assertTrue(0x20000000 <= info["addr"] < 0x21000000)

    def test_bss_variable(self):
        info = self.gdb.lookup_symbol("g_bss_var")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "variable")
        self.assertEqual(info["section"], ".bss")

    def test_const_variable(self):
        info = self.gdb.lookup_symbol("g_const_value")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "const")
        self.assertEqual(info["section"], ".rodata")
        self.assertEqual(info["size"], 4)

    def test_struct_variable_size(self):
        info = self.gdb.lookup_symbol("g_padded")
        self.assertIsNotNone(info)
        self.assertEqual(info["size"], 12)  # PaddedStruct with padding

    def test_nested_struct_size(self):
        info = self.gdb.lookup_symbol("g_nested")
        self.assertIsNotNone(info)
        self.assertEqual(info["size"], 16)  # Nested = PaddedStruct(12) + uint32(4)

    def test_union_size(self):
        info = self.gdb.lookup_symbol("g_union")
        self.assertIsNotNone(info)
        self.assertEqual(info["size"], 4)

    def test_array_size(self):
        info = self.gdb.lookup_symbol("g_bss_array")
        self.assertIsNotNone(info)
        self.assertEqual(info["size"], 64)

    def test_const_array_size(self):
        info = self.gdb.lookup_symbol("g_const_table")
        self.assertIsNotNone(info)
        self.assertEqual(info["size"], 16)

    def test_const_struct_array_size(self):
        info = self.gdb.lookup_symbol("g_pin_map")
        self.assertIsNotNone(info)
        self.assertEqual(info["size"], 48)  # PinMap_t(12) * 4

    def test_weak_function(self):
        info = self.gdb.lookup_symbol("weak_handler")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "function")

    def test_section_fallback_for_data(self):
        """Section should be resolved via 'info symbol' fallback for .data vars."""
        info = self.gdb.lookup_symbol("g_point")
        self.assertIsNotNone(info)
        self.assertEqual(info["section"], ".data")

    def test_section_fallback_for_rodata(self):
        """Section should be resolved via 'info symbol' fallback for .rodata."""
        info = self.gdb.lookup_symbol("g_const_string")
        self.assertIsNotNone(info)
        self.assertEqual(info["section"], ".rodata")

    def test_nonexistent_symbol(self):
        info = self.gdb.lookup_symbol("this_symbol_does_not_exist_xyz")
        self.assertIsNone(info)


# ═══════════════════════════════════════════════════════════════════
# Test 3: GDB struct layout
# ═══════════════════════════════════════════════════════════════════


@unittest.skipUnless(HAS_NM and HAS_GDB, "arm-none-eabi-nm or gdb-multiarch not found")
@unittest.skipUnless(TEST_ELF.exists(), "test_symbols.elf not built")
class TestGdbStructLayout(unittest.TestCase):
    """Test GDB get_struct_layout against the fixture ELF."""

    @classmethod
    def setUpClass(cls):
        cls.gdb = _make_gdb_session()
        if cls.gdb is None:
            raise unittest.SkipTest("Failed to start GDB session")

    @classmethod
    def tearDownClass(cls):
        if cls.gdb:
            try:
                cls.gdb.stop()
            except Exception:
                pass

    def test_simple_struct(self):
        layout = self.gdb.get_struct_layout("g_point")
        self.assertIsNotNone(layout)
        self.assertEqual(len(layout), 2)
        names = [m["name"] for m in layout]
        self.assertIn("x", names)
        self.assertIn("y", names)

    def test_padded_struct(self):
        layout = self.gdb.get_struct_layout("g_padded")
        self.assertIsNotNone(layout)
        self.assertEqual(len(layout), 4)
        # Check offsets account for padding
        by_name = {m["name"]: m for m in layout}
        self.assertEqual(by_name["a"]["offset"], 0)
        self.assertEqual(by_name["b"]["offset"], 4)  # 3 bytes padding after a
        self.assertEqual(by_name["c"]["offset"], 8)
        self.assertEqual(by_name["d"]["offset"], 10)

    def test_nested_struct(self):
        layout = self.gdb.get_struct_layout("g_nested")
        self.assertIsNotNone(layout)
        # Parser flattens nested structs — inner members appear at top level
        names = [m["name"] for m in layout]
        self.assertIn("id", names)
        # The nested PaddedStruct members are flattened
        self.assertGreaterEqual(len(layout), 2)

    def test_union(self):
        # Known limitation: ptype /o union format uses "/* size */" without
        # offset, so the current regex-based parser cannot parse union members.
        layout = self.gdb.get_struct_layout("g_union")
        # Union members are not parsed by current implementation
        self.assertIsNone(layout)

    def test_non_struct_returns_none(self):
        """Scalar variable should return None for struct layout."""
        layout = self.gdb.get_struct_layout("g_counter")
        self.assertIsNone(layout)

    def test_function_returns_none(self):
        layout = self.gdb.get_struct_layout("global_func")
        self.assertIsNone(layout)

    def test_const_struct(self):
        layout = self.gdb.get_struct_layout("g_const_point")
        self.assertIsNotNone(layout)
        self.assertEqual(len(layout), 2)


# ═══════════════════════════════════════════════════════════════════
# Test 4: GDB read symbol value
# ═══════════════════════════════════════════════════════════════════


@unittest.skipUnless(HAS_NM and HAS_GDB, "arm-none-eabi-nm or gdb-multiarch not found")
@unittest.skipUnless(TEST_ELF.exists(), "test_symbols.elf not built")
class TestGdbReadSymbolValue(unittest.TestCase):
    """Test GDB read_symbol_value against the fixture ELF."""

    @classmethod
    def setUpClass(cls):
        cls.gdb = _make_gdb_session()
        if cls.gdb is None:
            raise unittest.SkipTest("Failed to start GDB session")

    @classmethod
    def tearDownClass(cls):
        if cls.gdb:
            try:
                cls.gdb.stop()
            except Exception:
                pass

    def test_read_initialized_variable(self):
        """Read g_counter which is initialized to 42."""
        data = self.gdb.read_symbol_value("g_counter")
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 4)
        value = int.from_bytes(data, byteorder="little")
        self.assertEqual(value, 42)

    def test_read_signed_variable(self):
        """Read g_signed_var which is initialized to -100."""
        data = self.gdb.read_symbol_value("g_signed_var")
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 4)
        value = int.from_bytes(data, byteorder="little", signed=True)
        self.assertEqual(value, -100)

    def test_read_struct_variable(self):
        """Read g_padded and verify known field values."""
        data = self.gdb.read_symbol_value("g_padded")
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 12)
        # a at offset 0 = 1
        self.assertEqual(data[0], 1)
        # b at offset 4 = 0xDEADBEEF (little-endian)
        b_val = int.from_bytes(data[4:8], byteorder="little")
        self.assertEqual(b_val, 0xDEADBEEF)
        # c at offset 8 = 0x1234
        c_val = int.from_bytes(data[8:10], byteorder="little")
        self.assertEqual(c_val, 0x1234)
        # d at offset 10 = 0xFF
        self.assertEqual(data[10], 0xFF)

    def test_read_const_value(self):
        """Read g_const_value which is 0xA5A5A5A5."""
        data = self.gdb.read_symbol_value("g_const_value")
        self.assertIsNotNone(data)
        value = int.from_bytes(data, byteorder="little")
        self.assertEqual(value, 0xA5A5A5A5)

    def test_read_const_string(self):
        """Read g_const_string."""
        data = self.gdb.read_symbol_value("g_const_string")
        self.assertIsNotNone(data)
        text = data.rstrip(b"\x00").decode("ascii")
        self.assertEqual(text, "FPBInject Test Fixture")

    def test_read_bss_returns_none(self):
        """BSS variables should return None (zero-initialized, not in ELF)."""
        data = self.gdb.read_symbol_value("g_bss_var")
        self.assertIsNone(data)

    def test_read_union(self):
        """Read g_union initialized to {.as_u32 = 0x12345678}."""
        data = self.gdb.read_symbol_value("g_union")
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 4)
        value = int.from_bytes(data, byteorder="little")
        self.assertEqual(value, 0x12345678)

    def test_read_function_returns_none_or_small(self):
        """Functions have size=1 in GDB, read may return 1 byte or None."""
        # Functions are in .text, not .bss, so read_symbol_value may return
        # 1 byte (the first instruction byte). This is acceptable.
        data = self.gdb.read_symbol_value("global_func")
        # Either None (if implementation skips size<=0) or 1 byte
        if data is not None:
            self.assertLessEqual(len(data), 4)


# ═══════════════════════════════════════════════════════════════════
# Test 5: nm / GDB consistency
# ═══════════════════════════════════════════════════════════════════


@unittest.skipUnless(HAS_NM and HAS_GDB, "arm-none-eabi-nm or gdb-multiarch not found")
@unittest.skipUnless(TEST_ELF.exists(), "test_symbols.elf not built")
class TestNmGdbConsistency(unittest.TestCase):
    """Verify nm and GDB agree on symbol types for well-defined symbols."""

    @classmethod
    def setUpClass(cls):
        cls.nm_symbols = get_symbols(str(TEST_ELF))
        cls.gdb = _make_gdb_session()
        if cls.gdb is None:
            raise unittest.SkipTest("Failed to start GDB session")

    @classmethod
    def tearDownClass(cls):
        if cls.gdb:
            try:
                cls.gdb.stop()
            except Exception:
                pass

    def _check_type(self, name, expected_type):
        nm_info = self.nm_symbols.get(name)
        self.assertIsNotNone(nm_info, f"'{name}' not in nm symbols")
        self.assertEqual(
            nm_info["sym_type"], expected_type, f"nm type mismatch for '{name}'"
        )

        gdb_info = self.gdb.lookup_symbol(name)
        self.assertIsNotNone(gdb_info, f"GDB lookup failed for '{name}'")
        self.assertEqual(
            gdb_info["type"], expected_type, f"GDB type mismatch for '{name}'"
        )

    def test_function_consistency(self):
        for name in ["global_func", "add_values", "make_point"]:
            with self.subTest(name=name):
                self._check_type(name, "function")

    def test_variable_consistency(self):
        for name in ["g_counter", "g_point", "g_bss_var"]:
            with self.subTest(name=name):
                self._check_type(name, "variable")

    def test_const_consistency(self):
        for name in ["g_const_value", "g_const_point", "g_const_table"]:
            with self.subTest(name=name):
                self._check_type(name, "const")

    def test_address_consistency(self):
        """nm and GDB should agree on symbol addresses."""
        for name in ["global_func", "g_counter", "g_const_value", "g_padded"]:
            with self.subTest(name=name):
                nm_addr = self.nm_symbols[name]["addr"]
                gdb_info = self.gdb.lookup_symbol(name)
                self.assertIsNotNone(gdb_info)
                self.assertEqual(
                    nm_addr, gdb_info["addr"], f"Address mismatch for '{name}'"
                )


# ═══════════════════════════════════════════════════════════════════
# C++ fixture helpers
# ═══════════════════════════════════════════════════════════════════


def _make_cpp_gdb_session():
    """Create a GDBSession connected to the C++ test ELF (no RSP)."""
    from core.gdb_session import GDBSession
    from pygdbmi.IoManager import IoManager
    from utils.toolchain import get_subprocess_env

    gdb = GDBSession(str(TEST_CPP_ELF))
    gdb_path, is_multiarch = gdb._find_gdb()
    if not gdb_path:
        return None

    env = get_subprocess_env(None)
    proc = subprocess.Popen(
        [gdb_path, "--interpreter=mi3", "--nx", "-q"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        bufsize=0,
    )
    gdb._proc = proc
    gdb._io = IoManager(
        proc.stdin,
        proc.stdout,
        proc.stderr,
        time_to_check_for_additional_output_sec=0.3,
    )
    gdb._io.get_gdb_response(timeout_sec=5.0, raise_error_on_timeout=False)

    if is_multiarch:
        gdb._write_mi("set architecture arm", timeout=5.0)

    resp = gdb._write_mi(f"file {TEST_CPP_ELF}", timeout=30.0)
    if resp is None:
        proc.terminate()
        return None

    gdb._alive = True
    return gdb


# ═══════════════════════════════════════════════════════════════════
# Test 6: C++ nm symbol extraction
# ═══════════════════════════════════════════════════════════════════


@unittest.skipUnless(HAS_NM, "arm-none-eabi-nm not found")
@unittest.skipUnless(TEST_CPP_ELF.exists(), "test_symbols_cpp.elf not built")
class TestCppNmSymbolExtraction(unittest.TestCase):
    """Test get_symbols() nm-based extraction for C++ mangled symbols."""

    @classmethod
    def setUpClass(cls):
        cls.symbols = get_symbols(str(TEST_CPP_ELF))

    def test_symbols_not_empty(self):
        self.assertGreater(len(self.symbols), 0)

    def test_mangled_namespace_function(self):
        """Mangled namespace function should be present."""
        self.assertIn("_ZN3HAL9GPIO_InitEmm", self.symbols)
        self.assertEqual(self.symbols["_ZN3HAL9GPIO_InitEmm"]["sym_type"], "function")

    def test_demangled_namespace_function(self):
        """Demangled namespace function should also be present via -C."""
        # get_symbols runs nm -C and adds demangled names
        found = [n for n in self.symbols if "HAL::GPIO_Init" in n]
        self.assertGreater(len(found), 0, "No demangled HAL::GPIO_Init found")

    def test_mangled_class_method(self):
        """Mangled class method should be present."""
        self.assertIn("_ZN12SensorDevice4initEv", self.symbols)
        self.assertEqual(
            self.symbols["_ZN12SensorDevice4initEv"]["sym_type"], "function"
        )

    def test_demangled_class_method(self):
        """Demangled class method should be present."""
        found = [n for n in self.symbols if "SensorDevice::init" in n]
        self.assertGreater(len(found), 0, "No demangled SensorDevice::init found")

    def test_destructor_variants(self):
        """C++ destructors produce D0/D1/D2 variants."""
        dtors = [n for n in self.symbols if n.startswith("_ZN12SensorDeviceD")]
        self.assertGreaterEqual(
            len(dtors), 2, f"Expected >=2 dtor variants, got {dtors}"
        )

    def test_vtable_symbol(self):
        """vtable for SensorDevice should be present."""
        self.assertIn("_ZTV12SensorDevice", self.symbols)

    def test_guard_variable(self):
        """Guard variable for static local should be present."""
        guard = [n for n in self.symbols if n.startswith("_ZGV")]
        self.assertGreater(len(guard), 0, "No guard variable found")

    def test_static_local_in_function(self):
        """Static local 'instance' inside get_singleton() should be present."""
        self.assertIn("_ZZ13get_singletonvE8instance", self.symbols)

    def test_namespace_variable(self):
        """Namespace variable HAL::gpio_state should be present."""
        self.assertIn("_ZN3HAL10gpio_stateE", self.symbols)
        self.assertEqual(self.symbols["_ZN3HAL10gpio_stateE"]["sym_type"], "variable")

    def test_static_class_member(self):
        """Static class member Point3D::instance_count should be present."""
        self.assertIn("_ZN7Point3D14instance_countE", self.symbols)
        self.assertEqual(
            self.symbols["_ZN7Point3D14instance_countE"]["sym_type"], "variable"
        )

    def test_operator_delete(self):
        """operator delete should be present."""
        self.assertIn("_ZdlPv", self.symbols)
        self.assertEqual(self.symbols["_ZdlPv"]["sym_type"], "function")

    def test_cpp_const_in_rodata(self):
        """POD const struct should be in rodata (R type)."""
        self.assertIn("g_cpp_config", self.symbols)
        self.assertEqual(self.symbols["g_cpp_config"]["sym_type"], "const")

    def test_nested_namespace_function(self):
        """Nested namespace HAL::Detail::increment should be present."""
        self.assertIn("_ZN3HAL6Detail9incrementEv", self.symbols)
        self.assertEqual(
            self.symbols["_ZN3HAL6Detail9incrementEv"]["sym_type"], "function"
        )


# ═══════════════════════════════════════════════════════════════════
# Test 7: C++ GDB symbol lookup
# ═══════════════════════════════════════════════════════════════════


@unittest.skipUnless(HAS_NM and HAS_GDB, "arm-none-eabi-nm or gdb-multiarch not found")
@unittest.skipUnless(TEST_CPP_ELF.exists(), "test_symbols_cpp.elf not built")
class TestCppGdbLookupSymbol(unittest.TestCase):
    """Test GDB lookup_symbol for C++ mangled/demangled names."""

    @classmethod
    def setUpClass(cls):
        cls.gdb = _make_cpp_gdb_session()
        if cls.gdb is None:
            raise unittest.SkipTest("Failed to start GDB session")

    @classmethod
    def tearDownClass(cls):
        if cls.gdb:
            try:
                cls.gdb.stop()
            except Exception:
                pass

    def test_mangled_namespace_function(self):
        """Lookup mangled namespace function."""
        info = self.gdb.lookup_symbol("_ZN3HAL9GPIO_InitEmm")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "function")
        self.assertGreater(info["addr"], 0)

    def test_demangled_namespace_function(self):
        """Lookup demangled namespace function via GDB."""
        info = self.gdb.lookup_symbol("HAL::GPIO_Init")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "function")

    def test_nested_namespace_function(self):
        """Lookup nested namespace function."""
        info = self.gdb.lookup_symbol("HAL::Detail::increment")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "function")

    def test_mangled_class_method(self):
        """Lookup mangled class method."""
        info = self.gdb.lookup_symbol("_ZN12SensorDevice4initEv")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "function")

    def test_demangled_class_method(self):
        """Lookup demangled class method."""
        info = self.gdb.lookup_symbol("SensorDevice::init")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "function")

    def test_namespace_variable(self):
        """Lookup namespace variable."""
        info = self.gdb.lookup_symbol("HAL::gpio_state")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "variable")
        self.assertEqual(info["size"], 4)

    def test_static_class_member(self):
        """Lookup static class member."""
        info = self.gdb.lookup_symbol("Point3D::instance_count")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "variable")
        self.assertEqual(info["size"], 4)

    def test_global_cpp_object(self):
        """Lookup global C++ object (class instance)."""
        info = self.gdb.lookup_symbol("g_sensor")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "variable")
        # SensorDevice: DeviceBase(id=4) + value(4) + config(4) = 12
        self.assertGreater(info["size"], 0)

    def test_template_instance_ringbuffer_u32(self):
        """Lookup template instantiation RingBuffer<uint32_t, 8>."""
        info = self.gdb.lookup_symbol("g_ring_u32")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "variable")
        # RingBuffer<uint32_t, 8>: data[8]*4 + head(4) + tail(4) = 40
        self.assertEqual(info["size"], 40)

    def test_template_instance_ringbuffer_u8(self):
        """Lookup template instantiation RingBuffer<uint8_t, 16>."""
        info = self.gdb.lookup_symbol("g_ring_u8")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "variable")
        # RingBuffer<uint8_t, 16>: data[16]*1 + head(4) + tail(4) = 24
        self.assertEqual(info["size"], 24)

    def test_cpp_const_struct(self):
        """Lookup POD const struct in rodata."""
        info = self.gdb.lookup_symbol("g_cpp_config")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "const")
        self.assertEqual(info["section"], ".rodata")
        # CppConfig: baud(4) + parity(1) + stop_bits(1) + padding(2) = 8
        self.assertEqual(info["size"], 8)

    def test_extern_c_function(self):
        """Lookup extern "C" function (no mangling)."""
        info = self.gdb.lookup_symbol("cpp_test_main")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "function")

    def test_vtable_symbol(self):
        """vtable lookup — GDB may or may not resolve it."""
        info = self.gdb.lookup_symbol("_ZTV12SensorDevice")
        # vtable symbols are tricky — GDB may not resolve them via
        # 'info address'. This is a known limitation.
        # We just verify it doesn't crash.
        if info is not None:
            self.assertGreater(info["addr"], 0)

    def test_guard_variable(self):
        """Guard variable lookup."""
        info = self.gdb.lookup_symbol("_ZGVZ13get_singletonvE8instance")
        # Guard variables may or may not be resolvable via GDB.
        if info is not None:
            self.assertGreater(info["addr"], 0)


# ═══════════════════════════════════════════════════════════════════
# Test 8: C++ GDB struct layout
# ═══════════════════════════════════════════════════════════════════


@unittest.skipUnless(HAS_NM and HAS_GDB, "arm-none-eabi-nm or gdb-multiarch not found")
@unittest.skipUnless(TEST_CPP_ELF.exists(), "test_symbols_cpp.elf not built")
class TestCppGdbStructLayout(unittest.TestCase):
    """Test GDB get_struct_layout for C++ class instances."""

    @classmethod
    def setUpClass(cls):
        cls.gdb = _make_cpp_gdb_session()
        if cls.gdb is None:
            raise unittest.SkipTest("Failed to start GDB session")

    @classmethod
    def tearDownClass(cls):
        if cls.gdb:
            try:
                cls.gdb.stop()
            except Exception:
                pass

    def test_simple_class_layout(self):
        """Point3D should have x, y, z members."""
        layout = self.gdb.get_struct_layout("g_cpp_point")
        self.assertIsNotNone(layout)
        names = [m["name"] for m in layout]
        self.assertIn("x", names)
        self.assertIn("y", names)
        self.assertIn("z", names)

    def test_template_class_layout(self):
        """RingBuffer<uint32_t, 8> should have data, head, tail."""
        layout = self.gdb.get_struct_layout("g_ring_u32")
        self.assertIsNotNone(layout)
        names = [m["name"] for m in layout]
        self.assertIn("head", names)
        self.assertIn("tail", names)

    def test_inherited_class_layout(self):
        """SensorDevice inherits DeviceBase — should have id, value, config."""
        layout = self.gdb.get_struct_layout("g_sensor")
        self.assertIsNotNone(layout)
        # At minimum, the derived class fields should be present
        self.assertGreaterEqual(len(layout), 2)

    def test_const_cpp_struct_layout(self):
        """Const POD struct CppConfig should have baud, parity, stop_bits."""
        layout = self.gdb.get_struct_layout("g_cpp_config")
        self.assertIsNotNone(layout)
        names = [m["name"] for m in layout]
        self.assertIn("baud", names)
        self.assertIn("parity", names)
        self.assertIn("stop_bits", names)

    def test_scalar_returns_none(self):
        """Namespace scalar variable should return None."""
        layout = self.gdb.get_struct_layout("HAL::gpio_state")
        self.assertIsNone(layout)


# ═══════════════════════════════════════════════════════════════════
# Test 9: C++ nm / GDB consistency
# ═══════════════════════════════════════════════════════════════════


@unittest.skipUnless(HAS_NM and HAS_GDB, "arm-none-eabi-nm or gdb-multiarch not found")
@unittest.skipUnless(TEST_CPP_ELF.exists(), "test_symbols_cpp.elf not built")
class TestCppNmGdbConsistency(unittest.TestCase):
    """Verify nm and GDB agree on C++ symbol types and addresses."""

    @classmethod
    def setUpClass(cls):
        cls.nm_symbols = get_symbols(str(TEST_CPP_ELF))
        cls.gdb = _make_cpp_gdb_session()
        if cls.gdb is None:
            raise unittest.SkipTest("Failed to start GDB session")

    @classmethod
    def tearDownClass(cls):
        if cls.gdb:
            try:
                cls.gdb.stop()
            except Exception:
                pass

    def test_function_address_consistency(self):
        """nm and GDB should agree on C++ function addresses."""
        mangled_funcs = [
            "_ZN3HAL9GPIO_InitEmm",
            "_ZN3HAL6Detail9incrementEv",
            "cpp_test_main",
        ]
        for name in mangled_funcs:
            with self.subTest(name=name):
                nm_info = self.nm_symbols.get(name)
                self.assertIsNotNone(nm_info, f"'{name}' not in nm symbols")
                gdb_info = self.gdb.lookup_symbol(name)
                self.assertIsNotNone(gdb_info, f"GDB lookup failed for '{name}'")
                self.assertEqual(
                    nm_info["addr"], gdb_info["addr"], f"Address mismatch for '{name}'"
                )

    def test_variable_address_consistency(self):
        """nm and GDB should agree on C++ variable addresses."""
        for name in ["_ZN3HAL10gpio_stateE", "_ZN7Point3D14instance_countE"]:
            with self.subTest(name=name):
                nm_info = self.nm_symbols.get(name)
                self.assertIsNotNone(nm_info, f"'{name}' not in nm symbols")
                gdb_info = self.gdb.lookup_symbol(name)
                self.assertIsNotNone(gdb_info, f"GDB lookup failed for '{name}'")
                self.assertEqual(
                    nm_info["addr"], gdb_info["addr"], f"Address mismatch for '{name}'"
                )

    def test_type_consistency(self):
        """nm and GDB should agree on symbol types for C++ symbols."""
        checks = [
            ("_ZN3HAL9GPIO_InitEmm", "function"),
            ("_ZN3HAL10gpio_stateE", "variable"),
            ("g_cpp_config", "const"),
            ("cpp_test_main", "function"),
        ]
        for name, expected_type in checks:
            with self.subTest(name=name):
                nm_info = self.nm_symbols.get(name)
                self.assertIsNotNone(nm_info, f"'{name}' not in nm symbols")
                self.assertEqual(
                    nm_info["sym_type"], expected_type, f"nm type mismatch for '{name}'"
                )
                gdb_info = self.gdb.lookup_symbol(name)
                self.assertIsNotNone(gdb_info, f"GDB lookup failed for '{name}'")
                self.assertEqual(
                    gdb_info["type"], expected_type, f"GDB type mismatch for '{name}'"
                )


if __name__ == "__main__":
    unittest.main()
