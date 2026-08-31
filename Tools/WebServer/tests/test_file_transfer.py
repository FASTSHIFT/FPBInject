#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Tests for core/file_transfer.py (unittest format)
"""

import base64
import os
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpbinject.core.file_transfer import FileTransfer  # noqa: E402
from fpbinject.utils.crc import crc16  # noqa: E402


class TestCRC16(unittest.TestCase):
    """Tests for CRC-16 calculation."""

    def test_empty_data(self):
        """Test CRC of empty data."""
        self.assertEqual(crc16(b""), 0xFFFF)

    def test_known_value(self):
        """Test CRC with known value."""
        data = b"123456789"
        crc = crc16(data)
        self.assertIsInstance(crc, int)
        self.assertGreaterEqual(crc, 0)
        self.assertLessEqual(crc, 0xFFFF)

    def test_single_byte(self):
        """Test CRC of single byte."""
        crc = crc16(b"\x00")
        self.assertIsInstance(crc, int)

    def test_consistency(self):
        """Test CRC is consistent for same data."""
        data = b"test data"
        crc1 = crc16(data)
        crc2 = crc16(data)
        self.assertEqual(crc1, crc2)

    def test_different_data_different_crc(self):
        """Test different data produces different CRC."""
        crc1 = crc16(b"hello")
        crc2 = crc16(b"world")
        self.assertNotEqual(crc1, crc2)

    def test_large_data(self):
        """Test CRC with large data."""
        data = b"x" * 10000
        crc = crc16(data)
        self.assertIsInstance(crc, int)
        self.assertGreaterEqual(crc, 0)
        self.assertLessEqual(crc, 0xFFFF)


class TestFileTransferInit(unittest.TestCase):
    """Tests for FileTransfer initialization."""

    def setUp(self):
        """Set up mock FPB."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))

    def test_init(self):
        """Test FileTransfer initialization."""
        ft = FileTransfer(self.mock_fpb, upload_chunk_size=128, download_chunk_size=128)
        self.assertEqual(ft.fpb, self.mock_fpb)
        self.assertEqual(ft.upload_chunk_size, 128)

    def test_init_default_chunk_size(self):
        """Test default chunk size."""
        ft = FileTransfer(self.mock_fpb)
        self.assertEqual(ft.upload_chunk_size, FileTransfer.DEFAULT_UPLOAD_CHUNK_SIZE)


class TestFileTransferBasicOps(unittest.TestCase):
    """Tests for FileTransfer basic operations."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_fopen_success(self):
        """Test successful file open."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FOPEN /test.txt mode=w")
        success, msg = self.ft.fopen("/test.txt", "w")
        self.assertTrue(success)
        self.assertIn("FOPEN", msg)
        self.mock_fpb.send_fl_cmd.assert_called_once()

    def test_fopen_failure(self):
        """Test file open failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] File not found")
        success, msg = self.ft.fopen("/nonexistent.txt", "r")
        self.assertFalse(success)

    def test_fopen_read_mode(self):
        """Test file open in read mode."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FOPEN /test.txt mode=r")
        success, msg = self.ft.fopen("/test.txt", "r")
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("-m r", call_args)

    def test_fopen_append_mode(self):
        """Test file open in append mode."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FOPEN /test.txt mode=a")
        success, msg = self.ft.fopen("/test.txt", "a")
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("-m a", call_args)

    def test_fwrite_success(self):
        """Test successful file write."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FWRITE 10 bytes")
        data = b"test data!"
        success, msg = self.ft.fwrite(data)
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("-d", call_args)
        self.assertIn("-r", call_args)

    def test_fwrite_empty_data(self):
        """Test write with empty data."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FWRITE 0 bytes")
        success, msg = self.ft.fwrite(b"")
        self.assertTrue(success)

    def test_fwrite_failure(self):
        """Test write failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] Disk full")
        success, msg = self.ft.fwrite(b"test")
        self.assertFalse(success)

    def test_fclose_success(self):
        """Test successful file close."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FCLOSE")
        success, msg = self.ft.fclose()
        self.assertTrue(success)

    def test_fclose_failure(self):
        """Test close failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] No file open")
        success, msg = self.ft.fclose()
        self.assertFalse(success)


class TestFileTransferRead(unittest.TestCase):
    """Tests for FileTransfer read operations."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_fread_success(self):
        """Test successful file read."""
        test_data = b"hello world"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
        )
        success, data, msg = self.ft.fread(256)
        self.assertTrue(success)
        self.assertEqual(data, test_data)

    def test_fread_eof(self):
        """Test read at EOF."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FREAD 0 bytes EOF")
        success, data, msg = self.ft.fread(256)
        self.assertTrue(success)
        self.assertEqual(data, b"")
        self.assertEqual(msg, "EOF")

    def test_fread_crc_mismatch(self):
        """Test read with CRC mismatch."""
        test_data = b"hello world"
        b64_data = base64.b64encode(test_data).decode("ascii")
        wrong_crc = 0x1234
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            f"[FLOK] FREAD {len(test_data)} bytes crc=0x{wrong_crc:04X} data={b64_data}",
        )
        success, data, msg = self.ft.fread(256)
        self.assertFalse(success)
        self.assertIn("CRC mismatch", msg)

    def test_fread_failure(self):
        """Test read failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] Read failed")
        success, data, msg = self.ft.fread(256)
        self.assertFalse(success)
        self.assertEqual(data, b"")

    def test_fread_invalid_response(self):
        """Test read with invalid response format."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] Invalid response")
        success, data, msg = self.ft.fread(256)
        self.assertFalse(success)
        self.assertIn("Invalid response", msg)

    def test_fread_no_data_in_response(self):
        """Test read with missing data in response."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FREAD 10 bytes crc=0x1234",
        )
        success, data, msg = self.ft.fread(256)
        self.assertFalse(success)
        self.assertIn("No data", msg)

    def test_fread_base64_decode_error(self):
        """Test read with invalid base64 data."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FREAD 10 bytes crc=0x1234 data=!!!invalid!!!",
        )
        success, data, msg = self.ft.fread(256)
        self.assertFalse(success)
        self.assertIn("decode error", msg.lower())


