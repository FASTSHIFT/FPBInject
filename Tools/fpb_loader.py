#!/usr/bin/env python3

"""
MIT License

Copyright (c) 2026 VIFEX

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""
FPB Loader - Host tool for FPBInject runtime code injection

Works with func_loader text-based command protocol.

Usage:
    fpb_loader.py --port /dev/ttyUSB0 --ping
    fpb_loader.py --port /dev/ttyUSB0 --inject inject.c --target digitalWrite
    fpb_loader.py --port /dev/ttyUSB0 --interactive
"""

import argparse
import base64
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)

# =============================================================================
# CRC-16-CCITT
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
# FPB Loader Class
# =============================================================================

class FPBLoader:
    """FPB Loader - text protocol communication."""

    def __init__(self, port: str, baudrate: int = 115200, verbose: bool = False, chunk_size: int = 128):
        self.port = port
        self.baudrate = baudrate
        self.verbose = verbose
        self.chunk_size = chunk_size  # Max hex chars per upload command (128 hex = 64 bytes)
        self.ser: Optional[serial.Serial] = None

    def connect(self) -> bool:
        """Connect to device."""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=2.0,
                write_timeout=2.0
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.1)
            self._log(f"Connected to {self.port} @ {self.baudrate}")
            return True
        except serial.SerialException as e:
            print(f"Error: {e}")
            return False

    def disconnect(self):
        """Disconnect from device."""
        if self.ser:
            self.ser.close()
            self.ser = None

    def _log(self, msg: str):
        """Verbose log."""
        if self.verbose:
            print(f"[FPB] {msg}")

    def _send_cmd(self, cmd: str, timeout: float = 2.0) -> str:
        """Send command and get response."""
        if not self.ser:
            return ""

        # Always send as: fl --cmd ...
        full_cmd = f"fl {cmd}" if not cmd.strip().startswith("fl ") else cmd
        self._log(f"TX: {full_cmd}")

        # Clear buffer
        self.ser.reset_input_buffer()

        # Send command
        self.ser.write((full_cmd + "\n").encode())
        self.ser.flush()

        # Read response - return early when we see [OK] or [ERR]
        response = ""
        start = time.time()
        while time.time() - start < timeout:
            if self.ser.in_waiting:
                chunk = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='replace')
                response += chunk
                # Check if response is complete (contains status marker)
                if '[OK]' in response or '[ERR]' in response:
                    # Give a tiny bit more time for any trailing data
                    time.sleep(0.005)
                    if self.ser.in_waiting:
                        response += self.ser.read(self.ser.in_waiting).decode('utf-8', errors='replace')
                    break
            time.sleep(0.002)  # Reduced from 0.01 for faster polling

        self._log(f"RX: {response.strip()}")
        return response.strip()

    def _parse_response(self, resp: str) -> dict:
        """Parse response - format: [OK] msg or [ERR] msg"""
        resp = resp.strip()

        # Handle multi-line response - find the last status line
        lines = resp.split('\n')
        for line in reversed(lines):
            line = line.strip()
            if line.startswith('[OK]'):
                msg = line[4:].strip()
                return {"ok": True, "msg": msg, "raw": resp}
            elif line.startswith('[ERR]'):
                msg = line[5:].strip()
                return {"ok": False, "msg": msg, "raw": resp}

        return {"ok": False, "msg": resp, "raw": resp}

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    def ping(self) -> bool:
        """Ping device."""
        resp = self._send_cmd("--cmd ping")
        result = self._parse_response(resp)
        print(f"Ping: {result}")
        return result.get("ok", False)

    def info(self) -> Optional[dict]:
        """Get device info."""
        resp = self._send_cmd("--cmd info")
        result = self._parse_response(resp)

        # Parse additional info from response
        if result.get("ok"):
            raw = result.get("raw", "")
            for line in raw.split('\n'):
                line = line.strip()
                if line.startswith("Base:"):
                    try:
                        result["base"] = int(line.split(":")[1].strip(), 0)
                    except:
                        pass
                elif line.startswith("Size:"):
                    try:
                        result["size"] = int(line.split(":")[1].strip())
                    except:
                        pass
                elif line.startswith("Used:"):
                    try:
                        result["used"] = int(line.split(":")[1].strip())
                    except:
                        pass

        print(f"Info: {result}")
        return result

    def alloc(self, size: int) -> Optional[int]:
        """Allocate memory buffer."""
        resp = self._send_cmd(f"--cmd alloc --size {size}")
        result = self._parse_response(resp)
        if result.get("ok"):
            # Parse allocated address from response message
            # Format: "Allocated <size> at 0x<addr>"
            msg = result.get("msg", "")
            import re
            match = re.search(r'0x([0-9A-Fa-f]+)', msg)
            if match:
                base = int(match.group(1), 16)
                print(f"Allocated {size} bytes at 0x{base:08X}")
                return base
        print(f"Alloc failed: {result}")
        return None

    def free(self) -> bool:
        """Free memory buffer."""
        resp = self._send_cmd("--cmd free")
        result = self._parse_response(resp)
        return result.get("ok", False)

    def clear(self) -> bool:
        """Clear upload buffer."""
        resp = self._send_cmd("--cmd clear")
        result = self._parse_response(resp)
        return result.get("ok", False)

    def upload(self, data: bytes, progress: bool = True, start_offset: int = 0) -> Tuple[bool, dict]:
        """Upload binary data in chunks using base64 encoding.
        
        Args:
            data: Binary data to upload
            progress: Show progress bar
            start_offset: Starting offset in device buffer (for alignment)
            
        Returns:
            Tuple of (success, stats_dict)
        """
        total = len(data)
        data_offset = 0
        # Base64 encoding: 3 bytes -> 4 chars, so we use 48 bytes per chunk (64 chars base64)
        # This keeps command line reasonable length
        bytes_per_chunk = 48
        
        upload_start = time.time()
        chunk_count = 0
        total_chunks = (total + bytes_per_chunk - 1) // bytes_per_chunk

        while data_offset < total:
            chunk_start = time.time()
            chunk = data[data_offset:data_offset + bytes_per_chunk]
            b64_data = base64.b64encode(chunk).decode('ascii')
            crc = crc16(chunk)

            # Device offset = start_offset + data_offset
            device_offset = start_offset + data_offset
            # Use hex format for addr and crc
            cmd = f"--cmd upload --addr 0x{device_offset:X} --data {b64_data} --crc 0x{crc:04X}"
            resp = self._send_cmd(cmd)
            result = self._parse_response(resp)

            if not result.get("ok"):
                print(f"\nUpload failed at offset 0x{device_offset:X}: {result}")
                return False, {}

            data_offset += len(chunk)
            chunk_count += 1
            
            if progress:
                elapsed = time.time() - upload_start
                pct = data_offset * 100 // total
                # Calculate speed and ETA
                if elapsed > 0:
                    speed = data_offset / elapsed
                    remaining = total - data_offset
                    eta = remaining / speed if speed > 0 else 0
                    print(f"\rUploading: {data_offset}/{total} bytes ({pct}%) "
                          f"[{speed:.0f} B/s, ETA: {eta:.1f}s]", end='', flush=True)
                else:
                    print(f"\rUploading: {data_offset}/{total} bytes ({pct}%)", end='', flush=True)

        upload_time = time.time() - upload_start
        speed = total / upload_time if upload_time > 0 else 0
        
        stats = {
            "bytes": total,
            "chunks": chunk_count,
            "time": upload_time,
            "speed": speed
        }
        
        if progress:
            print(f"\nUpload complete: {total} bytes in {upload_time:.2f}s ({speed:.0f} B/s)")
        return True, stats

    def execute(self, entry: int = 0, args: str = "") -> Optional[int]:
        """Execute uploaded code."""
        cmd = f"--cmd exec --entry {entry}"
        if args:
            cmd += f' --args "{args}"'
        resp = self._send_cmd(cmd)
        result = self._parse_response(resp)
        if result.get("ok"):
            ret = result.get("ret", 0)
            print(f"Execution result: {ret}")
            return ret
        print(f"Exec failed: {result}")
        return None

    def call(self, addr: int, args: str = "") -> Optional[int]:
        """Call function at address."""
        cmd = f"--cmd call --addr 0x{addr:X}"
        if args:
            cmd += f' --args "{args}"'
        resp = self._send_cmd(cmd)
        result = self._parse_response(resp)
        if result.get("ok"):
            ret = result.get("ret", 0)
            print(f"Call result: {ret}")
            return ret
        print(f"Call failed: {result}")
        return None

    def read(self, addr: int, length: int) -> Optional[bytes]:
        """Read memory."""
        cmd = f"--cmd read --addr 0x{addr:X} --len {length}"
        resp = self._send_cmd(cmd)
        result = self._parse_response(resp)
        if result.get("ok"):
            hex_data = result.get("data", "")
            return bytes.fromhex(hex_data)
        return None

    def write(self, addr: int, data: bytes) -> bool:
        """Write memory."""
        hex_data = data.hex().upper()
        crc = crc16(data)
        cmd = f"--cmd write --addr 0x{addr:X} --data {hex_data} --crc 0x{crc:04X}"
        resp = self._send_cmd(cmd)
        result = self._parse_response(resp)
        return result.get("ok", False)

    def patch(self, comp: int, orig: int, target: int) -> bool:
        """Set FPB patch."""
        cmd = f"--cmd patch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
        resp = self._send_cmd(cmd)
        result = self._parse_response(resp)
        if result.get("ok"):
            print(f"Patch set: comp={comp}, 0x{orig:08X} -> 0x{target:08X}")
            return True
        print(f"Patch failed: {result}")
        return False

    def tpatch(self, comp: int, orig: int, target: int) -> bool:
        """Set trampoline patch (uses FPB + RAM trampoline, no Flash modification)."""
        cmd = f"--cmd tpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
        resp = self._send_cmd(cmd)
        result = self._parse_response(resp)
        if result.get("ok"):
            print(f"Trampoline patch: comp={comp}, 0x{orig:08X} -> 0x{target:08X}")
            return True
        print(f"Trampoline patch failed: {result}")
        return False

    def dpatch(self, comp: int, orig: int, target: int) -> bool:
        """Set DebugMonitor patch (uses FPB breakpoint + DebugMonitor exception, for ARMv8-M)."""
        cmd = f"--cmd dpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
        resp = self._send_cmd(cmd)
        result = self._parse_response(resp)
        if result.get("ok"):
            print(f"DebugMonitor patch: comp={comp}, 0x{orig:08X} -> 0x{target:08X}")
            return True
        print(f"DebugMonitor patch failed: {result}")
        return False

    def unpatch(self, comp: int) -> bool:
        """Clear FPB patch."""
        cmd = f"--cmd unpatch --comp {comp}"
        resp = self._send_cmd(cmd)
        result = self._parse_response(resp)
        return result.get("ok", False)


