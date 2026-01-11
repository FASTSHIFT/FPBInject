#!/usr/bin/env python3
"""
FPB Loader - Host tool for FPBInject runtime code injection

Features:
- ELF symbol extraction
- Patch source compilation
- Binary upload with CRC-16 checksum
- Retransmission for reliable transfer
- Interactive command mode

Usage:
    fpb_loader.py --port /dev/ttyUSB0 --upload patch.bin
    fpb_loader.py --port /dev/ttyUSB0 --compile patch.c --upload
    fpb_loader.py --port /dev/ttyUSB0 --interactive
"""

import argparse
import struct
import time
import sys
import os
import subprocess
import tempfile
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Optional, List, Tuple, BinaryIO

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)

# =============================================================================
# Protocol Constants
# =============================================================================

SOF = 0xAA
EOF = 0x55

MAX_PAYLOAD = 512
CHUNK_SIZE = 256  # Upload chunk size
TIMEOUT = 2.0     # Response timeout in seconds
MAX_RETRIES = 3   # Maximum retransmission attempts


class CmdType(IntEnum):
    """Command types matching func_loader.h"""
    PING = 0x00
    ACK = 0x01
    NACK = 0x02
    INFO = 0x10
    UPLOAD = 0x20
    UPLOAD_END = 0x21
    EXEC = 0x22
    CALL = 0x23
    READ = 0x30
    WRITE = 0x31
    PATCH = 0x40
    UNPATCH = 0x41
    LOG = 0xF0
    ERROR = 0xFF


class ErrorCode(IntEnum):
    """Error codes matching func_loader.h"""
    NONE = 0
    CRC = 1
    TIMEOUT = 2
    CMD = 3
    PARAM = 4
    SEQ = 5
    OVERFLOW = 6
    EXEC = 7


# =============================================================================
# CRC-16-CCITT Implementation
# =============================================================================

CRC16_TABLE = [
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
    0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
    0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,
    0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
    0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,
    0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
    0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
    0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
    0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,
    0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
    0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,
    0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
    0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,
    0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
    0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
    0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
    0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
    0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
    0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,
    0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
    0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
    0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
    0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,
    0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
    0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,
    0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
    0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,
    0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
    0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,
    0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
    0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,
    0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0
]


def crc16(data: bytes) -> int:
    """Calculate CRC-16-CCITT checksum."""
    crc = 0xFFFF
    for byte in data:
        crc = ((crc << 8) ^ CRC16_TABLE[(crc >> 8) ^ byte]) & 0xFFFF
    return crc


# =============================================================================
# Frame Data Structure
# =============================================================================

@dataclass
class Frame:
    """Protocol frame structure."""
    seq: int
    cmd: CmdType
    payload: bytes

    def encode(self) -> bytes:
        """Encode frame to bytes for transmission."""
        # Calculate CRC over seq + cmd + payload
        crc_data = bytes([self.seq, self.cmd]) + self.payload
        crc = crc16(crc_data)

        # Build frame
        length = len(self.payload)
        header = bytes([
            SOF,
            (length >> 8) & 0xFF,
            length & 0xFF,
            self.seq,
            self.cmd
        ])
        footer = bytes([
            (crc >> 8) & 0xFF,
            crc & 0xFF,
            EOF
        ])

        return header + self.payload + footer

    @classmethod
    def decode(cls, data: bytes) -> Optional['Frame']:
        """Decode frame from bytes. Returns None if invalid."""
        if len(data) < 8:  # Minimum frame size
            return None

        if data[0] != SOF or data[-1] != EOF:
            return None

        length = (data[1] << 8) | data[2]
        if len(data) != 8 + length:
            return None

        seq = data[3]
        cmd = CmdType(data[4])
        payload = data[5:5 + length]

        # Verify CRC
        rx_crc = (data[-3] << 8) | data[-2]
        calc_crc = crc16(bytes([seq, cmd]) + payload)

        if rx_crc != calc_crc:
            return None

        return cls(seq=seq, cmd=cmd, payload=payload)