class TestFileTransferStat(unittest.TestCase):
    """Tests for FileTransfer stat operations."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_fstat_success(self):
        """Test successful file stat."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FSTAT /test.txt size=1024 mtime=1234567890 type=file",
        )
        success, stat = self.ft.fstat("/test.txt")
        self.assertTrue(success)
        self.assertEqual(stat["size"], 1024)
        self.assertEqual(stat["mtime"], 1234567890)
        self.assertEqual(stat["type"], "file")

    def test_fstat_directory(self):
        """Test stat on directory."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FSTAT /data size=0 mtime=1234567890 type=dir",
        )
        success, stat = self.ft.fstat("/data")
        self.assertTrue(success)
        self.assertEqual(stat["type"], "dir")

    def test_fstat_failure(self):
        """Test stat failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] File not found")
        success, stat = self.ft.fstat("/nonexistent")
        self.assertFalse(success)
        self.assertIn("error", stat)

    def test_fstat_invalid_response(self):
        """Test stat with invalid response format."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] Invalid response")
        success, stat = self.ft.fstat("/test.txt")
        self.assertFalse(success)
        self.assertIn("error", stat)


class TestFileTransferList(unittest.TestCase):
    """Tests for FileTransfer list operations."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_flist_success(self):
        """Test successful directory listing."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FLIST dir=1 file=2\n  D subdir\n  F test.txt 100\n  F data.bin 256",
        )
        success, entries = self.ft.flist("/data")
        self.assertTrue(success)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["name"], "subdir")
        self.assertEqual(entries[0]["type"], "dir")
        self.assertEqual(entries[1]["name"], "test.txt")
        self.assertEqual(entries[1]["type"], "file")
        self.assertEqual(entries[1]["size"], 100)

    def test_flist_empty(self):
        """Test listing empty directory."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FLIST dir=0 file=0")
        success, entries = self.ft.flist("/empty")
        self.assertTrue(success)
        self.assertEqual(len(entries), 0)

    def test_flist_failure(self):
        """Test listing failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] Not a directory")
        success, entries = self.ft.flist("/test.txt")
        self.assertFalse(success)
        self.assertEqual(entries, [])

    def test_flist_file_without_size(self):
        """Test listing with file entry without size."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FLIST\n  F nosize",
        )
        success, entries = self.ft.flist("/data")
        self.assertTrue(success)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["name"], "nosize")
        self.assertEqual(entries[0]["size"], 0)

    def test_flist_file_invalid_size(self):
        """Test listing with file entry with invalid size."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FLIST\n  F test.txt abc",
        )
        success, entries = self.ft.flist("/data")
        self.assertTrue(success)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["size"], 0)


class TestFileTransferRemoveMkdir(unittest.TestCase):
    """Tests for FileTransfer remove and mkdir operations."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_fremove_success(self):
        """Test successful file removal."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FREMOVE /test.txt")
        success, msg = self.ft.fremove("/test.txt")
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("-r 0x", call_args)

    def test_fremove_failure(self):
        """Test removal failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] Permission denied")
        success, msg = self.ft.fremove("/protected.txt")
        self.assertFalse(success)

    def test_fmkdir_success(self):
        """Test successful directory creation."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FMKDIR /newdir")
        success, msg = self.ft.fmkdir("/newdir")
        self.assertTrue(success)

    def test_fmkdir_failure(self):
        """Test directory creation failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] Already exists")
        success, msg = self.ft.fmkdir("/existing")
        self.assertFalse(success)

    def test_frename_success(self):
        """Test successful file rename."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FRENAME /old.txt -> /new.txt",
        )
        success, msg = self.ft.frename("/old.txt", "/new.txt")
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("--path /old.txt", call_args)
        self.assertIn("--newpath /new.txt", call_args)
        self.assertIn("-r 0x", call_args)

    def test_frename_failure(self):
        """Test rename failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] File not found")
        success, msg = self.ft.frename("/nonexistent.txt", "/new.txt")
        self.assertFalse(success)


