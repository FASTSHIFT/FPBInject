#!/usr/bin/env python3

"""
Tests for file transfer with filenames containing spaces.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.file_transfer import FileTransfer  # noqa: E402


class TestFileTransferWithSpaces(unittest.TestCase):
    """Tests for file operations with filenames containing spaces."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_fpb = MagicMock()
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK]")
        self.ft = FileTransfer(self.mock_fpb)

    def test_fopen_with_spaces(self):
        """Test fopen with filename containing spaces."""
        success, msg = self.ft.fopen("/path/my file.txt", "r")
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn('--path "/path/my file.txt"', call_args)
        self.assertIn("-m r", call_args)
        self.assertIn("-r 0x", call_args)

    def test_fstat_with_spaces(self):
        """Test fstat with filename containing spaces."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FSTAT /path/my file.txt size=1024 mtime=1234567890 type=file",
        )
        success, stat = self.ft.fstat("/path/my file.txt")
        self.assertTrue(success)
        self.assertEqual(stat["size"], 1024)
        self.mock_fpb.send_fl_cmd.assert_called_with(
            'fl -c fstat --path "/path/my file.txt"',
            timeout=2.0,
            max_retries=3,
        )

    def test_flist_with_spaces(self):
        """Test flist with directory name containing spaces."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FLIST dir=1 file=1\nD sub dir\nF my file.txt 1024",
        )
        success, entries = self.ft.flist("/path/my dir")
        self.assertTrue(success)
        self.assertEqual(len(entries), 2)
        self.mock_fpb.send_fl_cmd.assert_called_with(
            'fl -c flist --path "/path/my dir"',
            timeout=5.0,
            max_retries=3,
        )

    def test_fremove_with_spaces(self):
        """Test fremove with filename containing spaces."""
        success, msg = self.ft.fremove("/path/my file.txt")
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn('--path "/path/my file.txt"', call_args)
        self.assertIn("-r 0x", call_args)

    def test_fmkdir_with_spaces(self):
        """Test fmkdir with directory name containing spaces."""
        success, msg = self.ft.fmkdir("/path/my new dir")
        self.assertTrue(success)
        self.mock_fpb.send_fl_cmd.assert_called_with(
            'fl -c fmkdir --path "/path/my new dir"',
            timeout=2.0,
            max_retries=3,
        )

    def test_frename_with_spaces(self):
        """Test frename with filenames containing spaces."""
        success, msg = self.ft.frename("/path/old file.txt", "/path/new file.txt")
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn('--path "/path/old file.txt"', call_args)
        self.assertIn('--newpath "/path/new file.txt"', call_args)
        self.assertIn("-r 0x", call_args)

    def test_upload_with_spaces(self):
        """Test upload with filename containing spaces."""
        from utils.crc import crc16

        data = b"hello"
        expected_crc = crc16(data)
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN"),  # fopen write
            (True, "[FLOK] FWRITE"),  # fwrite
            (True, "[FLOK] FCLOSE"),  # fclose after write
            (True, "[FLOK] FOPEN"),  # fopen read for CRC
            (True, f"[FLOK] FCRC offset=0 size=5 crc=0x{expected_crc:04X}"),  # fcrc
            (True, "[FLOK] FCLOSE"),  # fclose after CRC
        ]
        success, msg = self.ft.upload(data, "/path/my file.txt")
        self.assertTrue(success)
        # Check that fopen was called with quoted path
        first_call = self.mock_fpb.send_fl_cmd.call_args_list[0]
        self.assertIn('"/path/my file.txt"', first_call[0][0])

    def test_download_with_spaces(self):
        """Test download with filename containing spaces."""
        from utils.crc import crc16

        data = b"hello"
        expected_crc = crc16(data)
        # Mock responses for: fstat, fopen, fread (data), fread (EOF), fclose, fopen, fcrc, fclose
        self.mock_fpb.send_fl_cmd.side_effect = [
            (
                True,
                "[FLOK] FSTAT /path/my file.txt size=5 mtime=1234567890 type=file",
            ),  # fstat
            (True, "[FLOK] FOPEN"),  # fopen read
            (
                True,
                f"[FLOK] FREAD 5 bytes crc=0x{expected_crc:04X} data=aGVsbG8=",
            ),  # fread
            (True, "[FLOK] FREAD 0 bytes EOF"),  # fread EOF
            (True, "[FLOK] FCLOSE"),  # fclose after read
            (True, "[FLOK] FOPEN"),  # fopen read for CRC
            (True, f"[FLOK] FCRC offset=0 size=5 crc=0x{expected_crc:04X}"),  # fcrc
            (True, "[FLOK] FCLOSE"),  # fclose after CRC
        ]
        success, data, msg = self.ft.download("/path/my file.txt")
        self.assertTrue(success)
        self.assertEqual(data, b"hello")
        # Check that fstat was called with quoted path
        first_call = self.mock_fpb.send_fl_cmd.call_args_list[0]
        self.assertIn('"/path/my file.txt"', first_call[0][0])


class TestFileTransferSingleCharPath(unittest.TestCase):
    """Tests for file operations with single-character paths (no quotes)."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_fpb = MagicMock()
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK]")
        self.ft = FileTransfer(self.mock_fpb)

    def test_flist_single_char_path_no_quotes(self):
        """Test flist with single-char path does not add quotes."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK] FLIST dir=0 file=0")
        success, entries = self.ft.flist("/")
        self.assertTrue(success)
        self.mock_fpb.send_fl_cmd.assert_called_with(
            "fl -c flist --path /",
            timeout=5.0,
            max_retries=3,
        )

    def test_fstat_single_char_path_no_quotes(self):
        """Test fstat with single-char path does not add quotes."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FSTAT / size=0 mtime=0 type=dir",
        )
        success, stat = self.ft.fstat("/")
        self.assertTrue(success)
        self.mock_fpb.send_fl_cmd.assert_called_with(
            "fl -c fstat --path /",
            timeout=2.0,
            max_retries=3,
        )

    def test_fopen_single_char_path_no_quotes(self):
        """Test fopen with single-char path does not add quotes."""
        success, msg = self.ft.fopen("/", "r")
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("--path /", call_args)
        self.assertIn("-m r", call_args)
        # Path should not be quoted
        self.assertNotIn('"/"', call_args)

    def test_multi_char_path_no_quotes_without_spaces(self):
        """Test that multi-char paths without spaces have no quotes."""
        success, msg = self.ft.fopen("/a", "r")
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("--path /a", call_args)
        self.assertIn("-m r", call_args)
        self.assertNotIn('"/a"', call_args)


if __name__ == "__main__":
    unittest.main()