# =============================================================================
# FPB Loader Class
# =============================================================================

class FPBLoader:
    """FPB Loader host implementation."""

    def __init__(self, port: str, baudrate: int = 115200, verbose: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.verbose = verbose
        self.serial: Optional[serial.Serial] = None
        self.tx_seq = 0

    def connect(self) -> bool:
        """Connect to the device."""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=TIMEOUT,
                write_timeout=TIMEOUT
            )
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            time.sleep(0.1)  # Wait for device to be ready
            self._log(f"Connected to {self.port} @ {self.baudrate}")
            return True
        except serial.SerialException as e:
            print(f"Error: Failed to connect: {e}")
            return False

    def disconnect(self):
        """Disconnect from the device."""
        if self.serial:
            self.serial.close()
            self.serial = None
            self._log("Disconnected")

    def _log(self, msg: str):
        """Print verbose log message."""
        if self.verbose:
            print(f"[FPB] {msg}")

    def _send_frame(self, cmd: CmdType, payload: bytes = b'') -> Optional[Frame]:
        """Send a frame and wait for response."""
        if not self.serial:
            return None

        frame = Frame(seq=self.tx_seq, cmd=cmd, payload=payload)
        self.tx_seq = (self.tx_seq + 1) & 0xFF

        for attempt in range(MAX_RETRIES):
            self._log(f"TX: cmd={cmd.name}, len={len(payload)}, seq={frame.seq}")

            # Send frame
            self.serial.write(frame.encode())
            self.serial.flush()

            # Wait for response
            response = self._receive_frame()
            if response:
                return response

            self._log(f"Retry {attempt + 1}/{MAX_RETRIES}")

        return None

    def _receive_frame(self) -> Optional[Frame]:
        """Receive a frame with timeout."""
        if not self.serial:
            return None

        buffer = bytearray()
        start_time = time.time()

        while time.time() - start_time < TIMEOUT:
            if self.serial.in_waiting > 0:
                buffer.extend(self.serial.read(self.serial.in_waiting))

            # Try to find a valid frame
            sof_idx = buffer.find(bytes([SOF]))
            if sof_idx == -1:
                buffer.clear()
                continue

            if sof_idx > 0:
                buffer = buffer[sof_idx:]

            # Check if we have enough data for header
            if len(buffer) < 5:
                continue

            length = (buffer[1] << 8) | buffer[2]
            frame_len = 8 + length

            if len(buffer) < frame_len:
                continue

            # Try to decode frame
            frame_data = bytes(buffer[:frame_len])
            frame = Frame.decode(frame_data)

            if frame:
                self._log(f"RX: cmd={frame.cmd.name}, len={len(frame.payload)}")

                # Handle log messages
                if frame.cmd == CmdType.LOG:
                    print(f"[MCU] {frame.payload.decode('utf-8', errors='replace')}")
                    buffer = buffer[frame_len:]
                    continue

                # Handle error responses
                if frame.cmd == CmdType.ERROR:
                    err_code = frame.payload[0] if frame.payload else 0
                    err_msg = frame.payload[1:].decode('utf-8', errors='replace')
                    print(f"[ERROR] Code {err_code}: {err_msg}")
                    return None

                return frame

            # Invalid frame, skip SOF and try again
            buffer = buffer[1:]

            time.sleep(0.01)

        return None

    # -------------------------------------------------------------------------
    # High-level Commands
    # -------------------------------------------------------------------------

    def ping(self) -> bool:
        """Send ping and check response."""
        response = self._send_frame(CmdType.PING)
        if response and response.cmd == CmdType.ACK:
            print(f"PONG: {response.payload.decode('utf-8', errors='replace')}")
            return True
        print("Ping failed")
        return False

    def get_info(self) -> Optional[str]:
        """Get device information."""
        response = self._send_frame(CmdType.INFO)
        if response and response.cmd == CmdType.INFO:
            info = response.payload.decode('utf-8', errors='replace')
            print(info)
            return info
        return None

    def upload(self, data: bytes, progress: bool = True) -> bool:
        """Upload binary data to RAM code buffer."""
        total = len(data)
        offset = 0

        while offset < total:
            chunk = data[offset:offset + CHUNK_SIZE]

            # Build payload: offset (4 bytes) + data
            payload = struct.pack('>I', offset) + chunk

            response = self._send_frame(CmdType.UPLOAD, payload)
            if not response or response.cmd != CmdType.ACK:
                print(f"\nUpload failed at offset {offset}")
                return False

            # Verify received offset
            rx_offset = struct.unpack('>I', response.payload)[0]
            if rx_offset != offset + len(chunk):
                print(f"\nOffset mismatch: expected {offset + len(chunk)}, got {rx_offset}")
                return False

            offset += len(chunk)

            if progress:
                pct = offset * 100 // total
                print(f"\rUploading: {offset}/{total} bytes ({pct}%)", end='', flush=True)

        # Send upload end
        response = self._send_frame(CmdType.UPLOAD_END)
        if response and response.cmd == CmdType.ACK:
            if progress:
                print(f"\nUpload complete: {total} bytes")
            return True

        print("\nUpload end failed")
        return False

    def execute(self, entry_offset: int = 0, args: str = "") -> Optional[int]:
        """Execute uploaded RAM code."""
        payload = struct.pack('>I', entry_offset)
        if args:
            payload += args.encode('utf-8')

        response = self._send_frame(CmdType.EXEC, payload)
        if response and response.cmd == CmdType.ACK:
            result = struct.unpack('>i', response.payload)[0]
            print(f"Execution result: {result}")
            return result
        return None

    def call(self, address: int, args: str = "") -> Optional[int]:
        """Call function at address."""
        payload = struct.pack('>I', address)
        if args:
            payload += args.encode('utf-8')

        response = self._send_frame(CmdType.CALL, payload)
        if response and response.cmd == CmdType.ACK:
            result = struct.unpack('>i', response.payload)[0]
            print(f"Call result: {result}")
            return result
        return None

    def read_memory(self, address: int, length: int) -> Optional[bytes]:
        """Read memory from device."""
        payload = struct.pack('>II', address, length)
        response = self._send_frame(CmdType.READ, payload)
        if response and response.cmd == CmdType.READ:
            return response.payload
        return None

    def write_memory(self, address: int, data: bytes) -> bool:
        """Write memory to device."""
        payload = struct.pack('>I', address) + data
        response = self._send_frame(CmdType.WRITE, payload)
        return response is not None and response.cmd == CmdType.ACK

    def set_patch(self, comp: int, orig_addr: int, patch_addr: int) -> bool:
        """Set FPB patch."""
        payload = bytes([comp]) + struct.pack('>II', orig_addr, patch_addr)
        response = self._send_frame(CmdType.PATCH, payload)
        return response is not None and response.cmd == CmdType.ACK

    def clear_patch(self, comp: int) -> bool:
        """Clear FPB patch."""
        payload = bytes([comp])
        response = self._send_frame(CmdType.UNPATCH, payload)
        return response is not None and response.cmd == CmdType.ACK