class TestFileTransferCRC(unittest.TestCase):
    """Tests for FileTransfer fcrc operations."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_fcrc_success(self):
        """Test successful fcrc."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FCRC offset=0 size=1024 crc=0xABCD",
        )
        success, size, crc_val = self.ft.fcrc(1024)
        self.assertTrue(success)
        self.assertEqual(size, 1024)
        self.assertEqual(crc_val, 0xABCD)

    def test_fcrc_with_size(self):
        """Test fcrc with specific size."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FCRC offset=0 size=512 crc=0x1234",
        )
        success, size, crc_val = self.ft.fcrc(512)
        self.assertTrue(success)
        self.assertEqual(size, 512)
        self.assertEqual(crc_val, 0x1234)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("-l 512", call_args)

    def test_fcrc_failure(self):
        """Test fcrc failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] No file open")
        success, size, crc_val = self.ft.fcrc()
        self.assertFalse(success)
        self.assertEqual(size, 0)
        self.assertEqual(crc_val, 0)

    def test_fcrc_invalid_response(self):
        """Test fcrc with invalid response format."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] Invalid response")
        success, size, crc_val = self.ft.fcrc()
        self.assertFalse(success)
        self.assertEqual(size, 0)
        self.assertEqual(crc_val, 0)


class TestFileTransferUpload(unittest.TestCase):
    """Tests for FileTransfer upload operations."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_upload_success(self):
        """Test successful file upload with CRC verification."""
        data = b"x" * 300
        expected_crc = crc16(data)
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),  # fopen write
            (True, "[FLOK] FWRITE 256 bytes"),
            (True, "[FLOK] FWRITE 44 bytes"),
            (True, "[FLOK] FCLOSE"),  # fclose after write
            (True, "[FLOK] FOPEN /test.txt mode=r"),  # fopen read for CRC
            (True, f"[FLOK] FCRC offset=0 size=300 crc=0x{expected_crc:04X}"),
            (True, "[FLOK] FCLOSE"),  # fclose after CRC
        ]
        progress_calls = []

        def progress_cb(uploaded, total):
            progress_calls.append((uploaded, total))

        success, msg = self.ft.upload(data, "/test.txt", progress_cb)
        self.assertTrue(success)
        self.assertEqual(len(progress_calls), 2)

    def test_upload_success_without_crc_verify(self):
        """Test successful file upload with CRC verification warning."""
        data = b"x" * 300
        expected_crc = crc16(data)
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),
            (True, "[FLOK] FWRITE 256 bytes"),
            (True, "[FLOK] FWRITE 44 bytes"),
            (True, "[FLOK] FCLOSE"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size=300 crc=0x{expected_crc:04X}"),
            (True, "[FLOK] FCLOSE"),
        ]
        success, msg = self.ft.upload(data, "/test.txt")
        self.assertTrue(success)

    def test_upload_crc_mismatch(self):
        """Test upload fails on CRC mismatch."""
        data = b"x" * 100
        wrong_crc = 0x1234
        # max_retries=0 so whole-file verification runs exactly once.
        self.ft.max_retries = 0
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),
            (True, "[FLOK] FWRITE 100 bytes"),
            (True, "[FLOK] FCLOSE"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size=100 crc=0x{wrong_crc:04X}"),
            (True, "[FLOK] FCLOSE"),
        ]
        success, msg = self.ft.upload(data, "/test.txt")
        self.assertFalse(success)
        self.assertIn("CRC mismatch", msg)

    def test_upload_size_mismatch(self):
        """Test upload fails on size mismatch."""
        data = b"x" * 100
        expected_crc = crc16(data)
        # max_retries=0 so whole-file verification runs exactly once.
        self.ft.max_retries = 0
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),
            (True, "[FLOK] FWRITE 100 bytes"),
            (True, "[FLOK] FCLOSE"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (
                True,
                f"[FLOK] FCRC offset=0 size=50 crc=0x{expected_crc:04X}",
            ),  # Wrong size
            (True, "[FLOK] FCLOSE"),
        ]
        success, msg = self.ft.upload(data, "/test.txt")
        self.assertFalse(success)
        self.assertIn("Size mismatch", msg)

    def test_upload_open_failure(self):
        """Test upload with open failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] Cannot create file")
        success, msg = self.ft.upload(b"test", "/readonly/test.txt")
        self.assertFalse(success)
        self.assertIn("Failed to open", msg)

    def test_upload_write_failure(self):
        """Test upload with write failure."""
        # Set max_retries to 3 for this test
        self.ft.max_retries = 3
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),
            (False, "[FLERR] Disk full"),  # fwrite attempt 1
            (True, "[FLOK] FSEEK"),  # fseek before retry 1
            (False, "[FLERR] Disk full"),  # fwrite retry 1
            (True, "[FLOK] FSEEK"),  # fseek before retry 2
            (False, "[FLERR] Disk full"),  # fwrite retry 2
            (True, "[FLOK] FSEEK"),  # fseek before retry 3
            (False, "[FLERR] Disk full"),  # fwrite retry 3
            (True, "[FLOK] FCLOSE"),
        ]
        success, msg = self.ft.upload(b"test data", "/test.txt")
        self.assertFalse(success)
        self.assertIn("Write failed", msg)

    def test_upload_close_failure(self):
        """Test upload with close failure."""
        data = b"test"
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),
            (True, "[FLOK] FWRITE 4 bytes"),
            (False, "[FLERR] Close failed"),  # fclose after write fails
        ]
        success, msg = self.ft.upload(data, "/test.txt")
        self.assertFalse(success)
        self.assertIn("Failed to close", msg)

    def test_upload_empty_data(self):
        """Test upload with empty data."""
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),
            (True, "[FLOK] FCLOSE"),
        ]
        success, msg = self.ft.upload(b"", "/test.txt")
        self.assertTrue(success)

    def test_upload_exception(self):
        """Test upload with exception during write."""
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),
            Exception("Connection lost"),
            (True, "[FLOK] FCLOSE"),  # fclose in exception handler
        ]
        success, msg = self.ft.upload(b"test", "/test.txt")
        self.assertFalse(success)
        self.assertIn("Upload error", msg)

    def test_upload_exception_with_close_failure(self):
        """Test upload exception handling when close also fails."""
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),
            Exception("Connection lost"),
            Exception("Close failed"),  # fclose also fails
        ]
        success, msg = self.ft.upload(b"test", "/test.txt")
        self.assertFalse(success)
        self.assertIn("Upload error", msg)

    def test_upload_no_progress_callback(self):
        """Test upload without progress callback."""
        data = b"test"
        expected_crc = crc16(data)
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),
            (True, "[FLOK] FWRITE 4 bytes"),
            (True, "[FLOK] FCLOSE"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size=4 crc=0x{expected_crc:04X}"),
            (True, "[FLOK] FCLOSE"),
        ]
        success, msg = self.ft.upload(data, "/test.txt")
        self.assertTrue(success)


class TestFileTransferDownload(unittest.TestCase):
    """Tests for FileTransfer download operations."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_download_success(self):
        """Test successful file download with CRC verification."""
        test_data = b"hello world"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)

        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, f"[FLOK] FSTAT /test.txt size={len(test_data)} mtime=123 type=file"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),  # fopen read
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
            (True, "[FLOK] FREAD 0 bytes EOF"),
            (True, "[FLOK] FCLOSE"),  # fclose after read
            (True, "[FLOK] FOPEN /test.txt mode=r"),  # fopen read for CRC
            (True, f"[FLOK] FCRC offset=0 size={len(test_data)} crc=0x{crc:04X}"),
            (True, "[FLOK] FCLOSE"),  # fclose after CRC
        ]

        progress_calls = []

        def progress_cb(downloaded, total):
            progress_calls.append((downloaded, total))

        success, data, msg = self.ft.download("/test.txt", progress_cb)
        self.assertTrue(success)
        self.assertEqual(data, test_data)
        self.assertGreaterEqual(len(progress_calls), 1)

    def test_download_success_without_crc_verify(self):
        """Test successful file download with CRC verification."""
        test_data = b"hello world"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)

        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, f"[FLOK] FSTAT /test.txt size={len(test_data)} mtime=123 type=file"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
            (True, "[FLOK] FREAD 0 bytes EOF"),
            (True, "[FLOK] FCLOSE"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size={len(test_data)} crc=0x{crc:04X}"),
            (True, "[FLOK] FCLOSE"),
        ]
        success, data, msg = self.ft.download("/test.txt")
        self.assertTrue(success)
        self.assertEqual(data, test_data)

    def test_download_aborts_on_cancel_event(self):
        """A set cancel_event must abort the download before reading data."""
        import threading

        cancel_event = threading.Event()
        cancel_event.set()  # already cancelled

        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FSTAT /test.txt size=100 mtime=1 type=file"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, "[FLOK] FCLOSE"),  # fclose on cancel
        ]
        success, data, msg = self.ft.download("/test.txt", cancel_event=cancel_event)
        self.assertFalse(success)
        self.assertEqual(data, b"")
        self.assertEqual(msg, "Cancelled")

    def test_download_completes_when_cancel_event_unset(self):
        """An unset cancel_event must not interfere with a normal download."""
        import threading

        cancel_event = threading.Event()  # not set
        test_data = b"hello world"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, f"[FLOK] FSTAT /test.txt size={len(test_data)} mtime=1 type=file"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
            (True, "[FLOK] FREAD 0 bytes EOF"),
            (True, "[FLOK] FCLOSE"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size={len(test_data)} crc=0x{crc:04X}"),
            (True, "[FLOK] FCLOSE"),
        ]
        success, data, msg = self.ft.download("/test.txt", cancel_event=cancel_event)
        self.assertTrue(success)
        self.assertEqual(data, test_data)

    def test_download_crc_mismatch(self):
        """Test download fails on CRC mismatch."""
        test_data = b"hello world"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)
        wrong_crc = 0x1234

        # max_retries=0 so whole-file verification runs exactly once.
        self.ft.max_retries = 0
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, f"[FLOK] FSTAT /test.txt size={len(test_data)} mtime=123 type=file"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
            (True, "[FLOK] FREAD 0 bytes EOF"),
            (True, "[FLOK] FCLOSE"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size={len(test_data)} crc=0x{wrong_crc:04X}"),
            (True, "[FLOK] FCLOSE"),
        ]
        success, data, msg = self.ft.download("/test.txt")
        self.assertFalse(success)
        self.assertIn("CRC mismatch", msg)

    def test_download_stat_failure(self):
        """Test download with stat failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] File not found")
        success, data, msg = self.ft.download("/nonexistent.txt")
        self.assertFalse(success)
        self.assertEqual(data, b"")

    def test_download_directory(self):
        """Test download of directory (should fail)."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FSTAT /data size=0 mtime=123 type=dir",
        )
        success, data, msg = self.ft.download("/data")
        self.assertFalse(success)
        self.assertIn("Cannot download directory", msg)

    def test_download_open_failure(self):
        """Test download with open failure."""
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FSTAT /test.txt size=100 mtime=123 type=file"),
            (False, "[FLERR] Cannot open file"),
        ]
        success, data, msg = self.ft.download("/test.txt")
        self.assertFalse(success)
        self.assertIn("Failed to open", msg)

    def test_download_read_failure(self):
        """Test download with read failure."""
        # Set max_retries to 3 for this test
        self.ft.max_retries = 3
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FSTAT /test.txt size=100 mtime=123 type=file"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (False, "[FLERR] Read error"),  # fread attempt 1
            (True, "[FLOK] FSEEK"),  # fseek before retry 1
            (False, "[FLERR] Read error"),  # fread retry 1
            (True, "[FLOK] FSEEK"),  # fseek before retry 2
            (False, "[FLERR] Read error"),  # fread retry 2
            (True, "[FLOK] FSEEK"),  # fseek before retry 3
            (False, "[FLERR] Read error"),  # fread retry 3
            (True, "[FLOK] FCLOSE"),
        ]
        success, data, msg = self.ft.download("/test.txt")
        self.assertFalse(success)
        self.assertIn("Read failed", msg)

    def test_download_exception(self):
        """Test download with exception during read."""
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FSTAT /test.txt size=100 mtime=123 type=file"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            Exception("Connection lost"),
            (True, "[FLOK] FCLOSE"),  # fclose in exception handler
        ]
        success, data, msg = self.ft.download("/test.txt")
        self.assertFalse(success)
        self.assertIn("Download error", msg)

    def test_download_exception_with_close_failure(self):
        """Test download exception handling when close also fails."""
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FSTAT /test.txt size=100 mtime=123 type=file"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            Exception("Connection lost"),
            Exception("Close failed"),  # fclose also fails
        ]
        success, data, msg = self.ft.download("/test.txt")
        self.assertFalse(success)
        self.assertIn("Download error", msg)

    def test_download_close_failure(self):
        """Test download with close failure after successful read."""
        test_data = b"hello"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)

        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, f"[FLOK] FSTAT /test.txt size={len(test_data)} mtime=123 type=file"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
            (True, "[FLOK] FREAD 0 bytes EOF"),
            (False, "[FLERR] Close failed"),  # fclose after read fails
        ]
        success, data, msg = self.ft.download("/test.txt")
        self.assertFalse(success)
        self.assertIn("Failed to close", msg)

    def test_download_no_progress_callback(self):
        """Test download without progress callback."""
        test_data = b"hello"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)

        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, f"[FLOK] FSTAT /test.txt size={len(test_data)} mtime=123 type=file"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
            (True, "[FLOK] FREAD 0 bytes EOF"),
            (True, "[FLOK] FCLOSE"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size={len(test_data)} crc=0x{crc:04X}"),
            (True, "[FLOK] FCLOSE"),
        ]
        success, data, msg = self.ft.download("/test.txt")
        self.assertTrue(success)
        self.assertEqual(data, test_data)


