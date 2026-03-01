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
        self.mock_fpb.send_fl_cmd.assert_called_with(
            'fl -c fopen --path "/path/my file.txt" --mode r',
            timeout=2.0,
            max_retries=3,
        )

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
        self.mock_fpb.send_fl_cmd.assert_called_with(
            'fl -c fremove --path "/path/my file.txt"',
            timeout=2.0,
            max_retries=3,
        )

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
        self.mock_fpb.send_fl_cmd.assert_called_with(
            'fl -c frename --path "/path/old file.txt" --newpath "/path/new file.txt"',
            timeout=2.0,
            max_retries=3,
        )

    def test_upload_with_spaces(self):
        """Test upload with filename containing spaces."""
        self.mock_fpb.send_fl_cmd.side_effect = [
            (True, "[FLOK] FOPEN"),  # fopen
            (True, "[FLOK] FWRITE"),  # fwrite
            (True, "[FLOK] FCRC size=5 crc=0xd26e"),  # fcrc (correct CRC for "hello")
            (True, "[FLOK] FCLOSE"),  # fclose
        ]
        data = b"hello"
        success, msg = self.ft.upload(data, "/path/my file.txt")
        self.assertTrue(success)
        # Check that fopen was called with quoted path
        first_call = self.mock_fpb.send_fl_cmd.call_args_list[0]
        self.assertIn('"/path/my file.txt"', first_call[0][0])

    def test_download_with_spaces(self):
        """Test download with filename containing spaces."""
        # Mock responses for: fstat, fopen, fread (data), fread (EOF), fcrc, fclose
        self.mock_fpb.send_fl_cmd.side_effect = [
            (
                True,
                "[FLOK] FSTAT /path/my file.txt size=5 mtime=1234567890 type=file",
            ),  # fstat
            (True, "[FLOK] FOPEN"),  # fopen
            (
                True,
                "[FLOK] FREAD 5 bytes crc=0xd26e data=aGVsbG8=",
            ),  # fread (correct CRC for "hello")
            (True, "[FLOK] FREAD 0 bytes EOF"),  # fread EOF
            (True, "[FLOK] FCRC size=5 crc=0xd26e"),  # fcrc
            (True, "[FLOK] FCLOSE"),  # fclose
        ]
        success, data, msg = self.ft.download("/path/my file.txt")
        self.assertTrue(success)
        self.assertEqual(data, b"hello")
        # Check that fstat was called with quoted path
        first_call = self.mock_fpb.send_fl_cmd.call_args_list[0]
        self.assertIn('"/path/my file.txt"', first_call[0][0])


if __name__ == "__main__":
    unittest.main()