# =============================================================================
# ELF Utilities
# =============================================================================

# Global toolchain path (set by --toolchain argument)
_toolchain_path: Optional[str] = None


def get_tool_path(tool_name: str) -> str:
    """Get full path for a toolchain tool."""
    if _toolchain_path:
        full_path = os.path.join(_toolchain_path, tool_name)
        if os.path.exists(full_path):
            return full_path
    return tool_name


def get_symbols(elf_path: str) -> Dict[str, int]:
    """Extract symbols from ELF file."""
    symbols = {}
    try:
        nm_tool = get_tool_path('arm-none-eabi-nm')
        result = subprocess.run(
            [nm_tool, '-C', elf_path],
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                addr = int(parts[0], 16)
                name = parts[2]
                symbols[name] = addr
    except Exception as e:
        print(f"Error reading symbols: {e}")
    return symbols


def load_inject_config(config_path: str = None) -> Optional[Dict]:
    """
    Load inject compile configuration from JSON file.
    Search order:
      1. Explicit config_path
      2. build/inject_config.json (relative to script)
      3. ../build/inject_config.json (relative to script)
    """
    import json

    search_paths = []
    if config_path:
        search_paths.append(Path(config_path))

    script_dir = Path(__file__).parent.absolute()
    search_paths.extend([
        script_dir.parent / 'build' / 'inject_config.json',
        script_dir / 'build' / 'inject_config.json',
    ])

    for p in search_paths:
        if p.exists():
            try:
                with open(p, 'r') as f:
                    config = json.load(f)
                    config['_path'] = str(p)
                    return config
            except Exception as e:
                print(f"Error loading config {p}: {e}")

    return None


def parse_compile_commands(compile_commands_path: str, source_filter: str = None,
                          verbose: bool = False) -> Optional[Dict]:
    """
    Parse compile_commands.json to extract compiler flags.
    This reuses the NuttX build system's includes and defines.

    Args:
        compile_commands_path: Path to compile_commands.json
        source_filter: Optional substring to filter source file (e.g., '.c' or specific file name)
        verbose: Print debug info

    Returns:
        Config dict compatible with inject_config.json format
    """
    import json
    import shlex

    if not os.path.exists(compile_commands_path):
        print(f"Error: compile_commands.json not found: {compile_commands_path}")
        return None

    try:
        with open(compile_commands_path, 'r') as f:
            commands = json.load(f)
    except Exception as e:
        print(f"Error loading compile_commands.json: {e}")
        return None

    if not commands:
        print("Error: compile_commands.json is empty")
        return None

    # Find a suitable entry (prefer .c files, not .S assembly)
    selected_entry = None
    for entry in commands:
        file_path = entry.get('file', '')
        if source_filter:
            if source_filter in file_path:
                selected_entry = entry
                break
        elif file_path.endswith('.c') and '__ASSEMBLY__' not in entry.get('command', ''):
            selected_entry = entry
            break

    if not selected_entry:
        for entry in commands:
            if entry.get('file', '').endswith('.c'):
                selected_entry = entry
                break

    if not selected_entry:
        print("Error: No suitable C file entry found in compile_commands.json")
        return None

    if verbose:
        print(f"Using compile entry for: {selected_entry.get('file')}")

    command_str = selected_entry.get('command', '')
    if not command_str:
        print("Error: No command found in entry")
        return None

    try:
        tokens = shlex.split(command_str)
    except Exception as e:
        print(f"Error parsing command: {e}")
        return None

    compiler = tokens[0] if tokens else 'arm-none-eabi-gcc'
    includes = []
    defines = []
    cflags = []

    i = 1
    while i < len(tokens):
        token = tokens[i]

        if token == '-I' and i + 1 < len(tokens):
            includes.append(tokens[i + 1])
            i += 2
            continue
        elif token.startswith('-I'):
            includes.append(token[2:])
            i += 1
            continue

        if token == '-isystem' and i + 1 < len(tokens):
            includes.append(tokens[i + 1])
            i += 2
            continue

        if token == '-D' and i + 1 < len(tokens):
            defines.append(tokens[i + 1])
            i += 2
            continue
        elif token.startswith('-D'):
            defines.append(token[2:])
            i += 1
            continue

        if token == '-o' and i + 1 < len(tokens):
            i += 2
            continue

        if token.endswith(('.c', '.cpp', '.S', '.s', '.o')):
            i += 1
            continue

        if token == '--param' and i + 1 < len(tokens):
            i += 2
            continue

        if token.startswith('-Wa,'):
            i += 1
            continue

        # Keep architecture flags
        if any(token.startswith(p) for p in ['-mthumb', '-mcpu', '-mtune', '-march', '-mfpu', '-mfloat-abi']):
            cflags.append(token)
        elif token in ['-ffunction-sections', '-fdata-sections', '-fno-common', '-nostdlib']:
            cflags.append(token)

        i += 1

    # Add size optimization for inject code
    if '-Os' not in cflags:
        cflags.append('-Os')

    includes = list(dict.fromkeys(includes))
    defines = list(dict.fromkeys(defines))
    cflags = list(dict.fromkeys(cflags))

    # Only replace the filename part, not the full path
    compiler_dir = os.path.dirname(compiler)
    compiler_name = os.path.basename(compiler)
    objcopy_name = compiler_name.replace('gcc', 'objcopy').replace('g++', 'objcopy')
    objcopy = os.path.join(compiler_dir, objcopy_name) if compiler_dir else objcopy_name

    config = {
        'compiler': compiler,
        'objcopy': objcopy,
        'includes': includes,
        'defines': defines,
        'cflags': cflags,
        'ldflags': [],
        '_path': compile_commands_path,
        '_source': 'compile_commands.json'
    }

    if verbose:
        print(f"Extracted from compile_commands.json:")
        print(f"  Compiler: {compiler}")
        print(f"  Includes: {len(includes)} paths")
        print(f"  Defines:  {len(defines)}")
        print(f"  CFlags:   {cflags}")

    return config


def compile_inject(source: str, base_addr: int, elf_path: str = None,
                   config_path: str = None, compile_commands_path: str = None,
                   verbose: bool = False) -> Optional[Tuple[bytes, Dict[str, int]]]:
    """
    Compile injection code to binary.
    Uses inject_config.json or compile_commands.json for toolchain settings.
    Returns (binary_data, symbols) or None on failure.

    Args:
        source: Path to injection source file (.c/.cpp)
        base_addr: Base address for injection code
        elf_path: Path to main ELF for symbol resolution
        config_path: Path to inject_config.json
        compile_commands_path: Path to compile_commands.json (alternative to config_path)
        verbose: Enable verbose output
    """
    # Load config - prefer compile_commands if specified
    config = None
    if compile_commands_path:
        config = parse_compile_commands(compile_commands_path, verbose=verbose)
        if config and verbose:
            print(f"Using compile_commands: {compile_commands_path}")

    if not config:
        config = load_inject_config(config_path)

    if not config:
        print("Error: No config found.")
        print("       Options:")
        print("       1. Use --config to specify inject_config.json")
        print("       2. Use --compile-commands to specify compile_commands.json")
        print("       3. Run cmake -B build -G Ninja && cmake --build build")
        return None

    if verbose:
        print(f"Using config: {config.get('_path', 'unknown')}")

    # Get compiler/objcopy from config
    compiler = config.get('compiler', 'arm-none-eabi-gcc')
    objcopy = config.get('objcopy', 'arm-none-eabi-objcopy')

    # If compile_commands provided full paths, use them directly
    # Otherwise, apply toolchain path
    if not os.path.isabs(compiler):
        compiler = get_tool_path(compiler)
    if not os.path.isabs(objcopy):
        objcopy = get_tool_path(objcopy)

    if verbose and _toolchain_path:
        print(f"Using toolchain: {_toolchain_path}")

    includes = config.get('includes', [])
    defines = config.get('defines', [])
    cflags = config.get('cflags', [])
    ldflags = config.get('ldflags', [])

    # Use main_elf from config if not specified
    if not elf_path:
        elf_path = config.get('main_elf')

    with tempfile.TemporaryDirectory() as tmpdir:
        obj_file = os.path.join(tmpdir, 'inject.o')
        elf_file = os.path.join(tmpdir, 'inject.elf')
        bin_file = os.path.join(tmpdir, 'inject.bin')

        # Compile to object
        cmd = [compiler] + cflags + ['-c']

        for inc in includes:
            if os.path.isdir(inc):
                cmd.extend(['-I', inc])

        for d in defines:
            cmd.extend(['-D', d])

        cmd.extend(['-o', obj_file, source])

        if verbose:
            print(f"Compile: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Compile error:\n{result.stderr}")
            return None

        # Create linker script with KEEP to prevent gc-sections from removing inject functions
        ld_content = f"""
ENTRY(inject_entry)
SECTIONS
{{
    . = 0x{base_addr:08X};
    .text : {{
        KEEP(*(.text.inject*))
        *(.text .text.*)
    }}
    .rodata : {{ *(.rodata .rodata.*) }}
    .data : {{ *(.data .data.*) }}
    .bss : {{ *(.bss .bss.* COMMON) }}
}}
"""
        ld_file = os.path.join(tmpdir, 'inject.ld')
        with open(ld_file, 'w') as f:
            f.write(ld_content)

        # Link - remove --gc-sections to keep all symbols for injection
        link_cmd = [compiler] + cflags[:2] + ['-nostartfiles', '-nostdlib', f'-T{ld_file}']

        # Use symbols from main ELF
        if elf_path and os.path.exists(elf_path):
            link_cmd.append(f'-Wl,--just-symbols={elf_path}')

        link_cmd.extend(['-o', elf_file, obj_file])

        if verbose:
            print(f"Link: {' '.join(link_cmd)}")

        result = subprocess.run(link_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Link error:\n{result.stderr}")
            return None

        # Extract binary
        subprocess.run([objcopy, '-O', 'binary', elf_file, bin_file], check=True)

        # Read binary
        with open(bin_file, 'rb') as f:
            data = f.read()

        # Get symbols
        nm_cmd = objcopy.replace('objcopy', 'nm')
        result = subprocess.run([nm_cmd, '-C', elf_file], capture_output=True, text=True)

        symbols = {}
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3:
                addr = int(parts[0], 16)
                name = parts[2]
                symbols[name] = addr

        print(f"Compiled {len(data)} bytes @ 0x{base_addr:08X}")
        if verbose and symbols:
            print("Symbols:")
            for name, addr in symbols.items():
                print(f"  0x{addr:08X}  {name}")

        return data, symbols


# =============================================================================
# Interactive Mode
# =============================================================================

def nuttx_interactive_mode(loader: FPBLoader):
    """
    NuttX device interactive mode.
    
    Connects to the device's 'fl' command interactive shell and provides
    a pass-through terminal experience. First sends 'fl' to enter device's
    interactive mode (showing 'fl> ' prompt), then passes through user input.
    
    This mode:
    1. Sends 'fl' command to enter device interactive mode
    2. Sends user input directly to device
    3. Reads and displays device output
    4. Handles 'quit'/'exit'/'q' to exit both device and host
    """
    import select
    import threading
    
    print("\nNuttX FPBInject Interactive Mode")
    print("Entering device 'fl' interactive mode...")
    print("Type commands to send to device. 'quit'/'exit'/'q' to exit.")
    print("Ctrl+C to force exit.\n")
    
    ser = loader.ser
    if not ser:
        print("Error: Not connected to device")
        return
    
    # Clear any pending data
    ser.reset_input_buffer()
    
    # Send 'fl' command to enter device interactive mode
    ser.write(b'fl\n')
    time.sleep(0.1)  # Wait for device to enter interactive mode
    
    stop_event = threading.Event()
    
    def reader_thread():
        """Background thread to read and display device output."""
        buffer = ""
        while not stop_event.is_set():
            try:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    if data:
                        text = data.decode('utf-8', errors='replace')
                        # Print output, handling prompt specially
                        print(text, end='', flush=True)
                else:
                    time.sleep(0.01)
            except Exception as e:
                if not stop_event.is_set():
                    print(f"\nReader error: {e}")
                break
    
    # Start reader thread
    reader = threading.Thread(target=reader_thread, daemon=True)
    reader.start()
    
    try:
        while True:
            try:
                line = input()
            except EOFError:
                break
            
            # Check for local exit commands
            cmd = line.strip().lower()
            if cmd in ('quit', 'exit', 'q'):
                # Send exit to device first
                ser.write((line + '\n').encode('utf-8'))
                time.sleep(0.1)
                break
            
            # Send command to device
            ser.write((line + '\n').encode('utf-8'))
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        stop_event.set()
        reader.join(timeout=0.5)
        print("\nExited NuttX interactive mode")

def interactive_mode(loader: FPBLoader, elf_path: str = None):
    """Interactive command mode."""
    print("\nFPB Loader Interactive Mode")
    print("Commands: ping, info, upload <file>, exec, call <addr>,")
    print("          read <addr> <len>, write <addr> <hex>,")
    print("          patch <comp> <orig> <target>, unpatch <comp>,")
    print("          inject <source.c> <target_func>, symbols, quit")
    print()

    symbols = {}
    if elf_path and os.path.exists(elf_path):
        symbols = get_symbols(elf_path)
        print(f"Loaded {len(symbols)} symbols from {elf_path}")

    # Get device info for base address
    base_addr = 0x20001000  # Default
    info = loader.info()
    if info and info.get("base"):
        base_addr = info.get("base")

    while True:
        try:
            line = input("fpb> ").strip()
            if not line:
                continue

            parts = line.split()
            cmd = parts[0].lower()

            if cmd in ('quit', 'exit', 'q'):
                break

            elif cmd == 'ping':
                loader.ping()

            elif cmd == 'info':
                loader.info()

            elif cmd == 'alloc':
                size = int(parts[1], 0) if len(parts) > 1 else 1024
                loader.alloc(size)

            elif cmd == 'free':
                loader.free()

            elif cmd == 'clear':
                loader.clear()

            elif cmd == 'upload':
                if len(parts) < 2:
                    print("Usage: upload <file>")
                    continue
                with open(parts[1], 'rb') as f:
                    loader.upload(f.read())

            elif cmd == 'exec':
                entry = int(parts[1], 0) if len(parts) > 1 else 0
                args = ' '.join(parts[2:]) if len(parts) > 2 else ''
                loader.execute(entry, args)

            elif cmd == 'call':
                if len(parts) < 2:
                    print("Usage: call <addr|symbol>")
                    continue
                addr_str = parts[1]
                if addr_str in symbols:
                    addr = symbols[addr_str]
                else:
                    addr = int(addr_str, 0)
                args = ' '.join(parts[2:]) if len(parts) > 2 else ''
                loader.call(addr, args)

            elif cmd == 'read':
                if len(parts) < 3:
                    print("Usage: read <addr> <len>")
                    continue
                addr = int(parts[1], 0)
                length = int(parts[2], 0)
                data = loader.read(addr, length)
                if data:
                    for i in range(0, len(data), 16):
                        hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
                        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
                        print(f'{addr+i:08X}  {hex_str:<48}  {asc}')

            elif cmd == 'write':
                if len(parts) < 3:
                    print("Usage: write <addr> <hex>")
                    continue
                addr = int(parts[1], 0)
                data = bytes.fromhex(parts[2])
                if loader.write(addr, data):
                    print("OK")

            elif cmd == 'patch':
                if len(parts) < 4:
                    print("Usage: patch <comp> <orig_addr|symbol> <target_addr>")
                    continue
                comp = int(parts[1], 0)
                orig_str = parts[2]
                if orig_str in symbols:
                    orig = symbols[orig_str]
                else:
                    orig = int(orig_str, 0)
                target = int(parts[3], 0)
                loader.patch(comp, orig, target)

            elif cmd == 'unpatch':
                if len(parts) < 2:
                    print("Usage: unpatch <comp>")
                    continue
                comp = int(parts[1], 0)
                if loader.unpatch(comp):
                    print("OK")

            elif cmd == 'symbols':
                pattern = parts[1].lower() if len(parts) > 1 else None
                for name, addr in sorted(symbols.items(), key=lambda x: x[1]):
                    if not pattern or pattern in name.lower():
                        print(f"0x{addr:08X}  {name}")

            elif cmd == 'inject':
                if len(parts) < 3:
                    print("Usage: inject <source.c> <target_func>")
                    continue
                source = parts[1]
                target_func = parts[2]

                if target_func not in symbols:
                    print(f"Error: Symbol '{target_func}' not found")
                    continue

                target_addr = symbols[target_func]
                print(f"Target: {target_func} @ 0x{target_addr:08X}")

                # Compile injection code
                result = compile_inject(source, base_addr, elf_path)
                if not result:
                    continue

                data, inject_symbols = result

                # Find inject function
                inject_func = None
                for name, addr in inject_symbols.items():
                    if name.startswith('inject_'):
                        inject_func = (name, addr)
                        break

                if not inject_func:
                    print("Error: No inject_* function found")
                    continue

                print(f"Inject: {inject_func[0]} @ 0x{inject_func[1]:08X}")

                # Clear and upload
                loader.clear()
                success, _ = loader.upload(data)
                if not success:
                    continue

                # Set patch (Thumb address needs +1)
                patch_addr = inject_func[1] | 1
                if loader.patch(0, target_addr, patch_addr):
                    print(f"Injection active!")

            else:
                print(f"Unknown command: {cmd}")

        except KeyboardInterrupt:
            print()
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


# =============================================================================
# Main
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
        description='FPB Loader - Runtime code injection tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s --list                      List serial ports
  %(prog)s -p /dev/ttyUSB0 --ping      Test connection
  %(prog)s -p /dev/ttyUSB0 --info      Get device info
  %(prog)s -p /dev/ttyUSB0 -i          Host-side interactive mode
  %(prog)s -p /dev/ttyUSB0 -ni         NuttX device interactive mode (pass-through)
  %(prog)s -p /dev/ttyUSB0 --inject App/inject/inject.c --target digitalWrite
  %(prog)s -p /dev/ttyUSB0 --inject inject.c --target func --patch-mode debugmon

NuttX example (using compile_commands.json):
  %(prog)s -p /dev/ttyACM0 -b 921600 --inject inject.c --target syslog \\
           --compile-commands out/xxx/compile_commands.json \\
           -e out/xxx/nuttx.elf --patch-mode debugmon -ni
'''
    )

    parser.add_argument('-p', '--port', help='Serial port')
    parser.add_argument('-b', '--baudrate', type=int, default=115200)
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-e', '--elf', default='build/FPBInject.elf',
                        help='Main ELF file for symbols')
    parser.add_argument('-t', '--toolchain', metavar='PATH',
                        help='Custom toolchain directory (e.g., prebuilts/gcc/linux-x86_64/arm-none-eabi/bin)')

    parser.add_argument('--list', action='store_true', help='List serial ports')
    parser.add_argument('--ping', action='store_true')
    parser.add_argument('--info', action='store_true')

    parser.add_argument('-u', '--upload', metavar='FILE', help='Upload binary')
    parser.add_argument('--exec', action='store_true', help='Execute after upload')
    parser.add_argument('--entry', type=lambda x: int(x, 0), default=0)

    parser.add_argument('--inject', metavar='FILE', help='Injection source file')
    parser.add_argument('--target', help='Target function to hijack')
    parser.add_argument('--func', help='Inject function name (default: first inject_* found)')
    parser.add_argument('--comp', type=int, default=0, help='FPB comparator')
    parser.add_argument('--config', help='Path to inject_config.json (default: build/inject_config.json)')
    parser.add_argument('--compile-commands', metavar='PATH',
                        help='Path to compile_commands.json to extract NuttX/project compiler flags')
    parser.add_argument('--chunk-size', type=int, default=128,
                        help='Max hex chars per upload command (default: 128, i.e. 64 bytes)')
    parser.add_argument('--patch-mode', choices=['trampoline', 'debugmon', 'direct'],
                        default='trampoline',
                        help='Patch mode: trampoline (FPB REMAP to Flash trampoline, default), '
                             'debugmon (FPB breakpoint + DebugMonitor, for ARMv8-M), '
                             'direct (FPB REMAP directly, limited)')

    parser.add_argument('-i', '--interactive', action='store_true',
                        help='Host-side interactive mode with local command parsing')
    parser.add_argument('-ni', '--nuttx-interactive', action='store_true',
                        help='NuttX device interactive mode (pass-through to device fl shell)')

    args = parser.parse_args()

    if args.list:
        list_ports()
        return 0

    # Set global toolchain path
    global _toolchain_path
    if args.toolchain:
        toolchain_path = args.toolchain
        if not os.path.isabs(toolchain_path):
            toolchain_path = os.path.abspath(toolchain_path)
        if os.path.isdir(toolchain_path):
            _toolchain_path = toolchain_path
            if args.verbose:
                print(f"Using toolchain: {_toolchain_path}")
        else:
            print(f"Warning: Toolchain directory not found: {toolchain_path}")

    if not args.port:
        parser.print_help()
        return 1

    # Resolve ELF path
    elf_path = args.elf
    if not os.path.isabs(elf_path):
        script_dir = Path(__file__).parent.absolute()
        elf_path = str(script_dir.parent / elf_path)

    loader = FPBLoader(args.port, args.baudrate, args.verbose, args.chunk_size)
    if not loader.connect():
        return 1

    try:
        if args.ping:
            loader.ping()

        if args.info:
            loader.info()

        if args.upload:
            with open(args.upload, 'rb') as f:
                data = f.read()
            success, _ = loader.upload(data)
            if success and args.exec:
                loader.execute(args.entry)

        if args.inject and args.target:
            if not os.path.exists(elf_path):
                print(f"Error: ELF not found: {elf_path}")
                return 1

            symbols = get_symbols(elf_path)

            if args.target not in symbols:
                print(f"Error: Symbol '{args.target}' not found")
                print("Available symbols matching pattern:")
                for name in symbols:
                    if args.target.lower() in name.lower():
                        print(f"  {name}")
                return 1

            target_addr = symbols[args.target]
            print(f"Target: {args.target} @ 0x{target_addr:08X}")

            # Get device info to determine allocation mode
            info = loader.info()
            is_dynamic = info and info.get("base", 0) == 0 and info.get("size", 0) == 0

            total_start_time = time.time()
            compile_time = 0
            upload_stats = {}

            if is_dynamic:
                # Dynamic allocation mode: compile first to get size, then alloc, then recompile
                print("Dynamic allocation mode detected")

                # First pass: compile with dummy address (8-byte aligned) to get size
                compile_start = time.time()
                result = compile_inject(args.inject, 0x20000000, elf_path, args.config,
                                         getattr(args, 'compile_commands', None), args.verbose)
                if not result:
                    return 1
                data, _ = result
                code_size = len(data)

                # Allocate memory on device (request extra for alignment)
                alloc_size = code_size + 8  # Extra space for alignment
                raw_addr = loader.alloc(alloc_size)
                if not raw_addr:
                    print("Error: Failed to allocate memory on device")
                    return 1

                # Calculate alignment offset
                aligned_addr = (raw_addr + 7) & ~7
                align_offset = aligned_addr - raw_addr
                if align_offset:
                    print(f"Alignment: raw=0x{raw_addr:08X}, aligned=0x{aligned_addr:08X}, offset={align_offset}")
                base_addr = aligned_addr

                # Second pass: recompile with aligned address
                result = compile_inject(args.inject, base_addr, elf_path, args.config,
                                         getattr(args, 'compile_commands', None), args.verbose)
                compile_time = time.time() - compile_start
                if not result:
                    return 1
                data, inject_symbols = result
            else:
                # Static allocation mode: use pre-allocated buffer
                base_addr = info.get("base", 0x20001000) if info else 0x20001000
                align_offset = 0  # Static buffer should already be aligned
                compile_start = time.time()
                result = compile_inject(args.inject, base_addr, elf_path, args.config,
                                         getattr(args, 'compile_commands', None), args.verbose)
                compile_time = time.time() - compile_start
                if not result:
                    return 1
                data, inject_symbols = result

            inject_func = None
            if args.func:
                # User specified function name
                for name, addr in inject_symbols.items():
                    if args.func in name:
                        inject_func = (name, addr)
                        break
                if not inject_func:
                    print(f"Error: Function '{args.func}' not found in source")
                    print("Available symbols:")
                    for name, addr in inject_symbols.items():
                        print(f"  0x{addr:08X}  {name}")
                    return 1
            else:
                # Find inject function matching target name, or first inject_*
                target_lower = args.target.lower()
                # First try to match inject_<target>
                for name, addr in inject_symbols.items():
                    name_lower = name.lower()
                    if name_lower.startswith('inject_') and target_lower in name_lower:
                        inject_func = (name, addr)
                        break
                # Fallback: first inject_* by address order
                if not inject_func:
                    inject_funcs = [(n, a) for n, a in inject_symbols.items() if n.startswith('inject_')]
                    if inject_funcs:
                        inject_func = min(inject_funcs, key=lambda x: x[1])

            if not inject_func:
                print("Error: No inject_* function found in source")
                return 1

            print(f"Inject: {inject_func[0]} @ 0x{inject_func[1]:08X}")

            loader.clear()
            # Upload with alignment offset so data starts at aligned address
            success, upload_stats = loader.upload(data, start_offset=align_offset)
            if not success:
                return 1

            patch_addr = inject_func[1] | 1
            
            # Apply patch using selected mode
            patch_mode = args.patch_mode
            if patch_mode == 'trampoline':
                # Use trampoline patching - FPB REMAP -> Flash trampoline -> RAM
                loader.tpatch(args.comp, target_addr, patch_addr)
            elif patch_mode == 'debugmon':
                # Use DebugMonitor patching - FPB breakpoint -> DebugMon exception -> modify PC
                loader.dpatch(args.comp, target_addr, patch_addr)
            else:
                # Direct FPB REMAP (limited, may not work for RAM targets)
                loader.patch(args.comp, target_addr, patch_addr)
            
            # Print statistics
            total_time = time.time() - total_start_time
            print(f"\n--- Injection Statistics ---")
            print(f"Compile time:  {compile_time:.2f}s")
            if upload_stats:
                print(f"Upload time:   {upload_stats.get('time', 0):.2f}s ({upload_stats.get('speed', 0):.0f} B/s)")
                print(f"Upload size:   {upload_stats.get('bytes', 0)} bytes in {upload_stats.get('chunks', 0)} chunks")
            print(f"Total time:    {total_time:.2f}s")
            print(f"Injection active! (mode: {patch_mode})")

        if args.nuttx_interactive:
            nuttx_interactive_mode(loader)
        elif args.interactive:
            interactive_mode(loader, elf_path)

    finally:
        loader.disconnect()

    return 0


if __name__ == '__main__':
    sys.exit(main())