class TestFileTransferIntegration(unittest.TestCase):
    """Integration-style tests for FileTransfer."""

    def test_upload_download_roundtrip(self):
        """Test upload then download returns same data."""
        mock_fpb = Mock()
        ft = FileTransfer(mock_fpb, upload_chunk_size=256, download_chunk_size=256)

        original_data = b"Test file content for roundtrip"
        b64_data = base64.b64encode(original_data).decode("ascii")
        crc = crc16(original_data)

        # Upload: fopen(w) → fwrite → fclose → fopen(r) → fcrc → fclose
        mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),
            (True, f"[FLOK] FWRITE {len(original_data)} bytes"),
            (True, "[FLOK] FCLOSE"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size={len(original_data)} crc=0x{crc:04X}"),
            (True, "[FLOK] FCLOSE"),
        ]
        success, _ = ft.upload(original_data, "/test.txt")
        self.assertTrue(success)

        # Download: fstat → fopen(r) → fread → fclose → fopen(r) → fcrc → fclose
        mock_fpb.send_fl_cmd.side_effect = [
            (
                True,
                f"[FLOK] FSTAT /test.txt size={len(original_data)} mtime=123 type=file",
            ),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (
                True,
                f"[FLOK] FREAD {len(original_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
            (True, "[FLOK] FREAD 0 bytes EOF"),
            (True, "[FLOK] FCLOSE"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size={len(original_data)} crc=0x{crc:04X}"),
            (True, "[FLOK] FCLOSE"),
        ]
        success, downloaded_data, _ = ft.download("/test.txt")
        self.assertTrue(success)
        self.assertEqual(downloaded_data, original_data)


class TestSendCmd(unittest.TestCase):
    """Tests for _send_cmd method."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_send_cmd_with_timeout(self):
        """Test _send_cmd passes timeout correctly."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK]")
        self.ft._send_cmd("test cmd", timeout=5.0)
        self.mock_fpb.send_fl_cmd.assert_called_once_with(
            "test cmd", timeout=5.0, max_retries=3
        )

    def test_send_cmd_default_timeout(self):
        """Test _send_cmd uses default timeout."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK]")
        self.ft._send_cmd("test cmd")
        self.mock_fpb.send_fl_cmd.assert_called_once_with(
            "test cmd", timeout=2.0, max_retries=3
        )

    def test_send_cmd_no_protocol_retry(self):
        """Test _send_cmd with no_protocol_retry=True."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK]")
        self.ft._send_cmd("test cmd", no_protocol_retry=True)
        self.mock_fpb.send_fl_cmd.assert_called_once_with(
            "test cmd", timeout=2.0, max_retries=0
        )


class TestFileTransferRetry(unittest.TestCase):
    """Tests for FileTransfer retry functionality."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )
        self.ft.max_retries = 3

    def test_fwrite_retry_on_crc_mismatch(self):
        """Test fwrite retries on CRC mismatch."""
        self.mock_fpb.send_fl_cmd.side_effect = [
            (False, "[FLERR] CRC mismatch: 0x1234 != 0x5678"),
            (False, "[FLERR] CRC mismatch: 0x1234 != 0x5678"),
            (True, "[FLOK] FWRITE 10 bytes"),
        ]
        success, msg = self.ft.fwrite(b"test data!")
        self.assertTrue(success)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 3)

    def test_fwrite_max_retries_exceeded(self):
        """Test fwrite fails after max retries."""
        self.mock_fpb.send_fl_cmd.return_value = (
            False,
            "[FLERR] CRC mismatch: 0x1234 != 0x5678",
        )
        success, msg = self.ft.fwrite(b"test data!")
        self.assertFalse(success)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 4)  # 1 + 3 retries

    def test_fwrite_no_retry_on_other_error(self):
        """Test fwrite retries on non-CRC errors too (all errors are retried)."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] Disk full")
        success, msg = self.ft.fwrite(b"test data!")
        self.assertFalse(success)
        # All errors are retried: 1 initial + 3 retries = 4 calls
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 4)

    def test_fread_retry_on_crc_mismatch(self):
        """Test fread retries on CRC mismatch."""
        test_data = b"hello world"
        b64_data = base64.b64encode(test_data).decode("ascii")
        correct_crc = crc16(test_data)
        wrong_crc = 0x1234

        self.mock_fpb.send_fl_cmd.side_effect = [
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{wrong_crc:04X} data={b64_data}",
            ),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{wrong_crc:04X} data={b64_data}",
            ),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{correct_crc:04X} data={b64_data}",
            ),
        ]
        success, data, msg = self.ft.fread(256)
        self.assertTrue(success)
        self.assertEqual(data, test_data)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 3)

    def test_fread_retry_on_base64_error(self):
        """Test fread retries on base64 decode error."""
        test_data = b"hello world"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)

        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FREAD 10 bytes crc=0x1234 data=!!!invalid!!!"),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
        ]
        success, data, msg = self.ft.fread(256)
        self.assertTrue(success)
        self.assertEqual(data, test_data)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 2)

    def test_fread_retry_on_invalid_response(self):
        """Test fread retries on invalid response format."""
        test_data = b"hello world"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)

        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] Invalid response format"),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
        ]
        success, data, msg = self.ft.fread(256)
        self.assertTrue(success)
        self.assertEqual(data, test_data)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 2)

    def test_fread_retry_on_failure(self):
        """Test fread retries on command failure."""
        test_data = b"hello world"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)

        self.mock_fpb.send_fl_cmd.side_effect = [
            (False, "[FLERR] Timeout"),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
        ]
        success, data, msg = self.ft.fread(256)
        self.assertTrue(success)
        self.assertEqual(data, test_data)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 2)

    def test_fread_max_retries_exceeded(self):
        """Test fread fails after max retries."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] Timeout")
        success, data, msg = self.ft.fread(256)
        self.assertFalse(success)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 4)  # 1 + 3 retries

    def test_fread_uses_download_chunk_size_as_default(self):
        """Test fread uses download_chunk_size as default read size."""
        test_data = b"hello"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)

        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
        )
        self.ft.fread()  # No size argument
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("-l 256", call_args)  # download_chunk_size is 256

    def test_fwrite_custom_max_retries(self):
        """Test fwrite with custom max_retries."""
        self.mock_fpb.send_fl_cmd.return_value = (
            False,
            "[FLERR] CRC mismatch: 0x1234 != 0x5678",
        )
        success, msg = self.ft.fwrite(b"test", max_retries=1)
        self.assertFalse(success)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 2)  # 1 + 1 retry

    def test_fread_custom_max_retries(self):
        """Test fread with custom max_retries."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] Timeout")
        success, data, msg = self.ft.fread(256, max_retries=1)
        self.assertFalse(success)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 2)  # 1 + 1 retry


