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

from fpbinject.core.file_transfer import FileTransfer  # noqa: E402


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
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn('--path "/path/my file.txt"', call_args)
        self.assertIn("-r 0x", call_args)

    def test_flist_with_spaces(self):
        """Test flist with directory name containing spaces."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FLIST dir=1 file=1\nD sub dir\nF my file.txt 1024",
        )
        success, entries = self.ft.flist("/path/my dir")
        self.assertTrue(success)
        self.assertEqual(len(entries), 2)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn('--path "/path/my dir"', call_args)
        self.assertIn("-r 0x", call_args)

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
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn('--path "/path/my new dir"', call_args)
        self.assertIn("-r 0x", call_args)

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
        from fpbinject.utils.crc import crc16

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
        from fpbinject.utils.crc import crc16

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
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("--path /", call_args)
        self.assertNotIn('"/"', call_args)

    def test_fstat_single_char_path_no_quotes(self):
        """Test fstat with single-char path does not add quotes."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[FLOK] FSTAT / size=0 mtime=0 type=dir",
        )
        success, stat = self.ft.fstat("/")
        self.assertTrue(success)
        call_args = self.mock_fpb.send_fl_cmd.call_args[0][0]
        self.assertIn("--path /", call_args)
        self.assertNotIn('"/"', call_args)

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


def _device_parse_line(line):
    """Faithful model of the fixed device tokenizer fl_stream_parse_line().

    Strips ``"`` quotes (no backslash escaping), splits on unquoted
    whitespace. Used to verify the host emits a command the device parses
    back into the exact path -- i.e. the '--path' bytes round-trip.
    """
    buf = bytearray(line.encode("utf-8"))
    offs, p, in_quote, in_arg = [], 0, False, False
    while p < len(buf) and buf[p] != 0:
        b = buf[p]
        ch = chr(b) if b < 128 else None
        if ch == '"':
            in_quote = not in_quote
            del buf[p]
            if not in_arg:
                offs.append(p)
                in_arg = True
            continue
        if not in_quote and ch in (" ", "\t"):
            if in_arg:
                buf[p] = 0
                in_arg = False
        else:
            if not in_arg:
                offs.append(p)
                in_arg = True
        p += 1
    out = []
    for o in offs:
        e = o
        while e < len(buf) and buf[e] != 0:
            e += 1
        out.append(bytes(buf[o:e]).decode("utf-8", errors="replace"))
    return out


class TestPathRoundTripRobustness(unittest.TestCase):
    """Host must emit commands whose --path the device tokenizer recovers
    byte-for-byte, and whose CRC matches. Guards against host/device
    tokenizer divergence for weird-but-valid paths."""

    # Paths the device CAN represent and must round-trip exactly.
    GOOD_PATHS = [
        "/tmp/plain.svg",
        "/tmp/112 1.svg",
        "/tmp/two  spaces.txt",
        "/tmp/中文/文件.svg",
        "/tmp/a (v2)[final]#1.svg",
        "/tmp/with\ttab.txt",
        "/tmp/back\\slash.svg",
        "/tmp/'single'.svg",
        "/tmp/trailing ",
        "/tmp/-dash --path.txt",
    ]

    # Paths the host must reject (device tokenizer cannot represent them).
    BAD_PATHS = [
        '/tmp/say "hi".svg',
        "/tmp/line\nbreak",
        "/tmp/carriage\rreturn",
    ]

    def setUp(self):
        self.mock_fpb = MagicMock()
        self.mock_fpb.send_fl_cmd.return_value = (True, "[FLOK]")
        self.ft = FileTransfer(self.mock_fpb)

    def _extract_path_and_crc(self, cmd):
        argv = _device_parse_line(cmd)
        path = None
        crc = None
        for i, tok in enumerate(argv):
            if tok == "--path" and i + 1 < len(argv):
                path = argv[i + 1]
            if tok == "-r" and i + 1 < len(argv):
                crc = int(argv[i + 1], 16)
        return path, crc

    def test_good_paths_round_trip_and_crc_matches(self):
        from fpbinject.utils.crc import crc16_update

        for path in self.GOOD_PATHS:
            with self.subTest(path=path):
                self.mock_fpb.reset_mock()
                self.ft.fstat(path)
                cmd = self.mock_fpb.send_fl_cmd.call_args[0][0]
                dev_path, dev_crc = self._extract_path_and_crc(cmd)
                # Device recovers the exact path...
                self.assertEqual(dev_path, path)
                # ...and the CRC the host advertised is over that same path.
                expected = crc16_update(0xFFFF, path.encode("utf-8"))
                self.assertEqual(dev_crc, expected)

    def test_bad_paths_are_rejected(self):
        for path in self.BAD_PATHS:
            with self.subTest(path=path):
                self.mock_fpb.reset_mock()
                with self.assertRaises(ValueError):
                    self.ft.fstat(path)
                self.mock_fpb.send_fl_cmd.assert_not_called()

    def test_frename_round_trips_both_paths(self):
        from fpbinject.utils.crc import crc16_update

        old, new = "/tmp/old name.txt", "/tmp/new (v2).txt"
        self.ft.frename(old, new)
        cmd = self.mock_fpb.send_fl_cmd.call_args[0][0]
        argv = _device_parse_line(cmd)
        dev_old = argv[argv.index("--path") + 1]
        dev_new = argv[argv.index("--newpath") + 1]
        self.assertEqual(dev_old, old)
        self.assertEqual(dev_new, new)
        # CRC chains old then new path.
        crc = crc16_update(0xFFFF, old.encode("utf-8"))
        crc = crc16_update(crc, new.encode("utf-8"))
        dev_crc = int(argv[argv.index("-r") + 1], 16)
        self.assertEqual(dev_crc, crc)


if __name__ == "__main__":
    unittest.main()
