#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for core/exec_client.py (the fl ``exec`` command client).

The client is exercised against ``FirmwareSim``, a small model of the
firmware side (App/func_loader/fl_cmd_exec.c) with fault injection, covering
the recovery scenarios from docs/exec-command-design.md: damaged/lost request,
lost start line, lost response, damaged result line, blocking command.
"""

import base64
import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpbinject.core import exec_client  # noqa: E402
from fpbinject.core.exec_client import (  # noqa: E402
    ExecArgumentError,
    ExecClient,
    ExecResponseParser,
    default_max_retries,
    max_command_bytes,
    request_crc,
    result_crc,
    start_crc,
    validate_args,
    worst_case_seconds,
)
from fpbinject.core.serial_protocol import FPBProtocol, FPBProtocolError  # noqa: E402
from fpbinject.services.device_worker import DeviceWorker  # noqa: E402

# Small timeouts keep the suite fast
ACK = 0.05
RUN = 0.3


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
def frame_err(msg):
    return f"[FLERR] {msg}\n[FLEND]\n".encode()


class FirmwareSim:
    """Model of the firmware's exec command with fault injection."""

    def __init__(self):
        self.calls = []  # (cmdline, timeout_ms) per real execution
        self.ret = 0
        self.output = "out\n"
        self.last = None  # (seq, ret) cached result
        self.exec_cb = True
        self.lose_requests = 0  # request never reaches the device
        self.damage_requests = 0  # request damaged: device answers CRC mismatch
        self.drop_responses = 0  # executed, but the whole response is lost
        self.drop_start = False  # start line lost
        self.damage_results = 0  # result line damaged on the way back
        self.hang = False  # command never finishes
        self.hung = False
        self.forget_after = False  # device "reboots" after running the command
        self.fatal_error = None  # device rejects the request with this message
        self.prefix = ""  # stale text arriving before the response
        self.unterminated = False  # command output has no trailing newline

    def _result(self, seq, ret, replay):
        ok = ret >= 0
        text = (
            f"[{'FLOK' if ok else 'FLERR'}] EXEC seq={seq} ret={ret} "
            f"crc=0x{result_crc(seq, ret):04X}"
            f"{' replay=1' if replay else ''}{'' if ok else ' spawn failed'}"
        )
        if self.damage_results > 0 and not replay:
            self.damage_results -= 1
            text = text.replace(f"ret={ret}", f"ret={ret + 1}")
        return text + "\n[FLEND]\n"

    def __call__(self, line):
        if self.hung:
            return b""
        toks = line.split()
        if toks[:3] == ["fl", "-c", "ping"]:
            return b"[FLOK] PONG\n[FLEND]\n"
        if toks[:3] != ["fl", "-c", "exec"]:
            return b""
        if self.lose_requests > 0:
            self.lose_requests -= 1
            return b""
        if self.damage_requests > 0:
            self.damage_requests -= 1
            return frame_err("CRC mismatch: 0x0000 != 0x0001")
        if self.fatal_error:
            return frame_err(self.fatal_error)
        if not self.exec_cb:
            return frame_err("No exec_cb")

        opts = dict(zip(toks[3::2], toks[4::2]))
        seq = int(opts.get("--seq", -1))
        timeout = int(opts.get("--timeout", 0))
        crc = int(opts["-r"], 16)

        if "-d" not in opts:  # query
            if crc != request_crc(seq, 0, b""):
                return frame_err("CRC mismatch: 0x0000 != 0x0001")
            if self.last and self.last[0] == seq:
                return self._wrap(self._result(seq, self.last[1], True).encode())
            return frame_err(f"EXEC seq={seq} no record")

        cmd = base64.b64decode(opts["-d"])
        if crc != request_crc(seq, timeout, cmd):
            return frame_err("CRC mismatch: 0x0000 != 0x0001")

        if seq >= 0 and self.last and self.last[0] == seq:
            return self._wrap(self._result(seq, self.last[1], True).encode())

        self.calls.append((cmd.decode(), timeout))
        start = (
            b""
            if self.drop_start
            else f"[FLEXEC] seq={seq} crc=0x{start_crc(seq):04X}\n".encode()
        )
        body = self.output.rstrip("\n") if self.unterminated else self.output
        out = start + body.encode()
        if self.hang:
            self.hung = True
            return self._wrap(out)
        result = self._result(seq, self.ret, False)
        if self.forget_after:
            self.last = None
        elif seq >= 0:
            self.last = (seq, self.ret)
        out += result.encode()
        if self.drop_responses > 0:
            self.drop_responses -= 1
            return b""
        return self._wrap(out)

    def _wrap(self, data):
        prefix, self.prefix = self.prefix, ""
        return prefix.encode() + data


class FakeSerial:
    """Serial port whose peer is a callable (the firmware model)."""

    def __init__(self, handler, chunk=0):
        self.handler = handler
        self.chunk = chunk
        self._rx = bytearray()
        self._tx = bytearray()
        self.lines = []
        self.write_calls = []
        self.emitted = bytearray()  # every byte the device put on the wire
        self.resets = 0  # reset_input_buffer() calls
        self.guard = False  # worker mode: only the worker may read the port
        self.in_pump = False
        self.stray_reads = 0  # reads made outside the worker's own RX step

    @property
    def in_waiting(self):
        return len(self._rx)

    def isOpen(self):
        return True

    def read(self, n=1):
        if self.guard and not self.in_pump:
            self.stray_reads += 1
        if self.chunk:
            n = min(n, self.chunk)
        data = bytes(self._rx[:n])
        del self._rx[:n]
        return data

    def write(self, data):
        self.write_calls.append(bytes(data))
        self._tx += data
        while b"\n" in self._tx:
            line, _, rest = bytes(self._tx).partition(b"\n")
            self._tx = bytearray(rest)
            text = line.decode()
            self.lines.append(text)
            reply = self.handler(text)
            if reply:
                self._rx += reply
                self.emitted += reply

    def flush(self):
        pass

    def reset_input_buffer(self):
        self.resets += 1
        self._rx.clear()

    def exec_lines(self):
        return [ln for ln in self.lines if "-c exec" in ln]