class TestFileTransferStats(unittest.TestCase):
    """Tests for FileTransfer statistics functionality."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_initial_stats(self):
        """Test initial stats are all zero."""
        stats = self.ft.stats
        self.assertEqual(stats["total_chunks"], 0)
        self.assertEqual(stats["retry_count"], 0)
        self.assertEqual(stats["crc_errors"], 0)
        self.assertEqual(stats["timeout_errors"], 0)
        self.assertEqual(stats["other_errors"], 0)

    def test_reset_stats(self):
        """Test reset_stats clears all counters."""
        # Modify stats
        self.ft.stats["total_chunks"] = 10
        self.ft.stats["retry_count"] = 5
        self.ft.stats["crc_errors"] = 2
        self.ft.stats["timeout_errors"] = 1
        self.ft.stats["other_errors"] = 1

        # Reset
        self.ft.reset_stats()

        # Verify all reset to zero
        self.assertEqual(self.ft.stats["total_chunks"], 0)
        self.assertEqual(self.ft.stats["retry_count"], 0)
        self.assertEqual(self.ft.stats["crc_errors"], 0)
        self.assertEqual(self.ft.stats["timeout_errors"], 0)
        self.assertEqual(self.ft.stats["other_errors"], 0)

    def test_get_stats_returns_copy(self):
        """Test get_stats returns a copy of stats."""
        self.ft.stats["total_chunks"] = 5
        stats = self.ft.get_stats()
        stats["total_chunks"] = 100
        # Original should be unchanged
        self.assertEqual(self.ft.stats["total_chunks"], 5)

    def test_get_stats_includes_packet_loss_rate(self):
        """Test get_stats calculates packet_loss_rate."""
        self.ft.stats["total_chunks"] = 10
        self.ft.stats["retry_count"] = 2
        stats = self.ft.get_stats()
        # packet_loss_rate = retries / (total + retries) * 100 = 2 / 12 * 100 = 16.67
        self.assertIn("packet_loss_rate", stats)
        self.assertAlmostEqual(stats["packet_loss_rate"], 16.67, places=2)

    def test_get_stats_zero_total_chunks(self):
        """Test get_stats with zero total_chunks returns 0 packet_loss_rate."""
        self.ft.stats["total_chunks"] = 0
        self.ft.stats["retry_count"] = 0
        stats = self.ft.get_stats()
        self.assertEqual(stats["packet_loss_rate"], 0.0)

    def test_fwrite_increments_total_chunks(self):
        """Test fwrite increments total_chunks counter."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FWRITE 10 bytes")
        self.ft.fwrite(b"test data!")
        self.assertEqual(self.ft.stats["total_chunks"], 1)

    def test_fread_increments_total_chunks(self):
        """Test fread increments total_chunks counter."""
        test_data = b"hello"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
        )
        self.ft.fread(256)
        self.assertEqual(self.ft.stats["total_chunks"], 1)

    def test_fwrite_retry_increments_stats(self):
        """Test fwrite retry increments retry_count and crc_errors."""
        self.mock_fpb.send_fl_cmd.side_effect = [
            (False, "[FLERR] CRC mismatch: 0x1234 != 0x5678"),
            (True, "[FLOK] FWRITE 10 bytes"),
        ]
        self.ft.fwrite(b"test data!")
        self.assertEqual(self.ft.stats["total_chunks"], 1)
        self.assertEqual(self.ft.stats["retry_count"], 1)
        self.assertEqual(self.ft.stats["crc_errors"], 1)

    def test_fread_retry_increments_timeout_errors(self):
        """Test fread retry on failure increments timeout_errors."""
        test_data = b"hello"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)
        self.mock_fpb.send_fl_cmd.side_effect = [
            (False, "[FLERR] Timeout"),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
        ]
        self.ft.fread(256)
        self.assertEqual(self.ft.stats["retry_count"], 1)
        self.assertEqual(self.ft.stats["timeout_errors"], 1)

    def test_fread_retry_increments_crc_errors(self):
        """Test fread retry on CRC mismatch increments crc_errors."""
        test_data = b"hello"
        b64_data = base64.b64encode(test_data).decode("ascii")
        correct_crc = crc16(test_data)
        wrong_crc = 0x1234

        self.mock_fpb.send_fl_cmd.side_effect = [
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{wrong_crc:04X} data={b64_data}",
            ),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{correct_crc:04X} data={b64_data}",
            ),
        ]
        self.ft.fread(256)
        self.assertEqual(self.ft.stats["retry_count"], 1)
        self.assertEqual(self.ft.stats["crc_errors"], 1)

    def test_fread_retry_increments_other_errors(self):
        """Test fread retry on invalid response increments other_errors."""
        test_data = b"hello"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)

        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] Invalid response format"),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
        ]
        self.ft.fread(256)
        self.assertEqual(self.ft.stats["retry_count"], 1)
        self.assertEqual(self.ft.stats["other_errors"], 1)

    def test_fwrite_other_error_increments_stats(self):
        """Test fwrite with non-CRC error increments other_errors."""
        # Set max_retries to 3 for this test
        self.ft.max_retries = 3
        self.mock_fpb.send_fl_cmd.side_effect = [
            (False, "[FLERR] Some other error"),
            (False, "[FLERR] Some other error"),
            (False, "[FLERR] Some other error"),
            (False, "[FLERR] Some other error"),
        ]
        self.ft.fwrite(b"test")
        self.assertEqual(self.ft.stats["other_errors"], 3)  # 3 retries


class TestFileTransferSeek(unittest.TestCase):
    """Tests for FileTransfer fseek functionality."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] FSEEK"))
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_fseek_success(self):
        """Test successful fseek."""
        success, msg = self.ft.fseek(100, 0)
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("-a 100", call_args)

    def test_fseek_from_current(self):
        """Test fseek from current position (whence=1)."""
        success, msg = self.ft.fseek(50, 1)
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("-a 50", call_args)

    def test_fseek_from_end(self):
        """Test fseek from end (whence=2)."""
        success, msg = self.ft.fseek(-10, 2)
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("-a -10", call_args)

    def test_fseek_failure(self):
        """Test fseek failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] Seek failed")
        success, msg = self.ft.fseek(100, 0)
        self.assertFalse(success)

    def test_fseek_default_whence(self):
        """Test fseek with default whence (SEEK_SET)."""
        success, msg = self.ft.fseek(200)
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("-a 200", call_args)

    def test_fwrite_with_seek_on_retry(self):
        """Test fwrite seeks to correct position on retry."""
        self.mock_fpb.send_fl_cmd.side_effect = [
            (False, "[FLERR] CRC mismatch"),  # First attempt fails
            (True, "[FLOK] FSEEK"),  # Seek on retry
            (True, "[FLOK] FWRITE 10 bytes"),  # Retry succeeds
        ]
        success, msg = self.ft.fwrite(b"test data!", current_offset=100)
        self.assertTrue(success)
        # Check that fseek was called with correct offset
        calls = self.mock_fpb.send_fl_cmd.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertIn("fseek", calls[1][0][0])
        self.assertIn("-a 100", calls[1][0][0])

    def test_fread_with_seek_on_retry(self):
        """Test fread seeks to correct position on retry."""
        test_data = b"hello"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)

        self.mock_fpb.send_fl_cmd.side_effect = [
            (False, "[FLERR] Timeout"),  # First attempt fails
            (True, "[FLOK] FSEEK"),  # Seek on retry
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
        ]
        success, data, msg = self.ft.fread(256, current_offset=200)
        self.assertTrue(success)
        self.assertEqual(data, test_data)
        # Check that fseek was called with correct offset
        calls = self.mock_fpb.send_fl_cmd.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertIn("fseek", calls[1][0][0])
        self.assertIn("-a 200", calls[1][0][0])

    def test_fwrite_no_seek_without_offset(self):
        """Test fwrite does not seek when current_offset is None."""
        self.mock_fpb.send_fl_cmd.side_effect = [
            (False, "[FLERR] CRC mismatch"),
            (True, "[FLOK] FWRITE 10 bytes"),
        ]
        success, msg = self.ft.fwrite(b"test data!")  # No current_offset
        self.assertTrue(success)
        # Should only have 2 calls (no fseek)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 2)
        # Neither call should be fseek
        for call in self.mock_fpb.send_fl_cmd.call_args_list:
            self.assertNotIn("fseek", call[0][0])

    def test_fread_no_seek_without_offset(self):
        """Test fread does not seek when current_offset is None."""
        test_data = b"hello"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)

        self.mock_fpb.send_fl_cmd.side_effect = [
            (False, "[FLERR] Timeout"),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
        ]
        success, data, msg = self.ft.fread(256)  # No current_offset
        self.assertTrue(success)
        # Should only have 2 calls (no fseek)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 2)


