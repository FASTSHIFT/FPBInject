#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Reliable remote command execution over the fl protocol (the ``exec`` command).

Wire format (see docs/exec-command-design.md)::

    request : fl -c exec -d <base64(cmd)> --seq <id> --timeout <ms> -r 0x<crc>
    query   : fl -c exec --seq <id> -r 0x<crc>              (never executes)
    response:
        [FLEXEC] seq=<id> crc=0x<crc>                       (command starting)
        <command stdout / stderr>
        [FLOK] EXEC seq=<id> ret=<n> crc=0x<crc>
        [FLEND]

CRC-16 (little-endian integers, init 0xFFFF):

    request : seq(i32) + timeout(u32) + len(u32) + command bytes
    start   : seq(i32)
    result  : seq(i32) + ret(i32)

Why this is not built on ``FPBProtocol.send_cmd``: send_cmd resends the whole
command when it does not see a response, which would run a non-idempotent
command twice. Here a resend is only done while the device has provably not
started the command (no start line seen); once the start line is seen the
request is never resent, and a damaged result line is recovered with a
read-only query instead.
"""

import base64
import codecs
import logging
import re
import secrets
import struct
import time
from typing import List, Optional

from fpbinject.core.config_schema import (
    DEFAULT_TRANSFER_MAX_RETRIES,
    DEFAULT_UPLOAD_CHUNK_SIZE,
)
from fpbinject.core.serial_protocol import FPBProtocolError, LogDirection
from fpbinject.core.state import tool_log
from fpbinject.utils.crc import crc16_update

logger = logging.getLogger(__name__)

START_MARKER = "[FLEXEC]"
FRAME_END = "[FLEND]"

# Largest --timeout the device accepts (C int, milliseconds)
MAX_TIMEOUT_MS = 2**31 - 1
# seq is a C int; random values avoid colliding with the device's cached seq
# from a previous host session.
SEQ_SPACE = 2**31

# Same ceiling as the transfer_max_retries config item
MAX_RETRIES_LIMIT = 20
DEFAULT_MAX_OUTPUT = 256 * 1024
# A single output line longer than this is flushed even without a newline
MAX_PENDING_LINE = 64 * 1024

# After a valid result line, wait this long for the closing [FLEND] only
RESULT_GRACE_S = 0.3
POLL_INTERVAL_S = 0.002

# error_code values reported to callers
ERR_NOT_SUPPORTED = "not_supported"
ERR_TOO_LONG = "too_long"
ERR_DEVICE_SUSPECT = "device_suspect"
ERR_REQUEST_FAILED = "request_failed"
ERR_UNKNOWN_STATE = "unknown_state"
ERR_SPAWN_FAILED = "spawn_failed"
ERR_DEVICE_ERROR = "device_error"
ERR_BUSY = "busy"

_START_RE = re.compile(r"\[FLEXEC\] seq=(-?\d+) crc=0x([0-9A-Fa-f]{4})\s*$")
_RESULT_RE = re.compile(
    r"\[(FLOK|FLERR)\] EXEC seq=(-?\d+) ret=(-?\d+) crc=0x([0-9A-Fa-f]{4})"
    r"(?P<replay> replay=1)?(?: spawn failed)?\s*$"
)
_NO_RECORD_RE = re.compile(r"\[FLERR\] EXEC seq=(-?\d+) no record\s*$")
_MARKER_RE = re.compile(r"\[(FLOK|FLERR)\]")

# Device replies that mean "the request was damaged in transit and nothing was
# executed", so the whole request may safely be sent again.
_RETRIABLE_ERRORS = ("CRC mismatch", "Invalid base64", "Invalid arguments")


class ExecArgumentError(ValueError):
    """Raised for invalid exec arguments (nothing is sent to the device)."""


# ---------------------------------------------------------------------------
# Pure helpers (also used by tests and the SDK to compute budgets)
# ---------------------------------------------------------------------------
def request_crc(seq: int, timeout_ms: int, cmd: bytes) -> int:
    """CRC of an exec request: seq + timeout + len + command bytes."""
    crc = crc16_update(0xFFFF, struct.pack("<iII", seq, timeout_ms, len(cmd)))
    return crc16_update(crc, cmd) if cmd else crc


def start_crc(seq: int) -> int:
    """CRC carried by the ``[FLEXEC]`` start line."""
    return crc16_update(0xFFFF, struct.pack("<i", seq))


def result_crc(seq: int, ret: int) -> int:
    """CRC carried by the ``EXEC ... ret=`` result line."""
    return crc16_update(0xFFFF, struct.pack("<ii", seq, ret))


def _b64_len(n: int) -> int:
    return ((n + 2) // 3) * 4


def max_command_bytes(upload_chunk_size: int, seq: int, timeout_ms: int) -> int:
    """Longest command that still fits the device's line buffer.

    Same approach as ``write_memory``: take the line length of a proven-safe
    fwrite (derived from the calibrated upload chunk size) as the budget and
    subtract the fixed overhead of the exec request. The overhead uses the
    actual digits of ``seq`` and ``timeout_ms``.
    """
    chunk = upload_chunk_size if upload_chunk_size and upload_chunk_size > 0 else 0
    if not chunk:
        chunk = DEFAULT_UPLOAD_CHUNK_SIZE
    budget = _b64_len(chunk) + len("fl -c fwrite -d  -r 65535")
    overhead = len(f"fl -c exec -d  --seq {seq} --timeout {timeout_ms} -r 0xFFFF")
    return max(0, ((budget - overhead) // 4) * 3)


def default_max_retries(device) -> int:
    """Resend budget used when the caller does not give one.

    Shares the ``transfer_max_retries`` setting with file transfer (CLI
    ``--transfer-max-retries`` / config), so one knob tunes how hard the tool
    fights a lossy serial link.
    """
    value = getattr(device, "transfer_max_retries", None)
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_TRANSFER_MAX_RETRIES
    return max(0, min(value, MAX_RETRIES_LIMIT))


def worst_case_seconds(timeout: float, ack_timeout: float, max_retries: int) -> float:
    """Upper bound on how long one exec call can take.

    Callers that put a time limit around the call (the HTTP route's worker
    window, the SDK's HTTP client) must allow at least this long, otherwise
    they give up while the client is still legitimately waiting. Covers the
    liveness probe, every resend, the command's own wait and the result
    recovery queries.
    """
    attempts = max_retries + 1
    return timeout + 2.0 * (ack_timeout + 0.5) * attempts + 15.0


def validate_args(cmd, timeout, ack_timeout, max_retries):
    """Validate user supplied arguments.

    Returns:
        (command bytes, timeout in milliseconds)

    Raises:
        ExecArgumentError: if anything is out of range.
    """
    if not isinstance(cmd, str) or not cmd.strip():
        raise ExecArgumentError("cmd must be a non-empty string")
    if "\x00" in cmd:
        raise ExecArgumentError("cmd must not contain NUL characters")

    for name, value in (("timeout", timeout), ("ack_timeout", ack_timeout)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ExecArgumentError(f"{name} must be a number")
        if not value > 0:
            raise ExecArgumentError(f"{name} must be greater than 0")

    timeout_ms = int(round(timeout * 1000))
    if timeout_ms < 1 or timeout_ms > MAX_TIMEOUT_MS:
        raise ExecArgumentError(
            f"timeout out of range (max {MAX_TIMEOUT_MS // 1000} seconds)"
        )

    if (
        isinstance(max_retries, bool)
        or not isinstance(max_retries, int)
        or not 0 <= max_retries <= MAX_RETRIES_LIMIT
    ):
        raise ExecArgumentError(f"max_retries must be an integer 0-{MAX_RETRIES_LIMIT}")

    return cmd.encode("utf-8"), timeout_ms


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------
class _Result:
    """A result line addressed to our request."""

    def __init__(self, ok: bool, ret: int, crc_ok: bool, replay: bool):
        self.ok = ok
        self.ret = ret
        self.crc_ok = crc_ok
        self.replay = replay


class ExecResponseParser:
    """Incremental parser for the response to one exec request (or query).

    Feed it decoded serial text. It tolerates noise around the protocol lines
    (prompt, echo of the request, a command that did not end its output with a
    newline) and ignores lines belonging to other requests.
    """

    def __init__(self, seq: int, max_output: int = DEFAULT_MAX_OUTPUT):
        self.seq = seq
        self.max_output = max_output
        self.started = False  # a start line was seen (valid or not)
        self.result: Optional[_Result] = None
        self.no_record = False  # query answered "no record"
        self.frame_error = ""  # message of a response without EXEC result line
        self.complete = False  # closing [FLEND] seen
        self.truncated = False
        self._pending = ""
        self._lines: List[str] = []
        self._size = 0
        self._unterminated = False

    # -- public -----------------------------------------------------------
    @property
    def maybe_started(self) -> bool:
        """True once a start line, or the beginning of one, has arrived."""
        return self.started or START_MARKER in self._pending

    def feed(self, text: str) -> None:
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            self._line(line.rstrip("\r"))
        # Output without any newline must not grow without bound
        if len(self._pending) > MAX_PENDING_LINE:
            line, self._pending = self._pending, ""
            self._line(line)

    def output(self) -> str:
        """Command output captured between the start line and the result."""
        lines = self._lines
        if not self.started:
            # Start line lost: drop the echo of our own request and the noise.
            lines = [ln for ln in lines if " -c exec " not in ln]
        text = "\n".join(lines)
        if lines and not self._unterminated:
            text += "\n"
        return text

    # -- internals --------------------------------------------------------
    def _add_output(self, line: str) -> None:
        if self._size >= self.max_output:
            self.truncated = True
            return
        room = self.max_output - self._size
        if len(line) + 1 > room:
            line = line[:room]
            self.truncated = True
        self._lines.append(line)
        self._size += len(line) + 1

    def _line(self, line: str) -> None:
        if self.complete:
            return

        if FRAME_END in line:
            # A stray [FLEND] (e.g. from the previous command) before anything
            # of ours has shown up is just noise.
            if self.started or self.result or self.frame_error or self.no_record:
                self.complete = True
            return

        if START_MARKER in line:
            self._start_line(line)
            return

        m = _RESULT_RE.search(line)
        if m:
            self._result_line(line, m)
            return

        m = _NO_RECORD_RE.search(line)
        if m:
            if int(m.group(1)) == self.seq:
                self.no_record = True
            return

        marker = _MARKER_RE.search(line)
        if marker:
            # A response line we do not understand. After our start line it is
            # most likely our own result line damaged in transit; before it, it
            # is the device's reply to a request that was rejected.
            if not self.started and not self.frame_error:
                self.frame_error = line[marker.start() :].strip()
            return

        self._unterminated = False
        self._add_output(line)

    def _start_line(self, line: str) -> None:
        if self.started:
            return
        m = _START_RE.search(line)
        if m:
            seq = int(m.group(1))
            if int(m.group(2), 16) == start_crc(seq) and seq != self.seq:
                return  # intact start line of another request: stale
        # Ours, or damaged: either way the device accepted a request, so assume
        # it started and never resend (a wrong guess only costs a retry).
        self.started = True
        self._lines = []
        self._size = 0
        self._unterminated = False

    def _result_line(self, line: str, m) -> None:
        seq = int(m.group(2))
        if seq != self.seq:
            return
        ret = int(m.group(3))
        prefix = line[: m.start()]
        if prefix:
            # The command did not end its output with a newline
            self._add_output(prefix)
            self._unterminated = True
        self.result = _Result(
            ok=m.group(1) == "FLOK",
            ret=ret,
            crc_ok=int(m.group(4), 16) == result_crc(seq, ret),
            replay=m.group("replay") is not None,
        )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class ExecClient:
    """Runs a command on the device through the fl ``exec`` command."""

    def __init__(self, protocol):
        self.protocol = protocol
        self.device = protocol.device
        self._max_output = DEFAULT_MAX_OUTPUT

    # -- public -----------------------------------------------------------
    def run(
        self,
        cmd: str,
        timeout: float = 10.0,
        ack_timeout: float = 1.0,
        max_retries: Optional[int] = None,
        max_output: int = DEFAULT_MAX_OUTPUT,
    ) -> dict:
        """Execute ``cmd`` on the device and return a result dict.

        Keys: success, ret, output, replayed, started, output_truncated,
        elapsed_ms, error_code, error. Protocol-level outcomes (unknown state,
        suspect device, command too long, ...) are reported in the dict;
        ``ExecArgumentError`` is raised only for invalid arguments and
        ``FPBProtocolError`` when no serial port is open.
        """
        t0 = time.monotonic()
        self._max_output = max_output
        if max_retries is None:
            max_retries = default_max_retries(self.device)
        cmd_bytes, timeout_ms = validate_args(cmd, timeout, ack_timeout, max_retries)

        ser = self.device.ser
        if not ser:
            raise FPBProtocolError("Serial port not connected")

        seq = secrets.randbelow(SEQ_SPACE)
        limit = max_command_bytes(
            getattr(self.device, "upload_chunk_size", 0), seq, timeout_ms
        )
        if len(cmd_bytes) > limit:
            return self._fail(
                t0,
                ERR_TOO_LONG,
                f"Command is {len(cmd_bytes)} bytes, the current serial settings "
                f"allow {limit}. Upload a script and run it instead.",
            )

        if self.protocol.exec_suspect_ser is ser and not self._probe_alive(ack_timeout):
            return self._fail(
                t0,
                ERR_DEVICE_SUSPECT,
                "A previous exec did not finish and the device does not answer. "
                "The command may still be running; wait for it to end or reset "
                "the device.",
            )
        self.protocol.exec_suspect_ser = None

        tool_log(self.device, "INFO", f"exec seq={seq}: {cmd}")
        outcome = self._execute(
            t0, ser, seq, cmd_bytes, timeout, timeout_ms, ack_timeout, max_retries
        )
        level = "SUCCESS" if outcome["success"] else "ERROR"
        detail = f"ret={outcome['ret']}" if outcome["success"] else outcome["error"]
        tool_log(self.device, level, f"exec seq={seq} done: {detail}")
        return outcome

    # -- request / retry loop ----------------------------------------------
    def _execute(
        self, t0, ser, seq, cmd_bytes, timeout, timeout_ms, ack_timeout, max_retries
    ) -> dict:
        crc = request_crc(seq, timeout_ms, cmd_bytes)
        b64 = base64.b64encode(cmd_bytes).decode("ascii")
        line = f"fl -c exec -d {b64} --seq {seq} --timeout {timeout_ms} -r 0x{crc:04X}"
        last_note = "no response from the device"

        for attempt in range(max_retries + 1):
            if attempt:
                logger.warning(f"exec seq={seq}: resend {attempt}/{max_retries}")
            parser = ExecResponseParser(seq, self._max_output)
            self.protocol.try_enter_fl_mode()
            self._send(ser, line)
            self._collect(ser, parser, ack_timeout, timeout)

            result = parser.result
            if result is not None and result.crc_ok:
                return self._done(t0, parser, result)

            if result is not None or (parser.complete and parser.started):
                # The device ran the command (or at least started it) but the
                # result line is missing or damaged: ask for it again. A query
                # never executes anything.
                return self._recover(t0, ser, seq, parser, ack_timeout, max_retries)

            if parser.complete and parser.frame_error:
                msg = parser.frame_error
                if "No exec_cb" in msg:
                    return self._fail(
                        t0,
                        ERR_NOT_SUPPORTED,
                        "The device firmware has no exec support (exec_cb not set)",
                    )
                if any(text in msg for text in _RETRIABLE_ERRORS):
                    last_note = msg
                    continue  # damaged in transit, nothing was executed
                return self._fail(t0, ERR_DEVICE_ERROR, msg)

            if parser.maybe_started:
                return self._unknown(t0, ser, parser, timeout)

            last_note = "no response from the device"

        return self._fail(
            t0,
            ERR_REQUEST_FAILED,
            f"Request not acknowledged after {max_retries + 1} attempt(s): {last_note}",
        )

    def _recover(self, t0, ser, seq, parser, ack_timeout, max_retries) -> dict:
        """Fetch the cached result of an executed request with a query."""
        q_crc = request_crc(seq, 0, b"")
        query = f"fl -c exec --seq {seq} -r 0x{q_crc:04X}"
        wait = max(ack_timeout, 0.5)

        for _ in range(max_retries + 1):
            q = ExecResponseParser(seq)
            self._send(ser, query)
            self._collect(ser, q, wait, wait)
            if q.result is not None and q.result.crc_ok:
                return self._done(t0, parser, q.result, replayed=True)
            if q.no_record:
                break

        return self._unknown(
            t0,
            ser,
            parser,
            None,
            "The command ran but its result could not be recovered",
        )

    # -- serial I/O ---------------------------------------------------------
    def _send(self, ser, line: str) -> None:
        ser.reset_input_buffer()
        self.protocol._log_raw(LogDirection.TX, line)
        self.protocol._write_line(line)

    def _collect(self, ser, parser, ack_timeout: float, run_timeout: float) -> None:
        """Read until the response is complete or a deadline passes.

        Phase one waits ``ack_timeout`` for the device to answer. As soon as a
        start line shows up the deadline moves to ``run_timeout`` from then on.
        """
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        deadline = time.monotonic() + ack_timeout
        running = False
        grace = False

        while time.monotonic() < deadline:
            n = ser.in_waiting
            if not n:
                time.sleep(POLL_INTERVAL_S)
                continue

            text = decoder.decode(ser.read(n))
            if not text:
                continue
            self.protocol._log_raw(LogDirection.RX, text.strip())
            parser.feed(text)
            if parser.complete:
                return

            now = time.monotonic()
            if parser.maybe_started and not running:
                running = True
                deadline = now + run_timeout
            if parser.result is not None and not grace:
                # The result line is in; only the closing [FLEND] is outstanding
                grace = True
                deadline = min(deadline, now + RESULT_GRACE_S)

    def _probe_alive(self, wait: float) -> bool:
        """Check that the device answers again (ping).

        ``FPBProtocol.ping`` is not usable here: it reports success for an
        empty reply.
        """
        try:
            resp = self.protocol.send_cmd(
                "-c ping",
                timeout=max(wait, 0.5),
                retry_on_missing_cmd=False,
                max_retries=0,
            )
        except Exception as e:
            logger.debug(f"exec: liveness probe failed: {e}")
            return False
        return "[FLOK]" in resp

    # -- result builders ----------------------------------------------------
    def _result(self, t0, success, ret=None, output="", **kw) -> dict:
        return {
            "success": success,
            "ret": ret,
            "output": output,
            "replayed": kw.get("replayed", False),
            "started": kw.get("started", False),
            "output_truncated": kw.get("truncated", False),
            "elapsed_ms": round((time.monotonic() - t0) * 1000.0, 1),
            "error_code": kw.get("error_code", ""),
            "error": kw.get("error", ""),
        }

    def _done(self, t0, parser, result, replayed=None) -> dict:
        replayed = result.replay if replayed is None else replayed
        if result.ok:
            return self._result(
                t0,
                True,
                ret=result.ret,
                output=parser.output(),
                replayed=replayed,
                started=True,
                truncated=parser.truncated,
            )
        return self._result(
            t0,
            False,
            ret=result.ret,
            output=parser.output(),
            replayed=replayed,
            started=True,
            truncated=parser.truncated,
            error_code=ERR_SPAWN_FAILED,
            error=(
                "The device could not start the command "
                f"(errno {-result.ret} on the device)"
            ),
        )

    def _fail(self, t0, code: str, message: str) -> dict:
        return self._result(t0, False, error_code=code, error=message)

    def _unknown(self, t0, ser, parser, timeout, note: str = "") -> dict:
        """The device never reported an outcome: remember it and say so."""
        self.protocol.exec_suspect_ser = ser
        waited = f" within {timeout:g}s" if timeout else ""
        detail = note or f"The command did not finish{waited}"
        return self._result(
            t0,
            False,
            output=parser.output(),
            started=parser.maybe_started,
            truncated=parser.truncated,
            error_code=ERR_UNKNOWN_STATE,
            error=(
                f"{detail}. It may still be running or may have finished; the "
                "device has no exec timeout, so wait for it to end or reset the device."
            ),
        )
