#!/usr/bin/env python3

"""Tests for ELF memory region parsing (core/elf_utils.get_memory_regions)."""

import os
import struct
import tempfile
import unittest

from fpbinject.core.elf_utils import (
    get_memory_regions,
    _merge_regions,
    _REGION_MARGIN,
)


def _build_elf32(phdrs):
    """Build a minimal 32-bit ELF with given program headers.

    Args:
        phdrs: list of (p_type, p_vaddr, p_memsz) tuples

    Returns:
        bytes of the ELF file
    """
    # ELF32 header = 52 bytes, Phdr = 32 bytes each
    e_phoff = 52
    e_phentsize = 32
    e_phnum = len(phdrs)

    # e_ident (16 bytes)
    e_ident = b"\x7fELF"  # magic
    e_ident += struct.pack("B", 1)  # EI_CLASS = ELFCLASS32
    e_ident += struct.pack("B", 1)  # EI_DATA = little-endian
    e_ident += struct.pack("B", 1)  # EI_VERSION
    e_ident += b"\x00" * 9  # padding

    # Rest of ELF32 header (36 bytes after e_ident)
    header = struct.pack(
        "<HHIIIIIHHHHHH",
        2,  # e_type = ET_EXEC
        40,  # e_machine = ARM
        1,  # e_version
        0,  # e_entry
        e_phoff,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        52,  # e_ehsize
        e_phentsize,  # e_phentsize
        e_phnum,  # e_phnum
        0,  # e_shentsize
        0,  # e_shnum
        0,  # e_shstrndx
    )

    data = e_ident + header

    # Program headers
    for p_type, p_vaddr, p_memsz in phdrs:
        phdr = struct.pack(
            "<IIIIIIII",
            p_type,  # p_type
            0,  # p_offset
            p_vaddr,  # p_vaddr
            p_vaddr,  # p_paddr
            0,  # p_filesz
            p_memsz,  # p_memsz
            5,  # p_flags (R+X)
            0x1000,  # p_align
        )
        data += phdr

    return data


def _build_elf64(phdrs):
    """Build a minimal 64-bit ELF with given program headers.

    Args:
        phdrs: list of (p_type, p_vaddr, p_memsz) tuples

    Returns:
        bytes of the ELF file
    """
    # ELF64 header = 64 bytes, Phdr = 56 bytes each
    e_phoff = 64
    e_phentsize = 56
    e_phnum = len(phdrs)

    # e_ident (16 bytes)
    e_ident = b"\x7fELF"
    e_ident += struct.pack("B", 2)  # EI_CLASS = ELFCLASS64
    e_ident += struct.pack("B", 1)  # EI_DATA = little-endian
    e_ident += struct.pack("B", 1)  # EI_VERSION
    e_ident += b"\x00" * 9

    # Rest of ELF64 header (48 bytes after e_ident)
    header = struct.pack(
        "<HHIQQQIHHHHHH",
        2,  # e_type
        183,  # e_machine = AARCH64
        1,  # e_version
        0,  # e_entry
        e_phoff,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        64,  # e_ehsize
        e_phentsize,  # e_phentsize
        e_phnum,  # e_phnum
        0,  # e_shentsize
        0,  # e_shnum
        0,  # e_shstrndx
    )

    data = e_ident + header

    # Program headers (ELF64)
    for p_type, p_vaddr, p_memsz in phdrs:
        phdr = struct.pack(
            "<IIQQQQQQ",
            p_type,  # p_type
            5,  # p_flags (R+X)
            0,  # p_offset
            p_vaddr,  # p_vaddr
            p_vaddr,  # p_paddr
            0,  # p_filesz
            p_memsz,  # p_memsz
            0x1000,  # p_align
        )
        data += phdr

    return data