class TestFileTransferMaxRetries(unittest.TestCase):
    """Tests for FileTransfer max_retries configuration."""

    def setUp(self):
        """Set up mock FPB."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))

    def test_default_max_retries(self):
        """Test default max_retries value."""
        ft = FileTransfer(self.mock_fpb)
        self.assertEqual(ft.max_retries, FileTransfer.DEFAULT_MAX_RETRIES)

    def test_custom_max_retries(self):
        """Test custom max_retries in constructor."""
        ft = FileTransfer(self.mock_fpb, max_retries=5)
        self.assertEqual(ft.max_retries, 5)

    def test_max_retries_used_in_fwrite(self):
        """Test max_retries is used in fwrite."""
        ft = FileTransfer(self.mock_fpb, max_retries=2)
        self.mock_fpb.send_fl_cmd.return_value = (
            False,
            "[FLERR] CRC mismatch",
        )
        ft.fwrite(b"test")
        # 1 initial + 2 retries = 3 calls
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 3)

    def test_max_retries_used_in_fread(self):
        """Test max_retries is used in fread."""
        ft = FileTransfer(self.mock_fpb, max_retries=2)
        self.mock_fpb.send_fl_cmd.return_value = (False, "[FLERR] Timeout")
        ft.fread(256)
        # 1 initial + 2 retries = 3 calls
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 3)


class TestFileTransferLogCallback(unittest.TestCase):
    """Tests for FileTransfer log_callback functionality."""

    def setUp(self):
        """Set up mock FPB."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))

    def test_log_callback_none_by_default(self):
        """Test log_callback is None by default."""
        ft = FileTransfer(self.mock_fpb)
        self.assertIsNone(ft.log_callback)

    def test_log_callback_set_in_constructor(self):
        """Test log_callback can be set in constructor."""
        callback = Mock()
        ft = FileTransfer(self.mock_fpb, log_callback=callback)
        self.assertEqual(ft.log_callback, callback)

    def test_log_method_calls_callback(self):
        """Test _log method calls log_callback."""
        callback = Mock()
        ft = FileTransfer(self.mock_fpb, log_callback=callback)
        ft._log("Test message")
        callback.assert_called_once_with("Test message")

    def test_log_method_without_callback(self):
        """Test _log method works without callback."""
        ft = FileTransfer(self.mock_fpb)
        # Should not raise
        ft._log("Test message")

    def test_log_callback_called_on_fwrite_retry(self):
        """Test log_callback is called during fwrite retry."""
        callback = Mock()
        ft = FileTransfer(self.mock_fpb, log_callback=callback, max_retries=2)
        self.mock_fpb.send_fl_cmd.side_effect = [
            (False, "[FLERR] CRC mismatch"),
            (True, "[FLOK] FSEEK"),  # fseek on retry
            (True, "[FLOK] FWRITE 10 bytes"),
        ]
        ft.fwrite(b"test data!", current_offset=100)
        # Should have logged the CRC mismatch
        self.assertTrue(callback.called)
        log_messages = [call[0][0] for call in callback.call_args_list]
        self.assertTrue(any("CRC mismatch" in msg for msg in log_messages))

    def test_log_callback_called_on_fread_retry(self):
        """Test log_callback is called during fread retry."""
        callback = Mock()
        ft = FileTransfer(self.mock_fpb, log_callback=callback, max_retries=2)
        test_data = b"hello"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)
        wrong_crc = 0x1234

        self.mock_fpb.send_fl_cmd.side_effect = [
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{wrong_crc:04X} data={b64_data}",
            ),
            (True, "[FLOK] FSEEK"),  # fseek on retry
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
        ]
        ft.fread(256, current_offset=200)
        # Should have logged the CRC mismatch
        self.assertTrue(callback.called)
        log_messages = [call[0][0] for call in callback.call_args_list]
        self.assertTrue(any("CRC mismatch" in msg for msg in log_messages))

    def test_log_callback_includes_offset_and_length(self):
        """Test log messages include offset and length info."""
        callback = Mock()
        ft = FileTransfer(self.mock_fpb, log_callback=callback, max_retries=2)
        self.mock_fpb.send_fl_cmd.side_effect = [
            (False, "[FLERR] CRC mismatch"),
            (True, "[FLOK] FSEEK"),  # fseek on retry
            (True, "[FLOK] FWRITE 10 bytes"),
        ]
        ft.fwrite(b"test data!", current_offset=512)
        # Check log message contains offset info
        log_messages = [call[0][0] for call in callback.call_args_list]
        self.assertTrue(any("offset=512" in msg for msg in log_messages))

    def test_log_callback_on_fread_timeout(self):
        """Test log_callback is called on fread timeout retry."""
        callback = Mock()
        ft = FileTransfer(self.mock_fpb, log_callback=callback, max_retries=2)
        test_data = b"hello"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)

        self.mock_fpb.send_fl_cmd.side_effect = [
            (False, "[FLERR] Timeout"),
            (True, "[FLOK] FSEEK"),  # fseek on retry
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
        ]
        ft.fread(256, current_offset=100)
        # Should have logged the timeout
        self.assertTrue(callback.called)
        log_messages = [call[0][0] for call in callback.call_args_list]
        self.assertTrue(any("timeout" in msg.lower() for msg in log_messages))


