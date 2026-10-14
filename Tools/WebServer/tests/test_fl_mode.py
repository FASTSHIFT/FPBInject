# -*- coding: utf-8 -*-
"""
fl-mode management: the one-time mode probe, leaving the loop with ``q`` and
the passive ``[FLEXIT]`` bookkeeping.

``ShellSim`` plays a NuttX-like console: an ``nsh>`` prompt where any
``fl ...`` line starts the fl loop (banner, first command, ``fl>`` prompt) and
``q`` leaves it again with ``[FLEXIT]``; or a ``oneshot`` port without any
loop.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpbinject.core.exec_client import ExecClient  # noqa: E402
from fpbinject.core.serial_protocol import (  # noqa: E402
    FPBProtocol,
    note_fl_markers,
)
from fpbinject.fpb_inject import FPBInject  # noqa: E402
from fpbinject.services.device_worker import DeviceWorker  # noqa: E402

BANNER = "FPBInject Function Loader (NuttX)\nType --cmd <command> or 'quit' to exit\n\n"


class ShellSim:
    """Serial port facing a NuttX-like console (or a oneshot port)."""

    def __init__(self, interactive=True, mode_line=True, silent=False):
        self.interactive = interactive
        self.mode_line = mode_line
        self.silent = silent  # never answers
        self.state = "nsh"  # "nsh" | "fl"
        self.rx = bytearray()
        self.written = bytearray()
        self.lines = []
        self.events = []  # "enter" / "exit"
        self.info_calls = 0
        self._partial = bytearray()

    # -- pyserial surface ---------------------------------------------------
    @property
    def in_waiting(self):
        return len(self.rx)

    def isOpen(self):
        return True

    def read(self, n=1):
        data = bytes(self.rx[:n])
        del self.rx[:n]
        return data

    def write(self, data):
        self.written += data
        self._partial += data
        while b"\n" in self._partial:
            line, _, rest = bytes(self._partial).partition(b"\n")
            self._partial = bytearray(rest)
            self.lines.append(line.decode())
            if not self.silent:
                self._handle(line.decode().strip())

    def flush(self):
        pass

    def reset_input_buffer(self):
        self.rx.clear()

    # -- the "device" ---------------------------------------------------------
    def _emit(self, text):
        self.rx += text.encode()

    def _prompt(self):
        self._emit("fl> " if self.state == "fl" else "nsh> ")

    def _fl_command(self, rest):
        if "-c info" in rest:
            self.info_calls += 1
            mode = "interactive" if self.interactive else "oneshot"
            self._emit("FPBInject v1.6.12\nBuild: Jan 1 2026 00:00:00\n")
            if self.mode_line:
                self._emit(f"Mode: {mode}\nPlatform: NuttX\n")
            self._emit("Exec: enabled\n[FLOK] Info complete\n[FLEND]\n")
        elif "-c ping" in rest:
            self._emit("[FLOK] PONG\n[FLEND]\n")
        else:
            self._emit("[FLOK] ok\n[FLEND]\n")

    def _handle(self, line):
        if line == "":
            self._prompt() if self.interactive else None
            return
        if line.startswith("fl "):
            if self.interactive and self.state == "nsh":
                self._emit(BANNER)  # the app starts and enters its loop
                self.state = "fl"
                self.events.append("enter")
            self._fl_command(line[3:])
            if self.interactive:
                self._prompt()
        elif line in ("q", "quit", "exit"):
            if self.state == "fl":
                self._emit("[FLEXIT]\n")
                self.state = "nsh"
                self.events.append("exit")
            else:
                self._emit(f"nsh: {line}: command not found\n")
            self._prompt()
        elif self.state == "fl":
            self._emit("fl_error: -3. Type 'q' to exit\n\nfl> ")
        else:
            self._emit(f"nsh: {line}: command not found\nnsh> ")

    def user_types(self, text):
        """The human types a line into the terminal (the host did not ask)."""
        self._handle(text)


def make_device(ser, wakeup=3):
    device = MagicMock()
    device.ser = ser
    device.raw_serial_log = []
    device.raw_log_next_id = 0
    device.raw_log_max_size = 5000
    device.serial_echo_enabled = False
    device.serial_tx_fragment_size = 0
    device.wakeup_shell_cnt = wakeup
    device.fl_exit_seen = 0
    return device


def make_protocol(sim, **kw):
    device = make_device(sim, **kw)
    return device, FPBProtocol(device)


class TestModeProbe(unittest.TestCase):
    def test_first_command_is_fl_info_after_the_wakeup_newlines(self):
        sim = ShellSim()
        _, proto = make_protocol(sim, wakeup=2)
        proto.send_cmd("-c ping")
        self.assertEqual(sim.lines[:3], ["", "", "fl -c info"])
        self.assertEqual(sim.lines[3], "fl -c ping")

    def test_interactive_device_is_learned_from_info(self):
        sim = ShellSim()
        _, proto = make_protocol(sim)
        proto.send_cmd("-c ping")
        self.assertTrue(proto.interactive)
        self.assertEqual(proto.platform_desc, "NuttX")
        self.assertTrue(proto._in_fl_mode)

    def test_probe_happens_only_once_per_port(self):
        sim = ShellSim()
        _, proto = make_protocol(sim)
        proto.send_cmd("-c ping")
        proto.send_cmd("-c ping")
        proto.send_cmd("-c ping")
        self.assertEqual(sim.info_calls, 1)

    def test_no_bare_fl_line_and_no_banner_dependence(self):
        sim = ShellSim()
        _, proto = make_protocol(sim)
        proto.send_cmd("-c ping")
        self.assertNotIn("fl", sim.lines)  # the old explicit 'fl' entry
        self.assertEqual(sim.events, ["enter"])  # entered by the command itself

    def test_banner_in_the_reply_does_not_disturb_mode_parsing(self):
        sim = ShellSim()
        _, proto = make_protocol(sim)
        info, _ = proto.info()
        self.assertEqual(info["mode"], "interactive")
        self.assertEqual(info["platform"], "NuttX")

    def test_oneshot_device_never_enters_or_exits(self):
        sim = ShellSim(interactive=False)
        _, proto = make_protocol(sim)
        proto.send_cmd("-c ping")
        self.assertFalse(proto.interactive)
        self.assertFalse(proto._in_fl_mode)
        sim.lines.clear()
        self.assertTrue(proto.exit_fl_mode())
        self.assertEqual(sim.lines, [])

    def test_missing_mode_line_is_treated_as_oneshot(self):
        sim = ShellSim(mode_line=False)
        _, proto = make_protocol(sim)
        proto.send_cmd("-c ping")
        self.assertFalse(proto.interactive)
        self.assertEqual(sim.info_calls, 1)
        proto.send_cmd("-c ping")
        self.assertEqual(sim.info_calls, 1)  # learned: not probed again

    def test_new_serial_object_is_probed_again(self):
        sim = ShellSim()
        device, proto = make_protocol(sim)
        proto.send_cmd("-c ping")
        sim2 = ShellSim(interactive=False)
        device.ser = sim2
        proto.send_cmd("-c ping")
        self.assertEqual(sim2.info_calls, 1)
        self.assertFalse(proto.interactive)
        self.assertFalse(proto._in_fl_mode)

    def test_unanswered_probe_is_retried_by_the_next_command(self):
        sim = ShellSim(silent=True)
        _, proto = make_protocol(sim, wakeup=0)
        proto.send_cmd("-c ping", timeout=0.05, max_retries=0)
        self.assertIsNone(proto._mode_ser)
        self.assertFalse(proto._in_fl_mode)
        sim.silent = False
        proto.send_cmd("-c ping")
        self.assertTrue(proto.interactive)

    def test_no_serial_port_raises(self):
        device, proto = make_protocol(ShellSim())
        device.ser = None
        with self.assertRaises(Exception):
            proto.send_cmd("-c ping")


class TestLeavingTheLoop(unittest.TestCase):
    def setUp(self):
        self.sim = ShellSim()
        self.device, self.proto = make_protocol(self.sim, wakeup=0)
        self.proto.send_cmd("-c ping")  # probe + enter
        self.sim.lines.clear()

    def test_exit_sends_a_single_q_and_sees_flexit(self):
        self.assertTrue(self.proto.exit_fl_mode())
        self.assertEqual(self.sim.lines, ["q"])
        self.assertEqual(self.sim.state, "nsh")
        self.assertFalse(self.proto._in_fl_mode)

    def test_nothing_is_sent_that_the_shell_would_complain_about(self):
        self.proto.exit_fl_mode()
        self.assertNotIn("fldet", self.sim.lines)

    def test_next_command_reenters_without_a_probe(self):
        self.proto.exit_fl_mode()
        self.sim.lines.clear()
        self.proto.send_cmd("-c ping")
        self.assertEqual(self.sim.lines, ["fl -c ping"])
        self.assertEqual(self.sim.events, ["enter", "exit", "enter"])
        self.assertTrue(self.proto._in_fl_mode)
        self.assertEqual(self.sim.info_calls, 1)

    def test_exit_when_not_in_the_loop_is_a_noop(self):
        self.proto.exit_fl_mode()
        self.sim.lines.clear()
        self.assertTrue(self.proto.exit_fl_mode())
        self.assertEqual(self.sim.lines, [])

    def test_drift_device_already_at_the_shell(self):
        # the host thinks it is in the loop, the device was reset meanwhile
        self.sim.state = "nsh"
        self.assertTrue(self.proto.exit_fl_mode())
        self.assertFalse(self.proto._in_fl_mode)
        self.assertEqual(self.sim.lines, ["q"])  # one try is enough

    def test_unconfirmed_exit_keeps_the_flag_and_gives_up_after_three_tries(self):
        self.sim.silent = True
        self.assertFalse(self.proto.exit_fl_mode(timeout=0.05))
        self.assertEqual(self.sim.lines, ["q", "q", "q"])
        self.assertTrue(self.proto._in_fl_mode)

    def test_exit_after_a_stuck_exec_tries_only_once(self):
        self.proto.exec_suspect_ser = self.sim
        self.sim.silent = True
        self.assertFalse(self.proto.exit_fl_mode(timeout=0.05))
        self.assertEqual(self.sim.lines, ["q"])

    def test_fl_session_leaves_the_loop(self):
        fpb = FPBInject(self.device)
        fpb._protocol = self.proto
        with fpb.fl_session():
            self.proto.send_cmd("-c ping")
            self.assertEqual(self.sim.state, "fl")
        self.assertEqual(self.sim.state, "nsh")


class TestPassiveExitTracking(unittest.TestCase):
    def setUp(self):
        self.sim = ShellSim()
        self.device, self.proto = make_protocol(self.sim, wakeup=0)
        self.proto.send_cmd("-c ping")
        self.sim.lines.clear()

    def test_user_typing_q_is_noticed_without_sending_anything(self):
        self.sim.user_types("q")
        note_fl_markers(self.device, self.sim.read(100).decode())
        self.assertTrue(self.proto.exit_fl_mode())
        self.assertEqual(self.sim.lines, [])
        self.assertFalse(self.proto._in_fl_mode)

    def test_marker_arriving_late_after_a_failed_exit(self):
        self.sim.silent = True
        self.assertFalse(self.proto.exit_fl_mode(timeout=0.05))
        note_fl_markers(self.device, "[FLEXIT]\nnsh> ")
        self.sim.lines.clear()
        self.assertTrue(self.proto.exit_fl_mode())
        self.assertEqual(self.sim.lines, [])

    def test_a_new_command_after_the_marker_marks_the_loop_again(self):
        note_fl_markers(self.device, "[FLEXIT]\n")
        self.proto.send_cmd("-c ping")
        self.assertTrue(self.proto._in_fl_mode)
        self.sim.lines.clear()
        self.proto.exit_fl_mode()
        self.assertEqual(self.sim.lines, ["q"])

    def test_our_own_exit_does_not_leave_a_stale_count(self):
        self.proto.exit_fl_mode()
        self.proto.send_cmd("-c ping")
        self.sim.lines.clear()
        self.proto.exit_fl_mode()
        self.assertEqual(self.sim.lines, ["q"])

    def test_protocol_reads_feed_the_counter(self):
        before = self.device.fl_exit_seen
        self.proto.exit_fl_mode()
        self.assertGreater(self.device.fl_exit_seen, before)

    def test_note_ignores_text_without_a_marker_and_odd_devices(self):
        note_fl_markers(self.device, "nsh> ")
        self.assertEqual(self.device.fl_exit_seen, 0)
        odd = MagicMock()
        odd.fl_exit_seen = "x"  # not a number: treated as 0
        note_fl_markers(odd, "[FLEXIT]")
        self.assertEqual(odd.fl_exit_seen, 1)


class TestWorkerFeedsTheCounter(unittest.TestCase):
    def test_background_read_of_a_user_q_counts(self):
        sim = ShellSim()
        device = make_device(sim, wakeup=0)
        device.serial_log = []
        device.log_next_id = 0
        device.log_max_size = 1000
        device.log_file_enabled = False
        device.vserial = None
        worker = DeviceWorker(device)
        worker._data_event = MagicMock()
        proto = FPBProtocol(device)
        proto.send_cmd("-c ping")
        sim.user_types("q")
        worker._process_serial_rx()  # what the worker loop does when idle
        sim.lines.clear()
        self.assertTrue(proto.exit_fl_mode())
        self.assertEqual(sim.lines, [])


class TestExecUsesTheSameState(unittest.TestCase):
    def test_exec_probes_once_and_marks_the_loop(self):
        sim = ShellSim()
        device, proto = make_protocol(sim, wakeup=0)
        device.upload_chunk_size = 64
        device.transfer_max_retries = 0
        ExecClient(proto).run("ls", timeout=0.2, ack_timeout=0.1, max_retries=0)
        self.assertEqual(sim.info_calls, 1)
        self.assertEqual(sim.lines[0], "fl -c info")
        self.assertTrue(proto._in_fl_mode)  # exec's request started the loop
        sim.lines.clear()
        self.assertTrue(proto.exit_fl_mode())
        self.assertEqual(sim.lines, ["q"])

    def test_exec_on_oneshot_never_marks_the_loop(self):
        sim = ShellSim(interactive=False)
        device, proto = make_protocol(sim, wakeup=0)
        device.upload_chunk_size = 64
        ExecClient(proto).run("ls", timeout=0.2, ack_timeout=0.1, max_retries=0)
        self.assertFalse(proto._in_fl_mode)
        self.assertTrue(proto.exit_fl_mode())


if __name__ == "__main__":
    unittest.main()