def _write_temp_elf(data):
    """Write bytes to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".elf")
    os.write(fd, data)
    os.close(fd)
    return path


# PT_LOAD = 1
PT_LOAD = 1
PT_NOTE = 4
PT_GNU_STACK = 0x6474E551


class TestMergeRegions(unittest.TestCase):
    """Test _merge_regions helper."""

    def test_empty(self):
        self.assertEqual(_merge_regions([]), [])

    def test_single_region(self):
        result = _merge_regions([(0x08000000, 0x08010000)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 0x08000000 - _REGION_MARGIN)
        self.assertEqual(result[0][1], 0x08010000 + _REGION_MARGIN)

    def test_non_overlapping(self):
        regions = [(0x08000000, 0x08100000), (0x20000000, 0x20050000)]
        result = _merge_regions(regions)
        self.assertEqual(len(result), 2)

    def test_overlapping_merged(self):
        regions = [(0x08000000, 0x08010000), (0x08008000, 0x08020000)]
        result = _merge_regions(regions)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 0x08000000 - _REGION_MARGIN)
        self.assertEqual(result[0][1], 0x08020000 + _REGION_MARGIN)

    def test_adjacent_merged(self):
        # Two regions close enough that margin makes them overlap
        gap = _REGION_MARGIN  # exactly at margin boundary
        regions = [(0x08000000, 0x08010000), (0x08010000 + gap, 0x08020000)]
        result = _merge_regions(regions)
        self.assertEqual(len(result), 1)

    def test_unsorted_input(self):
        regions = [(0x20000000, 0x20010000), (0x08000000, 0x08010000)]
        result = _merge_regions(regions)
        # Should be sorted by start address
        self.assertLess(result[0][0], result[1][0])

    def test_zero_margin(self):
        regions = [(0x1000, 0x2000), (0x3000, 0x4000)]
        result = _merge_regions(regions, margin=0)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], (0x1000, 0x2000))
        self.assertEqual(result[1], (0x3000, 0x4000))

    def test_clamp_to_zero(self):
        # Region near address 0 should not underflow
        regions = [(0x100, 0x1000)]
        result = _merge_regions(regions)
        self.assertEqual(result[0][0], 0)


class TestGetMemoryRegionsELF32(unittest.TestCase):
    """Test get_memory_regions with 32-bit ELF files."""

    def test_typical_cortex_m(self):
        """Typical Cortex-M: Flash + SRAM."""
        elf = _build_elf32(
            [
                (PT_LOAD, 0x08000000, 0x001A3C00),  # Flash .text
                (PT_LOAD, 0x20000000, 0x0005A800),  # SRAM .data/.bss
            ]
        )
        path = _write_temp_elf(elf)
        try:
            regions = get_memory_regions(path)
            self.assertEqual(len(regions), 2)
            # Flash region
            self.assertLessEqual(regions[0][0], 0x08000000)
            self.assertGreaterEqual(regions[0][1], 0x08000000 + 0x001A3C00)
            # SRAM region
            self.assertLessEqual(regions[1][0], 0x20000000)
            self.assertGreaterEqual(regions[1][1], 0x20000000 + 0x0005A800)
        finally:
            os.unlink(path)

    def test_single_segment(self):
        elf = _build_elf32([(PT_LOAD, 0x00000000, 0x10000)])
        path = _write_temp_elf(elf)
        try:
            regions = get_memory_regions(path)
            self.assertEqual(len(regions), 1)
        finally:
            os.unlink(path)

    def test_no_pt_load(self):
        """ELF with only non-LOAD segments returns empty."""
        elf = _build_elf32(
            [
                (PT_NOTE, 0x08000000, 0x100),
                (PT_GNU_STACK, 0x00000000, 0x00),
            ]
        )
        path = _write_temp_elf(elf)
        try:
            regions = get_memory_regions(path)
            self.assertEqual(regions, [])
        finally:
            os.unlink(path)

    def test_zero_memsz_skipped(self):
        """PT_LOAD with memsz=0 should be skipped."""
        elf = _build_elf32(
            [
                (PT_LOAD, 0x08000000, 0),
                (PT_LOAD, 0x20000000, 0x10000),
            ]
        )
        path = _write_temp_elf(elf)
        try:
            regions = get_memory_regions(path)
            self.assertEqual(len(regions), 1)
            self.assertLessEqual(regions[0][0], 0x20000000)
        finally:
            os.unlink(path)

    def test_mixed_segment_types(self):
        """Only PT_LOAD segments are extracted."""
        elf = _build_elf32(
            [
                (PT_LOAD, 0x08000000, 0x100000),
                (PT_NOTE, 0x08100000, 0x20),
                (PT_LOAD, 0x20000000, 0x40000),
                (PT_GNU_STACK, 0x00000000, 0x00),
            ]
        )
        path = _write_temp_elf(elf)
        try:
            regions = get_memory_regions(path)
            self.assertEqual(len(regions), 2)
        finally:
            os.unlink(path)

    def test_no_program_headers(self):
        elf = _build_elf32([])
        path = _write_temp_elf(elf)
        try:
            regions = get_memory_regions(path)
            self.assertEqual(regions, [])
        finally:
            os.unlink(path)


class TestGetMemoryRegionsELF64(unittest.TestCase):
    """Test get_memory_regions with 64-bit ELF files."""

    def test_basic_64bit(self):
        elf = _build_elf64(
            [
                (PT_LOAD, 0x00400000, 0x100000),
                (PT_LOAD, 0x00600000, 0x50000),
            ]
        )
        path = _write_temp_elf(elf)
        try:
            regions = get_memory_regions(path)
            self.assertGreaterEqual(len(regions), 1)
            # Both should be present (may merge if close)
            self.assertLessEqual(regions[0][0], 0x00400000)
        finally:
            os.unlink(path)


class TestGetMemoryRegionsFixtureELF(unittest.TestCase):
    """Test get_memory_regions with real compiled fixture ELF files."""

    FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

    def test_fixture_test_func_elf(self):
        """Parse real ARM Cortex-M ELF: test_func.elf (Flash .text + SRAM .bss)."""
        path = os.path.join(self.FIXTURES_DIR, "test_func.elf")
        if not os.path.exists(path):
            self.skipTest("Fixture test_func.elf not found")

        regions = get_memory_regions(path)
        self.assertGreater(len(regions), 0)

        # Should contain Flash region around 0x08000000
        flash_found = any(
            start <= 0x08000000 and end > 0x08000000 for start, end in regions
        )
        self.assertTrue(
            flash_found, f"Expected Flash region near 0x08000000, got {regions}"
        )

    def test_fixture_test_symbols_elf(self):
        """Parse real ARM ELF: test_symbols.elf."""
        path = os.path.join(self.FIXTURES_DIR, "test_symbols.elf")
        if not os.path.exists(path):
            self.skipTest("Fixture test_symbols.elf not found")

        regions = get_memory_regions(path)
        self.assertGreater(len(regions), 0)


class TestGetMemoryRegionsEdgeCases(unittest.TestCase):
    """Test error handling and edge cases."""

    def test_not_elf(self):
        fd, path = tempfile.mkstemp()
        os.write(fd, b"This is not an ELF file at all")
        os.close(fd)
        try:
            regions = get_memory_regions(path)
            self.assertEqual(regions, [])
        finally:
            os.unlink(path)

    def test_truncated_elf(self):
        fd, path = tempfile.mkstemp()
        os.write(fd, b"\x7fELF\x01")  # Valid magic + class but truncated
        os.close(fd)
        try:
            regions = get_memory_regions(path)
            self.assertEqual(regions, [])
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        regions = get_memory_regions("/nonexistent/path/firmware.elf")
        self.assertEqual(regions, [])

    def test_unknown_elf_class(self):
        data = b"\x7fELF\x03"  # class = 3 (invalid)
        data += b"\x00" * 11  # rest of e_ident
        fd, path = tempfile.mkstemp()
        os.write(fd, data)
        os.close(fd)
        try:
            regions = get_memory_regions(path)
            self.assertEqual(regions, [])
        finally:
            os.unlink(path)

    def test_empty_file(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            regions = get_memory_regions(path)
            self.assertEqual(regions, [])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