class TestPathSanitization(unittest.TestCase):
    """Tests for path sanitization to prevent command injection."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK]")

    def test_path_with_newline_rejected(self):
        """Test path with newline is rejected."""
        ft = FileTransfer(self.mock_fpb)
        with self.assertRaises(ValueError) as ctx:
            ft.fopen("/path\nwith\nnewline", "r")
        self.assertIn("control characters", str(ctx.exception))

    def test_path_with_carriage_return_rejected(self):
        """Test path with carriage return is rejected."""
        ft = FileTransfer(self.mock_fpb)
        with self.assertRaises(ValueError) as ctx:
            ft.fstat("/path\rwith\rcarriage")
        self.assertIn("control characters", str(ctx.exception))

    def test_path_with_quote_rejected(self):
        """A path containing a double quote is rejected: the device tokenizer
        has no escape mechanism, so it cannot be represented unambiguously.
        Escaping it (old behavior) produced a corrupt path + CRC mismatch."""
        ft = FileTransfer(self.mock_fpb)
        with self.assertRaises(ValueError) as ctx:
            ft.flist('/path/with"quotes"')
        self.assertIn("double quote", str(ctx.exception))
        # Nothing should have been sent to the device.
        self.mock_fpb.send_fl_cmd.assert_not_called()

    def test_path_with_quote_and_spaces_rejected(self):
        """Quote rejection wins even when spaces are also present."""
        ft = FileTransfer(self.mock_fpb)
        with self.assertRaises(ValueError):
            ft.flist('/path/with "quotes"')
        self.mock_fpb.send_fl_cmd.assert_not_called()

    def test_path_with_tab_is_quoted(self):
        """A tab is a device tokenizer separator, so the path must be wrapped
        in quotes (previously only spaces triggered wrapping, which truncated
        tab-containing paths on the device)."""
        ft = FileTransfer(self.mock_fpb)
        ft.flist("/path/with\ttab")
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn('--path "/path/with\ttab"', call_args)

    def test_path_with_backslash_unchanged(self):
        """Backslash is a normal path byte (no escape semantics); it must pass
        through verbatim and unquoted when there is no whitespace."""
        ft = FileTransfer(self.mock_fpb)
        ft.flist("/path/back\\slash")
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("--path /path/back\\slash", call_args)

    def test_normal_path_unchanged(self):
        """Test normal path works correctly without quotes."""
        ft = FileTransfer(self.mock_fpb)
        ft.fopen("/normal/path/file.txt", "r")
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("--path /normal/path/file.txt", call_args)

    def test_fmkdir_sanitizes_path(self):
        """Test fmkdir sanitizes path."""
        ft = FileTransfer(self.mock_fpb)
        with self.assertRaises(ValueError):
            ft.fmkdir("/dir\nname")

    def test_fremove_sanitizes_path(self):
        """Test fremove sanitizes path."""
        ft = FileTransfer(self.mock_fpb)
        with self.assertRaises(ValueError):
            ft.fremove("/file\rname")

    def test_frename_sanitizes_both_paths(self):
        """Test frename sanitizes both old and new paths."""
        ft = FileTransfer(self.mock_fpb)
        with self.assertRaises(ValueError):
            ft.frename("/old\npath", "/new/path")
        with self.assertRaises(ValueError):
            ft.frename("/old/path", "/new\npath")


if __name__ == "__main__":
    unittest.main()


class TestFileTransferCRCEnhancements(unittest.TestCase):
    """Tests for CRC integrity enhancements (V2 audit)."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_fopen_sends_crc(self):
        """fopen must send CRC covering path + mode."""
        from fpbinject.utils.crc import crc16_update

        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FOPEN /test.txt mode=w",
        )
        self.ft.fopen("/test.txt", "w")
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("-r 0x", call_args)

        # Verify CRC value
        import re

        m = re.search(r"-r 0x([0-9A-Fa-f]+)", call_args)
        self.assertIsNotNone(m)
        sent_crc = int(m.group(1), 16)
        expected = crc16_update(0xFFFF, b"/test.txt")
        expected = crc16_update(expected, b"w")
        self.assertEqual(sent_crc, expected)

    def test_fopen_crc_varies_with_mode(self):
        """fopen CRC must differ for different modes."""
        import re

        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FOPEN /test.txt mode=r",
        )
        self.ft.fopen("/test.txt", "r")
        call_r = self.mock_fpb.send_fl_cmd.call_args[0][0]
        crc_r = int(re.search(r"-r 0x([0-9A-Fa-f]+)", call_r).group(1), 16)

        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FOPEN /test.txt mode=w",
        )
        self.ft.fopen("/test.txt", "w")
        call_w = self.mock_fpb.send_fl_cmd.call_args[0][0]
        crc_w = int(re.search(r"-r 0x([0-9A-Fa-f]+)", call_w).group(1), 16)

        self.assertNotEqual(crc_r, crc_w)

    def test_fremove_sends_crc(self):
        """fremove must send CRC covering path."""
        from fpbinject.utils.crc import crc16_update
        import re

        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FREMOVE /test.txt",
        )
        self.ft.fremove("/test.txt")
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", call_args)
        self.assertIsNotNone(m)
        sent_crc = int(m.group(1), 16)
        expected = crc16_update(0xFFFF, b"/test.txt")
        self.assertEqual(sent_crc, expected)

    def test_frename_sends_crc(self):
        """frename must send CRC covering old_path + new_path."""
        from fpbinject.utils.crc import crc16_update
        import re

        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FRENAME /old.txt -> /new.txt",
        )
        self.ft.frename("/old.txt", "/new.txt")
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", call_args)
        self.assertIsNotNone(m)
        sent_crc = int(m.group(1), 16)
        expected = crc16_update(0xFFFF, b"/old.txt")
        expected = crc16_update(expected, b"/new.txt")
        self.assertEqual(sent_crc, expected)

    def test_fcrc_chunked_large_file(self):
        """fcrc must use chunked calls for files larger than 32KB."""
        # 64KB file should result in 2 chunked calls
        chunk1_size = 32768
        chunk2_size = 32768
        self.mock_fpb.send_fl_cmd.side_effect = [
            (
                True,
                f"[FLOK] FCRC offset=0 size={chunk1_size} crc=0x1234",
            ),
            (
                True,
                f"[FLOK] FCRC offset={chunk1_size} size={chunk2_size} crc=0xABCD",
            ),
        ]
        success, size, crc_val = self.ft.fcrc(65536)
        self.assertTrue(success)
        self.assertEqual(size, 65536)
        self.assertEqual(crc_val, 0xABCD)
        # Verify 2 calls were made
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 2)

    def test_fcrc_chunked_passes_crc_chain(self):
        """fcrc chunked calls must chain CRC from previous chunk."""
        import re

        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FCRC offset=0 size=32768 crc=0x1234"),
            (True, "[FLOK] FCRC offset=32768 size=32768 crc=0xABCD"),
        ]
        self.ft.fcrc(65536)

        # Second call should include -r 0x1234 (CRC from first chunk)
        second_call = self.mock_fpb.send_fl_cmd.call_args_list[1][0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", second_call)
        self.assertIsNotNone(m, "Second fcrc call must include -r for CRC chaining")
        self.assertEqual(int(m.group(1), 16), 0x1234)

    def test_fcrc_small_file_single_call(self):
        """fcrc for small files (<=32KB) should use single call."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FCRC offset=0 size=1024 crc=0x5678",
        )
        success, size, crc_val = self.ft.fcrc(1024)
        self.assertTrue(success)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 1)

    def test_fcrc_rejects_offset_echo_mismatch(self):
        """fcrc must retry when the device echoes a different offset.

        The fcrc request args (-a/-l/-r) are not CRC-protected on the wire, so
        a corrupted-but-parseable request can make the device seek to the wrong
        offset yet still return a well-formed [FLOK] FCRC line. The host must
        detect this via the echoed offset and retry rather than trust it.
        """
        self.ft.max_retries = 2
        self.mock_fpb.send_fl_cmd.side_effect = [
            # Device seeked to offset 7 instead of the requested 0 (corrupted -a)
            (True, "[FLOK] FCRC offset=7 size=1024 crc=0xBAD1"),
            # Retry succeeds with correct offset
            (True, "[FLOK] FCRC offset=0 size=1024 crc=0x5678"),
        ]
        success, size, crc_val = self.ft.fcrc(1024)
        self.assertTrue(success)
        self.assertEqual(size, 1024)
        self.assertEqual(crc_val, 0x5678)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 2)

    def test_fcrc_rejects_oversized_chunk(self):
        """fcrc must reject a reply whose size exceeds the requested length."""
        self.ft.max_retries = 0
        self.mock_fpb.send_fl_cmd.side_effect = [
            # size larger than the requested 512 -> corrupted -l
            (True, "[FLOK] FCRC offset=0 size=99999 crc=0xDEAD"),
        ]
        success, size, crc_val = self.ft.fcrc(512)
        self.assertFalse(success)
        self.assertEqual(size, 0)
        self.assertEqual(crc_val, 0)

    def test_fcrc_offset_mismatch_exhausts_retries(self):
        """fcrc fails cleanly if every reply has a bad offset echo."""
        self.ft.max_retries = 1
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FCRC offset=13 size=1024 crc=0x0001",
        )
        success, size, crc_val = self.ft.fcrc(1024)
        self.assertFalse(success)
        self.assertEqual(size, 0)
        self.assertEqual(crc_val, 0)
        # initial attempt + 1 retry
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 2)

    def test_fcrc_chunked_validates_each_offset(self):
        """Chunked fcrc must validate the echoed offset of every chunk."""
        self.ft.max_retries = 1
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FCRC offset=0 size=32768 crc=0x1234"),
            # Second chunk should be at offset 32768; device reports wrong offset
            (True, "[FLOK] FCRC offset=999 size=32768 crc=0xBEEF"),
            # Retry of second chunk with correct offset
            (True, "[FLOK] FCRC offset=32768 size=32768 crc=0xABCD"),
        ]
        success, size, crc_val = self.ft.fcrc(65536)
        self.assertTrue(success)
        self.assertEqual(size, 65536)
        self.assertEqual(crc_val, 0xABCD)
        self.assertEqual(self.mock_fpb.send_fl_cmd.call_count, 3)

    def test_upload_fclose_before_fcrc(self):
        """Upload must close file before CRC verification (P1 fix)."""
        data = b"test data"
        expected_crc = crc16(data)
        call_log = []

        def track_calls(cmd, **kwargs):
            call_log.append(cmd)
            if "fopen" in cmd and "mode=w" in cmd:
                return (True, "[FLOK] FOPEN /test.txt mode=w")
            elif "fwrite" in cmd:
                return (True, "[FLOK] FWRITE 9 bytes")
            elif "fclose" in cmd:
                return (True, "[FLOK] FCLOSE")
            elif "fopen" in cmd and "mode=r" in cmd:
                return (True, "[FLOK] FOPEN /test.txt mode=r")
            elif "fcrc" in cmd:
                return (
                    True,
                    f"[FLOK] FCRC offset=0 size=9 crc=0x{expected_crc:04X}",
                )
            return (True, "[FLOK] OK")

        self.mock_fpb.send_fl_cmd.side_effect = track_calls
        success, msg = self.ft.upload(data, "/test.txt")
        self.assertTrue(success)

        # Verify order: fopen(w) → fwrite → fclose → fopen(r) → fcrc → fclose
        fclose_indices = [i for i, c in enumerate(call_log) if "fclose" in c]
        fcrc_indices = [i for i, c in enumerate(call_log) if "fcrc" in c]
        self.assertTrue(len(fclose_indices) >= 2)
        self.assertTrue(len(fcrc_indices) >= 1)
        # First fclose must come before fcrc
        self.assertLess(fclose_indices[0], fcrc_indices[0])

    def test_download_fclose_before_fcrc(self):
        """Download must close file before CRC verification (P1 fix)."""
        import base64

        test_data = b"hello"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc_val = crc16(test_data)
        call_log = []

        def track_calls(cmd, **kwargs):
            call_log.append(cmd)
            if "fstat" in cmd:
                return (
                    True,
                    f"[FLOK] FSTAT /t.txt size={len(test_data)} mtime=0 type=file",
                )
            elif "fopen" in cmd and "mode=r" in cmd:
                return (True, "[FLOK] FOPEN /t.txt mode=r")
            elif "fread" in cmd:
                if any("fread" in c for c in call_log[:-1]):
                    return (True, "[FLOK] FREAD 0 bytes EOF")
                return (
                    True,
                    f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc_val:04X} data={b64_data}",
                )
            elif "fclose" in cmd:
                return (True, "[FLOK] FCLOSE")
            elif "fcrc" in cmd:
                return (
                    True,
                    f"[FLOK] FCRC offset=0 size={len(test_data)} crc=0x{crc_val:04X}",
                )
            return (True, "[FLOK] OK")

        self.mock_fpb.send_fl_cmd.side_effect = track_calls
        success, data, msg = self.ft.download("/t.txt")
        self.assertTrue(success)

        fclose_indices = [i for i, c in enumerate(call_log) if "fclose" in c]
        fcrc_indices = [i for i, c in enumerate(call_log) if "fcrc" in c]
        self.assertTrue(len(fclose_indices) >= 2)
        self.assertTrue(len(fcrc_indices) >= 1)
        self.assertLess(fclose_indices[0], fcrc_indices[0])

    def test_fseek_sends_crc(self):
        """fseek must send CRC covering addr(4B)."""
        import re
        import struct
        from fpbinject.utils.crc import crc16_update

        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FSEEK 100")
        self.ft.fseek(100)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", call_args)
        self.assertIsNotNone(m)
        sent_crc = int(m.group(1), 16)
        expected = crc16_update(0xFFFF, struct.pack("<i", 100))
        self.assertEqual(sent_crc, expected)

    def test_fstat_sends_crc(self):
        """fstat must send CRC covering path."""
        import re
        from fpbinject.utils.crc import crc16_update

        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FSTAT /test.txt size=100 mtime=0 type=file",
        )
        self.ft.fstat("/test.txt")
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", call_args)
        self.assertIsNotNone(m)
        sent_crc = int(m.group(1), 16)
        expected = crc16_update(0xFFFF, b"/test.txt")
        self.assertEqual(sent_crc, expected)

    def test_flist_sends_crc(self):
        """flist must send CRC covering path."""
        import re
        from fpbinject.utils.crc import crc16_update

        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FLIST dir=0 file=0",
        )
        self.ft.flist("/data")
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", call_args)
        self.assertIsNotNone(m)
        sent_crc = int(m.group(1), 16)
        expected = crc16_update(0xFFFF, b"/data")
        self.assertEqual(sent_crc, expected)

    def test_fmkdir_sends_crc(self):
        """fmkdir must send CRC covering path."""
        import re
        from fpbinject.utils.crc import crc16_update

        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FMKDIR /newdir")
        self.ft.fmkdir("/newdir")
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", call_args)
        self.assertIsNotNone(m)
        sent_crc = int(m.group(1), 16)
        expected = crc16_update(0xFFFF, b"/newdir")
        self.assertEqual(sent_crc, expected)


class TestFileTransferVerifyRetry(unittest.TestCase):
    """Tests for whole-file CRC verification retry (fcrc integrity gap)."""

    def setUp(self):
        """Set up mock FPB and FileTransfer."""
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[FLOK] Test"))
        self.ft = FileTransfer(
            self.mock_fpb, upload_chunk_size=256, download_chunk_size=256
        )

    def test_upload_verify_retries_then_succeeds(self):
        """A corrupted first verification must be retried, not fail the upload.

        The fcrc request args are not integrity-protected, so a corrupted
        verification exchange can report a wrong CRC even though the data
        (already CRC-checked per chunk during fwrite) is good. Upload must
        retry the whole verify and succeed on the good reply.
        """
        data = b"x" * 100
        good_crc = crc16(data)
        wrong_crc = good_crc ^ 0xFFFF
        self.ft.max_retries = 3
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),
            (True, "[FLOK] FWRITE 100 bytes"),
            (True, "[FLOK] FCLOSE"),
            # First verify: reopen + corrupted fcrc + close
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size=100 crc=0x{wrong_crc:04X}"),
            (True, "[FLOK] FCLOSE"),
            # Retry verify: reopen + good fcrc + close
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size=100 crc=0x{good_crc:04X}"),
            (True, "[FLOK] FCLOSE"),
        ]
        success, msg = self.ft.upload(data, "/test.txt")
        self.assertTrue(success)
        # One retry was counted for the corrupted verification.
        self.assertGreaterEqual(self.ft.stats["retry_count"], 1)

    def test_download_verify_retries_then_succeeds(self):
        """A corrupted first verification must be retried during download."""
        test_data = b"hello world"
        b64_data = base64.b64encode(test_data).decode("ascii")
        crc = crc16(test_data)
        wrong_crc = crc ^ 0xFFFF
        self.ft.max_retries = 3
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, f"[FLOK] FSTAT /test.txt size={len(test_data)} mtime=1 type=file"),
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (
                True,
                f"[FLOK] FREAD {len(test_data)} bytes crc=0x{crc:04X} data={b64_data}",
            ),
            (True, "[FLOK] FREAD 0 bytes EOF"),
            (True, "[FLOK] FCLOSE"),
            # First verify: corrupted
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size={len(test_data)} crc=0x{wrong_crc:04X}"),
            (True, "[FLOK] FCLOSE"),
            # Retry verify: good
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size={len(test_data)} crc=0x{crc:04X}"),
            (True, "[FLOK] FCLOSE"),
        ]
        success, data, msg = self.ft.download("/test.txt")
        self.assertTrue(success)
        self.assertEqual(data, test_data)
        self.assertGreaterEqual(self.ft.stats["retry_count"], 1)

    def test_verify_persistent_mismatch_fails(self):
        """If every verification attempt disagrees, upload must still fail."""
        data = b"x" * 100
        wrong_crc = crc16(data) ^ 0xFFFF
        self.ft.max_retries = 2
        # 3 verify attempts (initial + 2 retries), each reopen/fcrc/close.
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN /test.txt mode=w"),
            (True, "[FLOK] FWRITE 100 bytes"),
            (True, "[FLOK] FCLOSE"),
        ] + [
            (True, "[FLOK] FOPEN /test.txt mode=r"),
            (True, f"[FLOK] FCRC offset=0 size=100 crc=0x{wrong_crc:04X}"),
            (True, "[FLOK] FCLOSE"),
        ] * 3
        success, msg = self.ft.upload(data, "/test.txt")
        self.assertFalse(success)
        self.assertIn("CRC mismatch", msg)

    def test_verify_unavailable_is_warning_not_failure(self):
        """If a device CRC can never be obtained, upload still reports success.

        This preserves the original behavior: an unavailable verification is a
        warning, not a hard failure (data was already verified per chunk).
        Uses a command-dispatch mock so nested fcrc/verify retries never run
        out of scripted responses.
        """
        data = b"x" * 100
        self.ft.max_retries = 1

        def dispatch(cmd, *args, **kwargs):
            if "fwrite" in cmd:
                return (True, "[FLOK] FWRITE 100 bytes")
            if "fopen" in cmd:
                return (True, "[FLOK] FOPEN /test.txt mode=r")
            if "fclose" in cmd:
                return (True, "[FLOK] FCLOSE")
            if "fcrc" in cmd:
                # Always unparseable -> fcrc never yields a device CRC.
                return (True, "[FLOK] garbage response")
            return (True, "[FLOK] Test")

        self.mock_fpb.send_fl_cmd.side_effect = dispatch
        success, msg = self.ft.upload(data, "/test.txt")
        self.assertTrue(success)