def make_client(sim=None, chunk=0, **device_attrs):
    sim = sim or FirmwareSim()
    device = MagicMock()
    device.ser = FakeSerial(sim, chunk=chunk)
    device.raw_serial_log = []
    device.raw_log_next_id = 0
    device.raw_log_max_size = 5000
    device.serial_echo_enabled = False
    device.serial_tx_fragment_size = 0
    device.upload_chunk_size = 1024
    device.transfer_max_retries = 3
    device.worker = None  # direct mode: nothing else reads the port
    for key, value in device_attrs.items():
        setattr(device, key, value)
    protocol = FPBProtocol(device)
    protocol._in_fl_mode = True
    return sim, device, protocol, ExecClient(protocol)


def run(client, cmd="ls", **kw):
    kw.setdefault("timeout", RUN)
    kw.setdefault("ack_timeout", ACK)
    return client.run(cmd, **kw)


# ---------------------------------------------------------------------------
# CRC / budget / validation
# ---------------------------------------------------------------------------
class TestCrcVectors(unittest.TestCase):
    """Vectors cross-checked against the C implementation (fl_codec.c)."""

    def test_request_crc(self):
        self.assertEqual(request_crc(123456789, 10000, b"ls -l /data"), 0x6685)

    def test_start_crc(self):
        self.assertEqual(start_crc(123456789), 0xE526)

    def test_result_crc_negative_ret(self):
        self.assertEqual(result_crc(123456789, -5), 0x5FF7)

    def test_request_crc_covers_every_field(self):
        base = request_crc(1, 1000, b"ls")
        self.assertNotEqual(base, request_crc(2, 1000, b"ls"))
        self.assertNotEqual(base, request_crc(1, 2000, b"ls"))
        self.assertNotEqual(base, request_crc(1, 1000, b"lt"))

    def test_query_crc_has_empty_payload(self):
        self.assertEqual(request_crc(5, 0, b""), request_crc(5, 0, b""))
        self.assertNotEqual(request_crc(5, 0, b""), request_crc(6, 0, b""))


class TestBudget(unittest.TestCase):
    def test_default_chunk(self):
        # upload_chunk_size 64, 10-digit seq, 5-digit timeout -> 42 bytes
        self.assertEqual(max_command_bytes(64, 2147483647, 10000), 42)

    def test_grows_with_chunk_size(self):
        self.assertGreater(
            max_command_bytes(512, 1, 1000), max_command_bytes(64, 1, 1000)
        )

    def test_overhead_uses_actual_digits(self):
        self.assertGreaterEqual(
            max_command_bytes(64, 1, 1000), max_command_bytes(64, 2147483647, 900000)
        )

    def test_tiny_chunk_gives_zero(self):
        self.assertEqual(max_command_bytes(1, 2147483647, 900000), 0)

    def test_unset_chunk_falls_back_to_default(self):
        self.assertEqual(max_command_bytes(0, 1, 1000), max_command_bytes(64, 1, 1000))