# =============================================================================
# ELF Symbol Extraction
# =============================================================================

def extract_symbols(elf_path: str) -> dict:
    """Extract symbols from ELF file using arm-none-eabi-nm."""
    symbols = {}

    try:
        result = subprocess.run(
            ['arm-none-eabi-nm', '-C', elf_path],
            capture_output=True,
            text=True,
            check=True
        )

        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                addr = int(parts[0], 16)
                sym_type = parts[1]
                name = parts[2]
                symbols[name] = {'address': addr, 'type': sym_type}

    except subprocess.CalledProcessError as e:
        print(f"Error extracting symbols: {e}")
    except FileNotFoundError:
        print("Error: arm-none-eabi-nm not found")

    return symbols


def compile_patch(source_path: str, output_path: str, base_addr: int = 0x20001000,
                  includes: List[str] = None) -> bool:
    """Compile patch source file to binary."""
    includes = includes or []

    with tempfile.NamedTemporaryFile(suffix='.elf', delete=False) as elf_file:
        elf_path = elf_file.name

    try:
        # Compile to ELF
        cmd = [
            'arm-none-eabi-gcc',
            '-mcpu=cortex-m3',
            '-mthumb',
            '-Os',
            '-ffunction-sections',
            '-fdata-sections',
            '-nostartfiles',
            '-nostdlib',
            f'-Wl,--section-start=.text={base_addr:#x}',
            '-Wl,--gc-sections',
        ]

        for inc in includes:
            cmd.extend(['-I', inc])

        cmd.extend(['-o', elf_path, source_path])

        subprocess.run(cmd, check=True, capture_output=True)

        # Extract .text section to binary
        subprocess.run([
            'arm-none-eabi-objcopy',
            '-O', 'binary',
            '-j', '.text',
            elf_path,
            output_path
        ], check=True, capture_output=True)

        print(f"Compiled: {source_path} -> {output_path}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Compilation failed: {e.stderr.decode() if e.stderr else str(e)}")
        return False

    finally:
        if os.path.exists(elf_path):
            os.unlink(elf_path)


