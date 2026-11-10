# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech
"""Request/reply barrier for the fl serial protocol.

The protocol has no request id. After a timeout the late reply is taken for
the answer to the next command and every later reply is off by one, so a
failure is booked on the wrong command. The shell runs lines in order: send
``echo`` with a random payload and read until its own reply comes by;
everything before it is stale (logged, not interpreted).
"""

import logging
import secrets
import time

from fpbinject.core.state import tool_log
from fpbinject.utils.crc import crc16

logger = logging.getLogger(__name__)

# Seconds to wait for one barrier reply before sending another barrier
ROUND_TIMEOUT = 2.0


def resync_barrier(proto, total_timeout, log_tx, log_rx) -> bool:
    """Run the barrier on ``proto`` (an FPBProtocol). False if no answer."""
    ser = proto.device.ser
    deadline = time.time() + total_timeout
    rounds = 0
    while time.time() < deadline:
        rounds += 1
        token = secrets.token_hex(secrets.choice(range(6, 13)))
        crc = crc16(token.encode("ascii"))
        want = f"ECHO {len(token) // 2} Bytes, CRC 0x{crc:04X}"
        line = f"fl -c echo -d {token}"
        proto._log_raw(log_tx, line)
        proto._write_line(line)

        buf = ""
        found = False
        t_end = min(deadline, time.time() + ROUND_TIMEOUT)
        while time.time() < t_end:
            if ser.in_waiting:
                buf += ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                pos = buf.find(want)
                if pos >= 0 and "[FLEND]" in buf[pos:]:
                    found = True
                    break
            else:
                time.sleep(0.0005)
        if found:
            # also take the prompt that follows the reply
            buf += proto._drain_serial(ser, idle=0.03, max_wait=0.2)
        proto._log_raw(log_rx, buf)
        if found:
            logger.debug(f"resync done after {rounds} round(s)")
            return True
        logger.warning(f"resync: no reply to the barrier (round {rounds})")
    tool_log(proto.device, "ERROR", "Device does not answer, cannot resync")
    return False