class TestValidation(unittest.TestCase):
    def test_valid(self):
        data, ms = validate_args("ls -l", 2.5, 1.0, 3)
        self.assertEqual(data, b"ls -l")
        self.assertEqual(ms, 2500)

    def test_utf8_encoding(self):
        data, _ = validate_args("echo é", 1, 1, 0)
        self.assertEqual(data, "echo é".encode("utf-8"))

    def test_bad_cmd(self):
        for bad in ("", "   ", None, 5, b"ls"):
            with self.assertRaises(ExecArgumentError):
                validate_args(bad, 1, 1, 0)

    def test_nul_rejected(self):
        with self.assertRaises(ExecArgumentError):
            validate_args("a\x00b", 1, 1, 0)

    def test_bad_timeouts(self):
        for bad in (0, -1, "5", None, True, 0.0004):
            with self.assertRaises(ExecArgumentError):
                validate_args("ls", bad, 1, 0)
        with self.assertRaises(ExecArgumentError):
            validate_args("ls", 1, 0, 0)

    def test_timeout_has_no_artificial_cap(self):
        _, ms = validate_args("ls", 86400, 1, 0)
        self.assertEqual(ms, 86400000)

    def test_timeout_protocol_limit(self):
        validate_args("ls", exec_client.MAX_TIMEOUT_MS // 1000, 1, 0)
        with self.assertRaises(ExecArgumentError):
            validate_args("ls", exec_client.MAX_TIMEOUT_MS, 1, 0)

    def test_retries_range(self):
        validate_args("ls", 1, 1, exec_client.MAX_RETRIES_LIMIT)
        for bad in (-1, exec_client.MAX_RETRIES_LIMIT + 1, 1.5, True, "3"):
            with self.assertRaises(ExecArgumentError):
                validate_args("ls", 1, 1, bad)

    def test_worst_case_seconds_grows(self):
        self.assertGreater(worst_case_seconds(10, 1, 20), worst_case_seconds(10, 1, 3))
        self.assertGreater(worst_case_seconds(100, 1, 3), 100)


class TestDefaultRetries(unittest.TestCase):
    def test_uses_transfer_max_retries(self):
        dev = MagicMock()
        dev.transfer_max_retries = 7
        self.assertEqual(default_max_retries(dev), 7)

    def test_clamped_to_limit(self):
        dev = MagicMock()
        dev.transfer_max_retries = 999
        self.assertEqual(default_max_retries(dev), exec_client.MAX_RETRIES_LIMIT)
        dev.transfer_max_retries = -4
        self.assertEqual(default_max_retries(dev), 0)

    def test_fallback_when_not_a_number(self):
        dev = MagicMock()
        dev.transfer_max_retries = "x"
        self.assertEqual(
            default_max_retries(dev), exec_client.DEFAULT_TRANSFER_MAX_RETRIES
        )
        dev.transfer_max_retries = True
        self.assertEqual(
            default_max_retries(dev), exec_client.DEFAULT_TRANSFER_MAX_RETRIES
        )


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------
def start_line(seq):
    return f"[FLEXEC] seq={seq} crc=0x{start_crc(seq):04X}\n"


def result_line(seq, ret=0, tag="FLOK", extra="", crc=None):
    crc = result_crc(seq, ret) if crc is None else crc
    return f"[{tag}] EXEC seq={seq} ret={ret} crc=0x{crc:04X}{extra}\n"


class TestParser(unittest.TestCase):
    def test_full_response(self):
        p = ExecResponseParser(7)
        p.feed(start_line(7) + "hello\nworld\n" + result_line(7, 3) + "[FLEND]\n")
        self.assertTrue(p.started)
        self.assertTrue(p.complete)
        self.assertEqual(p.output(), "hello\nworld\n")
        self.assertEqual(p.result.ret, 3)
        self.assertTrue(p.result.ok)
        self.assertTrue(p.result.crc_ok)
        self.assertFalse(p.result.replay)

    def test_noise_before_start_line(self):
        p = ExecResponseParser(7)
        p.feed("fl> fl -c exec ...\r\nfl> " + start_line(7) + "x\n")
        self.assertTrue(p.started)
        self.assertEqual(p.output(), "x\n")

    def test_chunked_arrival(self):
        text = start_line(7) + "abc\n" + result_line(7) + "[FLEND]\n"
        p = ExecResponseParser(7)
        for i in range(0, len(text), 3):
            p.feed(text[i : i + 3])
        self.assertTrue(p.complete)
        self.assertEqual(p.output(), "abc\n")

    def test_crlf_line_endings(self):
        p = ExecResponseParser(7)
        p.feed(
            start_line(7).replace("\n", "\r\n")
            + "a\r\n"
            + result_line(7).replace("\n", "\r\n")
        )
        self.assertTrue(p.result.crc_ok)
        self.assertEqual(p.output(), "a\n")

    def test_output_without_trailing_newline(self):
        p = ExecResponseParser(7)
        p.feed(start_line(7) + "partial" + result_line(7) + "[FLEND]\n")
        self.assertEqual(p.output(), "partial")
        self.assertTrue(p.result.crc_ok)

    def test_empty_output(self):
        p = ExecResponseParser(7)
        p.feed(start_line(7) + result_line(7) + "[FLEND]\n")
        self.assertEqual(p.output(), "")

    def test_stale_start_line_ignored(self):
        p = ExecResponseParser(7)
        p.feed(start_line(99) + "stale\n")
        self.assertFalse(p.started)
        self.assertFalse(p.maybe_started)

    def test_damaged_start_line_counts_as_started(self):
        p = ExecResponseParser(7)
        p.feed("[FLEXEC] seq=7 crc=0xBAD\n")
        self.assertTrue(p.started)

    def test_wrong_crc_start_line_counts_as_started(self):
        p = ExecResponseParser(7)
        p.feed("[FLEXEC] seq=99 crc=0x0000\n")
        self.assertTrue(p.started)

    def test_partial_start_line_is_maybe_started(self):
        p = ExecResponseParser(7)
        p.feed("[FLEXEC] seq=")
        self.assertFalse(p.started)
        self.assertTrue(p.maybe_started)

    def test_second_start_line_ignored(self):
        p = ExecResponseParser(7)
        p.feed(start_line(7) + "a\n" + start_line(7))
        self.assertEqual(p.output(), "a\n")

    def test_result_crc_mismatch(self):
        p = ExecResponseParser(7)
        p.feed(start_line(7) + result_line(7, 0, crc=0x1234) + "[FLEND]\n")
        self.assertFalse(p.result.crc_ok)

    def test_result_other_seq_ignored(self):
        p = ExecResponseParser(7)
        p.feed(start_line(7) + result_line(8) + "[FLEND]\n")
        self.assertIsNone(p.result)
        self.assertTrue(p.complete)

    def test_replay_flag(self):
        p = ExecResponseParser(7)
        p.feed(result_line(7, 4, extra=" replay=1") + "[FLEND]\n")
        self.assertTrue(p.result.replay)
        self.assertEqual(p.result.ret, 4)
        self.assertTrue(p.complete)

    def test_spawn_failed_result(self):
        p = ExecResponseParser(7)
        p.feed(
            start_line(7) + result_line(7, -5, "FLERR", " spawn failed") + "[FLEND]\n"
        )
        self.assertFalse(p.result.ok)
        self.assertEqual(p.result.ret, -5)
        self.assertTrue(p.result.crc_ok)

    def test_no_record(self):
        p = ExecResponseParser(7)
        p.feed("[FLERR] EXEC seq=7 no record\n[FLEND]\n")
        self.assertTrue(p.no_record)
        self.assertTrue(p.complete)

    def test_no_record_other_seq_ignored(self):
        p = ExecResponseParser(7)
        p.feed("[FLERR] EXEC seq=8 no record\n[FLEND]\n")
        self.assertFalse(p.no_record)
        self.assertFalse(p.complete)

    def test_frame_error(self):
        p = ExecResponseParser(7)
        p.feed("[FLERR] CRC mismatch: 0x1 != 0x2\n[FLEND]\n")
        self.assertEqual(p.frame_error, "[FLERR] CRC mismatch: 0x1 != 0x2")
        self.assertTrue(p.complete)

    def test_unknown_marker_after_start_is_not_output(self):
        p = ExecResponseParser(7)
        p.feed(start_line(7) + "[FLOK] EXEC seq=??\n[FLEND]\n")
        self.assertEqual(p.output(), "")
        self.assertEqual(p.frame_error, "")
        self.assertTrue(p.complete)
        self.assertIsNone(p.result)

    def test_stray_frame_end_is_noise(self):
        p = ExecResponseParser(7)
        p.feed("[FLEND]\n" + start_line(7) + "a\n" + result_line(7) + "[FLEND]\n")
        self.assertTrue(p.complete)
        self.assertEqual(p.output(), "a\n")

    def test_nothing_after_complete(self):
        p = ExecResponseParser(7)
        p.feed(start_line(7) + result_line(7) + "[FLEND]\nfl> ")
        self.assertTrue(p.complete)
        p.feed("more\n")
        self.assertEqual(p.output(), "")

    def test_start_line_lost_output_kept_without_echo(self):
        p = ExecResponseParser(7)
        p.feed(
            "fl -c exec -d YQ== --seq 7\nreal output\n" + result_line(7) + "[FLEND]\n"
        )
        self.assertFalse(p.started)
        self.assertEqual(p.output(), "real output\n")

    def test_output_truncated(self):
        p = ExecResponseParser(7, max_output=20)
        p.feed(start_line(7))
        for _ in range(50):
            p.feed("0123456789\n")
        p.feed(result_line(7) + "[FLEND]\n")
        self.assertTrue(p.truncated)
        self.assertLessEqual(len(p.output()), 22)
        self.assertTrue(p.complete)
        self.assertTrue(p.result.crc_ok)

    def test_single_long_line_truncated(self):
        p = ExecResponseParser(7, max_output=10)
        p.feed(start_line(7) + "x" * 100 + "\n")
        self.assertTrue(p.truncated)

    def test_newline_less_flood_is_flushed(self):
        p = ExecResponseParser(7, max_output=100)
        p.feed(start_line(7))
        p.feed("y" * (exec_client.MAX_PENDING_LINE + 10))
        self.assertTrue(p.truncated)
        self.assertEqual(p._pending, "")


# ---------------------------------------------------------------------------
# Client behaviour
# ---------------------------------------------------------------------------
class TestRunBasics(unittest.TestCase):
    def test_success(self):
        sim, dev, proto, client = make_client()
        sim.output = "hello\n"
        r = run(client, "echo hello")
        self.assertTrue(r["success"])
        self.assertEqual(r["ret"], 0)
        self.assertEqual(r["output"], "hello\n")
        self.assertTrue(r["started"])
        self.assertFalse(r["replayed"])
        self.assertFalse(r["output_truncated"])
        self.assertEqual(r["error_code"], "")
        self.assertGreaterEqual(r["elapsed_ms"], 0)
        self.assertEqual(sim.calls[0][0], "echo hello")
        self.assertEqual(len(dev.ser.exec_lines()), 1)

    def test_timeout_forwarded_in_milliseconds(self):
        sim, *_rest, client = make_client()
        run(client, "ls", timeout=2.5)
        self.assertEqual(sim.calls[0][1], 2500)

    def test_nonzero_ret_is_still_success(self):
        sim, _, _, client = make_client()
        sim.ret = 3
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(r["ret"], 3)

    def test_special_characters_verbatim(self):
        sim, _, _, client = make_client()
        cmd = "echo \"a b\" > /tmp/x; cat $HOME 'q' | grep -v \\n && true"
        r = run(client, cmd)
        self.assertTrue(r["success"])
        self.assertEqual(sim.calls[0][0], cmd)

    def test_unicode_command(self):
        sim, _, _, client = make_client()
        cmd = "echo \u4f60\u597d"
        r = run(client, cmd)
        self.assertTrue(r["success"])
        self.assertEqual(sim.calls[0][0], cmd)

    def test_unterminated_output(self):
        sim, _, _, client = make_client()
        sim.output = "no newline"
        sim.unterminated = True
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(r["output"], "no newline")

    def test_spawn_failure(self):
        sim, _, _, client = make_client()
        sim.ret = -12
        r = run(client)
        self.assertFalse(r["success"])
        self.assertEqual(r["error_code"], "spawn_failed")
        self.assertEqual(r["ret"], -12)
        self.assertIn("errno 12", r["error"])
        self.assertTrue(r["started"])

    def test_no_serial_port(self):
        _, dev, _, client = make_client()
        dev.ser = None
        with self.assertRaises(FPBProtocolError):
            run(client)

    def test_invalid_arguments_raise_before_sending(self):
        sim, dev, _, client = make_client()
        with self.assertRaises(ExecArgumentError):
            client.run("")
        self.assertEqual(dev.ser.lines, [])

    def test_too_long_not_sent(self):
        sim, dev, _, client = make_client(upload_chunk_size=64)
        r = run(client, "x" * 200)
        self.assertFalse(r["success"])
        self.assertEqual(r["error_code"], "too_long")
        self.assertEqual(dev.ser.lines, [])

    def test_fragmented_tx_is_reassembled(self):
        sim, dev, _, client = make_client(
            serial_tx_fragment_size=10, serial_tx_fragment_delay=0
        )
        sim.output = "ok\n"
        r = run(client, "echo fragmented")
        self.assertTrue(r["success"])
        self.assertGreater(len(dev.ser.write_calls), 2)
        self.assertEqual(sim.calls[0][0], "echo fragmented")

    def test_response_in_tiny_chunks(self):
        sim, _, _, client = make_client(chunk=3)
        sim.output = "chunked output\n"
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(r["output"], "chunked output\n")

    def test_stale_response_before_ours_is_ignored(self):
        sim, _, _, client = make_client()
        sim.prefix = start_line(5) + "old\n" + result_line(5) + "[FLEND]\n"
        sim.output = "new\n"
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(r["output"], "new\n")

    def test_output_cap(self):
        sim, _, _, client = make_client()
        sim.output = "0123456789\n" * 100
        r = client.run("cat big", timeout=RUN, ack_timeout=ACK, max_output=64)
        self.assertTrue(r["success"])
        self.assertTrue(r["output_truncated"])
        self.assertLessEqual(len(r["output"]), 70)

    def test_seq_is_random_per_command(self):
        sim, dev, _, client = make_client()
        run(client)
        run(client)
        seqs = {ln.split("--seq ")[1].split()[0] for ln in dev.ser.exec_lines()}
        self.assertEqual(len(sim.calls), 2)
        self.assertEqual(len(seqs), 2)

    def test_tool_log_written(self):
        _, dev, _, client = make_client()
        run(client, "ls /data")
        messages = [c.args[0] for c in dev.add_tool_log.call_args_list]
        self.assertTrue(any("ls /data" in m for m in messages))


class TestRequestRecovery(unittest.TestCase):
    """Scenarios A-C: the request or the whole response is lost/damaged."""

    def test_damaged_request_is_resent_and_runs_once(self):
        sim, dev, _, client = make_client()
        sim.damage_requests = 1
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(len(sim.calls), 1)
        self.assertEqual(len(dev.ser.exec_lines()), 2)

    def test_lost_request_is_resent(self):
        sim, dev, _, client = make_client()
        sim.lose_requests = 2
        r = run(client, max_retries=3)
        self.assertTrue(r["success"])
        self.assertEqual(len(sim.calls), 1)
        self.assertEqual(len(dev.ser.exec_lines()), 3)

    def test_resend_reuses_same_seq_and_timeout(self):
        sim, dev, _, client = make_client()
        sim.lose_requests = 1
        run(client, timeout=3)
        first, second = dev.ser.exec_lines()
        self.assertEqual(first, second)

    def test_lost_response_replayed_not_reexecuted(self):
        sim, dev, _, client = make_client()
        sim.drop_responses = 1
        r = run(client)
        self.assertTrue(r["success"])
        self.assertTrue(r["replayed"])
        self.assertEqual(len(sim.calls), 1)  # executed exactly once
        self.assertEqual(len(dev.ser.exec_lines()), 2)

    def test_retries_exhausted(self):
        sim, dev, _, client = make_client()
        sim.lose_requests = 99
        r = run(client, max_retries=1)
        self.assertFalse(r["success"])
        self.assertEqual(r["error_code"], "request_failed")
        self.assertFalse(r["started"])
        self.assertEqual(len(dev.ser.exec_lines()), 2)
        self.assertEqual(sim.calls, [])

    def test_zero_retries_sends_once(self):
        sim, dev, _, client = make_client()
        sim.lose_requests = 99
        r = run(client, max_retries=0)
        self.assertEqual(r["error_code"], "request_failed")
        self.assertEqual(len(dev.ser.exec_lines()), 1)

    def test_default_retries_come_from_transfer_max_retries(self):
        sim, dev, _, client = make_client(transfer_max_retries=2)
        sim.lose_requests = 99
        run(client)  # max_retries not given
        self.assertEqual(len(dev.ser.exec_lines()), 3)  # 1 + 2 retries

    def test_explicit_retries_override_config(self):
        sim, dev, _, client = make_client(transfer_max_retries=9)
        sim.lose_requests = 99
        run(client, max_retries=1)
        self.assertEqual(len(dev.ser.exec_lines()), 2)

    def test_start_line_lost_result_still_accepted(self):
        sim, dev, _, client = make_client()
        sim.drop_start = True
        sim.output = "out\n"
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(len(sim.calls), 1)
        self.assertEqual(len(dev.ser.exec_lines()), 1)  # no resend

    def test_not_supported(self):
        sim, dev, _, client = make_client()
        sim.exec_cb = False
        r = run(client)
        self.assertFalse(r["success"])
        self.assertEqual(r["error_code"], "not_supported")
        self.assertEqual(len(dev.ser.exec_lines()), 1)  # not retried

    def test_non_retriable_device_error(self):
        sim, dev, _, client = make_client()
        sim.fatal_error = "Invalid command"
        r = run(client)
        self.assertEqual(r["error_code"], "device_error")
        self.assertIn("Invalid command", r["error"])
        self.assertEqual(len(dev.ser.exec_lines()), 1)

    def test_retriable_device_errors(self):
        for message in ("Invalid base64 data", "Invalid arguments", "CRC mismatch: 1"):
            sim, dev, _, client = make_client()
            sim.fatal_error = message
            r = run(client, max_retries=2)
            self.assertEqual(r["error_code"], "request_failed", message)
            self.assertEqual(len(dev.ser.exec_lines()), 3, message)


class TestResultRecovery(unittest.TestCase):
    """Scenario E: the result line is damaged on the way back."""

    def test_damaged_result_recovered_by_query(self):
        sim, dev, _, client = make_client()
        sim.damage_results = 1
        sim.ret = 7
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(r["ret"], 7)
        self.assertTrue(r["replayed"])
        self.assertEqual(len(sim.calls), 1)  # never executed twice
        self.assertEqual(len(dev.ser.exec_lines()), 2)
        self.assertNotIn("-d", dev.ser.exec_lines()[1])  # second is a query

    def test_query_retried_when_answer_is_lost(self):
        sim, dev, _, client = make_client()
        sim.damage_results = 1
        original = sim.__call__
        state = {"swallow": 1}

        def flaky(line):
            if "-d" not in line and "-c exec" in line and state["swallow"] > 0:
                state["swallow"] -= 1
                return b""
            return original(line)

        dev.ser.handler = flaky
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(len(sim.calls), 1)

    def test_no_record_gives_unknown_and_suspect(self):
        sim, dev, proto, client = make_client()
        sim.damage_results = 1
        sim.forget_after = True
        r = run(client)
        self.assertFalse(r["success"])
        self.assertEqual(r["error_code"], "unknown_state")
        self.assertEqual(len(sim.calls), 1)
        self.assertIs(proto.exec_suspect_ser, dev.ser)

    def test_never_resends_the_command_after_start(self):
        sim, dev, _, client = make_client()
        sim.damage_results = 1
        sim.forget_after = True
        run(client)
        full = [ln for ln in dev.ser.exec_lines() if " -d " in ln]
        self.assertEqual(len(full), 1)


class TestBlockingCommand(unittest.TestCase):
    """Scenario F: the command never finishes."""

    def test_unknown_state_and_single_request(self):
        sim, dev, proto, client = make_client()
        sim.hang = True
        r = run(client, timeout=0.15)
        self.assertFalse(r["success"])
        self.assertEqual(r["error_code"], "unknown_state")
        self.assertTrue(r["started"])
        self.assertIn("no exec timeout", r["error"])
        self.assertEqual(len(dev.ser.exec_lines()), 1)  # never resent
        self.assertIs(proto.exec_suspect_ser, dev.ser)

    def test_partial_output_is_returned(self):
        sim, _, _, client = make_client()
        sim.hang = True
        sim.output = "partial\n"
        r = run(client, timeout=0.15)
        self.assertEqual(r["output"], "partial\n")

    def test_suspect_gate_refuses_while_stuck(self):
        sim, dev, _, client = make_client()
        sim.hang = True
        run(client, timeout=0.15)
        r = run(client)
        self.assertFalse(r["success"])
        self.assertEqual(r["error_code"], "device_suspect")
        self.assertEqual(len(dev.ser.exec_lines()), 1)  # no new exec line

    def test_suspect_cleared_once_device_answers(self):
        sim, dev, proto, client = make_client()
        sim.hang = True
        run(client, timeout=0.15)
        sim.hung = False  # command finished, shell is back
        sim.hang = False
        r = run(client, "echo back")
        self.assertTrue(r["success"])
        self.assertIsNone(proto.exec_suspect_ser)
        self.assertEqual(sim.calls[-1][0], "echo back")

    def test_suspect_is_per_serial_object(self):
        sim, dev, proto, client = make_client()
        sim.hang = True
        run(client, timeout=0.15)
        # reconnect: a new serial object, the old verdict no longer applies
        sim2 = FirmwareSim()
        dev.ser = FakeSerial(sim2)
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(len(sim2.calls), 1)

    def test_partial_start_line_counts_as_started(self):
        sim, dev, _, client = make_client()
        original = sim.__call__

        def half_start(line):
            if " -d " in line:
                return b"[FLEXEC] seq="  # connection cut mid-line
            return original(line)

        dev.ser.handler = half_start
        r = run(client, timeout=0.1)
        self.assertEqual(r["error_code"], "unknown_state")
        self.assertEqual(len(dev.ser.exec_lines()), 1)


class TestFpbInjectIntegration(unittest.TestCase):
    def test_exec_cmd_delegates(self):
        from fpbinject.fpb_inject import FPBInject

        device = MagicMock()
        fpb = FPBInject(device)
        with patch("fpbinject.fpb_inject.ExecClient") as cls:
            cls.return_value.run.return_value = {"success": True}
            result = fpb.exec_cmd("ls", timeout=2, ack_timeout=0.5, max_retries=1)
        self.assertEqual(result, {"success": True})
        cls.assert_called_once_with(fpb._protocol)
        cls.return_value.run.assert_called_once_with(
            "ls", timeout=2, ack_timeout=0.5, max_retries=1
        )

    def test_exec_cmd_defaults(self):
        from fpbinject.fpb_inject import FPBInject

        fpb = FPBInject(MagicMock())
        with patch("fpbinject.fpb_inject.ExecClient") as cls:
            fpb.exec_cmd("ls")
        kwargs = cls.return_value.run.call_args.kwargs
        self.assertEqual(kwargs["timeout"], 10.0)
        self.assertIsNone(kwargs["max_retries"])


class TestSerialProtocolBits(unittest.TestCase):
    def setUp(self):
        self.device = MagicMock()
        self.device.ser = MagicMock()
        self.device.raw_serial_log = []
        self.device.raw_log_next_id = 0
        self.device.raw_log_max_size = 5000
        self.device.serial_echo_enabled = False
        self.protocol = FPBProtocol(self.device)

    def test_write_line_plain(self):
        self.device.serial_tx_fragment_size = 0
        self.protocol._write_line("fl -c ping")
        self.device.ser.write.assert_called_once_with(b"fl -c ping\n")
        self.device.ser.flush.assert_called()

    def test_write_line_fragments(self):
        self.device.serial_tx_fragment_size = 4
        self.device.serial_tx_fragment_delay = 0
        self.protocol._write_line("abcdefghij")
        sent = b"".join(c.args[0] for c in self.device.ser.write.call_args_list)
        self.assertEqual(sent, b"abcdefghij\n")
        self.assertEqual(self.device.ser.write.call_count, 3)

    def test_info_parses_exec_line(self):
        resp = (
            "[FLOK] Info complete\nFPBInject 1.0\nExec: enabled\n"
            "FileTransfer: enabled\n"
        )
        with patch.object(self.protocol, "send_cmd", return_value=resp):
            info, error = self.protocol.info()
        self.assertEqual(info["exec"], "enabled")
        self.assertEqual(info["file_transfer"], "enabled")

    def test_suspect_attribute_defaults_to_none(self):
        self.assertIsNone(self.protocol.exec_suspect_ser)


class TestConfigSchema(unittest.TestCase):
    def test_retries_tooltip_mentions_exec(self):
        from fpbinject.core.config_schema import get_schema_by_key

        self.assertIn("exec", get_schema_by_key("transfer_max_retries").tooltip)


class FakeWorker:
    """Stands in for DeviceWorker while an exec task occupies its thread.

    pump_rx() is the worker's normal RX step: read the port, append one entry
    to the raw serial log.
    """

    def __init__(self, device, on_thread=True):
        self.device = device
        self.on_thread = on_thread
        self.pumps = 0

    def is_worker_thread(self):
        return self.on_thread

    def pump_rx(self):
        self.pumps += 1
        ser = self.device.ser
        ser.in_pump = True
        try:
            n = ser.in_waiting
            if n:
                data = ser.read(n).decode(errors="replace")
                entry_id = self.device.raw_log_next_id
                self.device.raw_log_next_id += 1
                self.device.raw_serial_log.append({"id": entry_id, "data": data})
        finally:
            ser.in_pump = False


def make_worker_client(sim=None, chunk=0, **device_attrs):
    sim, device, protocol, client = make_client(sim, chunk, **device_attrs)
    device.ser.guard = True
    device.worker = FakeWorker(device)
    return sim, device, protocol, client


def panel_text(device):
    return "".join(entry["data"] for entry in device.raw_serial_log)


MULTILINE = "line one\nline two\n  indented three\nline four\n"


class TestReceiveSideIsUntouched(unittest.TestCase):
    """exec only adds to what is sent: the receive path and its log stay as
    they are, with or without a DeviceWorker."""

    def test_direct_mode_log_is_exactly_what_the_device_sent(self):
        sim, dev, _, client = make_client(chunk=7)
        sim.output = MULTILINE
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(panel_text(dev), dev.ser.emitted.decode())

    def test_direct_mode_never_flushes_the_receive_buffer(self):
        sim, dev, _, client = make_client()
        run(client)
        self.assertEqual(dev.ser.resets, 0)

    def test_direct_mode_pending_bytes_are_logged_not_lost(self):
        sim, dev, _, client = make_client()
        dev.ser._rx += b"late log line\n"
        r = run(client)
        self.assertTrue(r["success"])
        self.assertIn("late log line\n", panel_text(dev))

    def test_worker_mode_log_is_exactly_what_the_device_sent(self):
        sim, dev, _, client = make_worker_client(chunk=7)
        sim.output = MULTILINE
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(r["output"], MULTILINE)
        self.assertEqual(panel_text(dev), dev.ser.emitted.decode())

    def test_worker_mode_exec_never_reads_the_port_itself(self):
        sim, dev, _, client = make_worker_client(chunk=7)
        sim.output = MULTILINE
        run(client)
        self.assertEqual(dev.ser.stray_reads, 0)
        self.assertGreater(dev.worker.pumps, 0)

    def test_worker_mode_never_flushes_the_receive_buffer(self):
        sim, dev, _, client = make_worker_client()
        sim.damage_results = 1  # also covers the recovery query
        run(client)
        self.assertEqual(dev.ser.resets, 0)

    def test_worker_mode_pending_bytes_reach_the_log_and_are_not_parsed(self):
        sim, dev, _, client = make_worker_client()
        # a complete frame from earlier traffic is already waiting on the wire
        dev.ser._rx += b"late log line\n[FLOK] PONG\n[FLEND]\n"
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(r["output"], "out\n")
        self.assertIn("late log line\n", panel_text(dev))

    def test_worker_mode_older_log_entries_are_ignored(self):
        sim, dev, _, client = make_worker_client()
        dev.raw_serial_log.append(
            {"id": dev.raw_log_next_id, "data": "[FLERR] CRC mismatch: 1\n[FLEND]\n"}
        )
        dev.raw_log_next_id += 1
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(len(sim.calls), 1)

    def test_worker_mode_own_tx_echo_is_not_taken_for_a_response(self):
        sim, dev, _, client = make_worker_client(serial_echo_enabled=True)
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(r["output"], "out\n")
        self.assertIn("fl -c exec", panel_text(dev))  # the echo is still logged

    def test_worker_mode_recovers_a_damaged_result(self):
        sim, dev, _, client = make_worker_client(chunk=5)
        sim.damage_results = 1
        sim.ret = 7
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(r["ret"], 7)
        self.assertTrue(r["replayed"])
        self.assertEqual(len(sim.calls), 1)
        self.assertEqual(panel_text(dev), dev.ser.emitted.decode())

    def test_worker_mode_blocking_command_is_unknown(self):
        sim, dev, proto, client = make_worker_client()
        sim.hang = True
        r = run(client, timeout=0.15)
        self.assertEqual(r["error_code"], "unknown_state")
        self.assertEqual(dev.ser.stray_reads, 0)

    def test_worker_mode_retries_a_lost_request(self):
        sim, dev, _, client = make_worker_client()
        sim.lose_requests = 1
        r = run(client)
        self.assertTrue(r["success"])
        self.assertEqual(len(sim.calls), 1)

    def test_not_on_the_worker_thread_falls_back_to_reading_the_port(self):
        sim, dev, _, client = make_client()
        dev.worker = FakeWorker(dev, on_thread=False)
        r = run(client)
        self.assertTrue(r["success"])
        self.assertIsInstance(client._rx, exec_client._SerialRx)
        self.assertEqual(dev.worker.pumps, 0)

    def test_worker_without_pump_rx_falls_back(self):
        sim, dev, _, client = make_client()
        dev.worker = object()
        r = run(client)
        self.assertTrue(r["success"])
        self.assertIsInstance(client._rx, exec_client._SerialRx)

    def test_cursor_tolerates_the_log_being_cleared(self):
        sim, dev, _, client = make_worker_client()
        original = dev.worker.pump_rx

        def clearing_pump():
            original()
            if dev.worker.pumps == 3:
                dev.raw_serial_log = []  # the user cleared the SERIAL panel

        dev.worker.pump_rx = clearing_pump
        sim.output = "a\nb\n"
        r = run(client)
        self.assertIn(r["error_code"], ("", "unknown_state", "request_failed"))


class TestWithRealDeviceWorker(unittest.TestCase):
    """The real DeviceWorker running an exec task on its own thread."""

    def setUp(self):
        self.sim = FirmwareSim()
        self.device = MagicMock()
        self.device.ser = FakeSerial(self.sim, chunk=5)
        self.device.raw_serial_log = []
        self.device.raw_log_next_id = 0
        self.device.raw_log_max_size = 5000
        self.device.serial_log = []
        self.device.log_next_id = 0
        self.device.log_max_size = 1000
        self.device.log_file_enabled = False
        self.device.vserial = None
        self.device.serial_echo_enabled = False
        self.device.serial_tx_fragment_size = 0
        self.device.upload_chunk_size = 1024
        self.device.transfer_max_retries = 3
        self.worker = DeviceWorker(self.device)
        self.device.worker = self.worker
        self.worker.start()
        self.addCleanup(self.worker.stop)
        self.protocol = FPBProtocol(self.device)
        self.protocol._in_fl_mode = True

    def run_exec(self, cmd="ls", **kw):
        box = {}

        def task():
            kw.setdefault("timeout", RUN)
            kw.setdefault("ack_timeout", ACK)
            box["r"] = ExecClient(self.protocol).run(cmd, **kw)

        self.assertTrue(self.worker.run_in_worker(task, timeout=15))
        return box["r"]

    def test_is_worker_thread(self):
        seen = {}
        self.assertFalse(self.worker.is_worker_thread())
        self.worker.run_in_worker(
            lambda: seen.setdefault("v", self.worker.is_worker_thread()), timeout=5
        )
        self.assertTrue(seen["v"])

    def test_pump_rx_logs_like_the_normal_loop(self):
        self.device.ser._rx += b"hello\n"
        self.worker.run_in_worker(self.worker.pump_rx, timeout=5)
        self.assertEqual(panel_text(self.device), "hello\n")
        self.assertTrue(any(e["dir"] == "RX" for e in self.device.serial_log))

    def test_exec_through_the_worker_keeps_the_normal_log(self):
        self.sim.output = MULTILINE
        r = self.run_exec()
        self.assertTrue(r["success"])
        self.assertEqual(r["output"], MULTILINE)
        # SERIAL panel text == bytes on the wire, and the worker's own
        # formatted log (serial_log) saw the response lines too
        self.assertEqual(panel_text(self.device), self.device.ser.emitted.decode())
        rx_lines = "".join(
            e["data"] for e in self.device.serial_log if e["dir"] == "RX"
        )
        self.assertIn("line two", rx_lines)
        self.assertIn("  indented three", rx_lines)

    def test_sse_listeners_are_notified(self):
        self.worker._data_event.clear()
        self.run_exec()
        self.assertTrue(self.worker._data_event.is_set())

    def test_the_loop_resumes_polling_after_the_task(self):
        self.run_exec()
        self.device.ser._rx += b"async device log\n"
        deadline = time.time() + 2
        while time.time() < deadline and "async device log" not in panel_text(
            self.device
        ):
            time.sleep(0.02)
        self.assertIn("async device log\n", panel_text(self.device))


if __name__ == "__main__":
    unittest.main()