# =============================================================================
# Interactive Mode
# =============================================================================

def interactive_mode(loader: FPBLoader):
    """Run interactive command mode."""
    print("\nFPB Loader Interactive Mode")
    print("Commands: ping, info, upload <file>, exec [offset] [args], call <addr> [args],")
    print("          read <addr> <len>, write <addr> <hex>, patch <comp> <orig> <patch>,")
    print("          unpatch <comp>, symbols <elf>, compile <src> <out>, quit")
    print()

    while True:
        try:
            line = input("fpb> ").strip()
            if not line:
                continue

            parts = line.split()
            cmd = parts[0].lower()

            if cmd == 'quit' or cmd == 'exit':
                break

            elif cmd == 'ping':
                loader.ping()

            elif cmd == 'info':
                loader.get_info()

            elif cmd == 'upload':
                if len(parts) < 2:
                    print("Usage: upload <file>")
                    continue
                with open(parts[1], 'rb') as f:
                    loader.upload(f.read())

            elif cmd == 'exec':
                offset = int(parts[1], 0) if len(parts) > 1 else 0
                args = ' '.join(parts[2:]) if len(parts) > 2 else ''
                loader.execute(offset, args)

            elif cmd == 'call':
                if len(parts) < 2:
                    print("Usage: call <addr> [args]")
                    continue
                addr = int(parts[1], 0)
                args = ' '.join(parts[2:]) if len(parts) > 2 else ''
                loader.call(addr, args)

            elif cmd == 'read':
                if len(parts) < 3:
                    print("Usage: read <addr> <len>")
                    continue
                addr = int(parts[1], 0)
                length = int(parts[2], 0)
                data = loader.read_memory(addr, length)
                if data:
                    # Print hex dump
                    for i in range(0, len(data), 16):
                        hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
                        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
                        print(f'{addr+i:08X}  {hex_str:<48}  {ascii_str}')

            elif cmd == 'write':
                if len(parts) < 3:
                    print("Usage: write <addr> <hex>")
                    continue
                addr = int(parts[1], 0)
                data = bytes.fromhex(parts[2])
                if loader.write_memory(addr, data):
                    print("Write OK")

            elif cmd == 'patch':
                if len(parts) < 4:
                    print("Usage: patch <comp> <orig_addr> <patch_addr>")
                    continue
                comp = int(parts[1], 0)
                orig = int(parts[2], 0)
                patch = int(parts[3], 0)
                if loader.set_patch(comp, orig, patch):
                    print("Patch OK")

            elif cmd == 'unpatch':
                if len(parts) < 2:
                    print("Usage: unpatch <comp>")
                    continue
                comp = int(parts[1], 0)
                if loader.clear_patch(comp):
                    print("Unpatch OK")

            elif cmd == 'symbols':
                if len(parts) < 2:
                    print("Usage: symbols <elf>")
                    continue
                symbols = extract_symbols(parts[1])
                for name, info in sorted(symbols.items(), key=lambda x: x[1]['address']):
                    print(f"{info['address']:08X} {info['type']} {name}")

            elif cmd == 'compile':
                if len(parts) < 3:
                    print("Usage: compile <source.c> <output.bin>")
                    continue
                compile_patch(parts[1], parts[2])

            else:
                print(f"Unknown command: {cmd}")

        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"Error: {e}")


# =============================================================================
# Main Entry Point
# =============================================================================

def list_ports():
    """List available serial ports."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found")
        return

    print("Available serial ports:")
    for p in ports:
        print(f"  {p.device}: {p.description}")


def main():
    parser = argparse.ArgumentParser(
        description='FPB Loader - Runtime code injection tool for STM32',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s --list                     List serial ports
  %(prog)s -p /dev/ttyUSB0 --ping     Test connection
  %(prog)s -p /dev/ttyUSB0 --info     Get device info
  %(prog)s -p /dev/ttyUSB0 -u patch.bin --exec
                                      Upload and execute binary
  %(prog)s -p /dev/ttyUSB0 --compile patch.c -u --exec
                                      Compile, upload and execute
  %(prog)s -p /dev/ttyUSB0 -i         Interactive mode
'''
    )

    parser.add_argument('-p', '--port', help='Serial port')
    parser.add_argument('-b', '--baudrate', type=int, default=115200, help='Baud rate')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    parser.add_argument('--list', action='store_true', help='List serial ports')
    parser.add_argument('--ping', action='store_true', help='Ping device')
    parser.add_argument('--info', action='store_true', help='Get device info')

    parser.add_argument('-u', '--upload', metavar='FILE', help='Upload binary file')
    parser.add_argument('--exec', action='store_true', help='Execute after upload')
    parser.add_argument('--entry', type=lambda x: int(x, 0), default=0, help='Entry offset')
    parser.add_argument('--args', default='', help='Arguments for execution')

    parser.add_argument('--compile', metavar='FILE', help='Compile C source')
    parser.add_argument('-I', '--include', action='append', default=[], help='Include path')
    parser.add_argument('--base', type=lambda x: int(x, 0), default=0x20001000,
                        help='Base address for compilation')

    parser.add_argument('--symbols', metavar='ELF', help='Extract symbols from ELF')

    parser.add_argument('-i', '--interactive', action='store_true', help='Interactive mode')

    args = parser.parse_args()

    # List ports
    if args.list:
        list_ports()
        return 0

    # Extract symbols (no connection needed)
    if args.symbols:
        symbols = extract_symbols(args.symbols)
        for name, info in sorted(symbols.items(), key=lambda x: x[1]['address']):
            print(f"{info['address']:08X} {info['type']} {name}")
        return 0

    # Check port
    if not args.port:
        parser.print_help()
        return 1

    # Compile if requested
    upload_file = args.upload
    if args.compile:
        if not upload_file:
            upload_file = args.compile.replace('.c', '.bin')
        if not compile_patch(args.compile, upload_file, args.base, args.include):
            return 1

    # Connect to device
    loader = FPBLoader(args.port, args.baudrate, args.verbose)
    if not loader.connect():
        return 1

    try:
        # Ping
        if args.ping:
            loader.ping()

        # Info
        if args.info:
            loader.get_info()

        # Upload
        if upload_file:
            with open(upload_file, 'rb') as f:
                data = f.read()
            if not loader.upload(data):
                return 1

            # Execute
            if args.exec:
                loader.execute(args.entry, args.args)

        # Interactive mode
        if args.interactive:
            interactive_mode(loader)

    finally:
        loader.disconnect()

    return 0


if __name__ == '__main__':
    sys.exit(main())
