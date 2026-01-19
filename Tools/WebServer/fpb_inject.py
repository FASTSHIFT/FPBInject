#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
FPB Inject functionality for Web Server.

Provides injection operations based on fpb_loader.py but adapted for web server usage.
"""

import base64
import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import serial
import serial.tools.list_ports

# CRC-16-CCITT Table
CRC16_TABLE = [
    0x0000,
    0x1021,
    0x2042,
    0x3063,
    0x4084,
    0x50A5,
    0x60C6,
    0x70E7,
    0x8108,
    0x9129,
    0xA14A,
    0xB16B,
    0xC18C,
    0xD1AD,
    0xE1CE,
    0xF1EF,
    0x1231,
    0x0210,
    0x3273,
    0x2252,
    0x52B5,
    0x4294,
    0x72F7,
    0x62D6,
    0x9339,
    0x8318,
    0xB37B,
    0xA35A,
    0xD3BD,
    0xC39C,
    0xF3FF,
    0xE3DE,
    0x2462,
    0x3443,
    0x0420,
    0x1401,
    0x64E6,
    0x74C7,
    0x44A4,
    0x5485,
    0xA56A,
    0xB54B,
    0x8528,
    0x9509,
    0xE5EE,
    0xF5CF,
    0xC5AC,
    0xD58D,
    0x3653,
    0x2672,
    0x1611,
    0x0630,
    0x76D7,
    0x66F6,
    0x5695,
    0x46B4,
    0xB75B,
    0xA77A,
    0x9719,
    0x8738,
    0xF7DF,
    0xE7FE,
    0xD79D,
    0xC7BC,
    0x48C4,
    0x58E5,
    0x6886,
    0x78A7,
    0x0840,
    0x1861,
    0x2802,
    0x3823,
    0xC9CC,
    0xD9ED,
    0xE98E,
    0xF9AF,
    0x8948,
    0x9969,
    0xA90A,
    0xB92B,
    0x5AF5,
    0x4AD4,
    0x7AB7,
    0x6A96,
    0x1A71,
    0x0A50,
    0x3A33,
    0x2A12,
    0xDBFD,
    0xCBDC,
    0xFBBF,
    0xEB9E,
    0x9B79,
    0x8B58,
    0xBB3B,
    0xAB1A,
    0x6CA6,
    0x7C87,
    0x4CE4,
    0x5CC5,
    0x2C22,
    0x3C03,
    0x0C60,
    0x1C41,
    0xEDAE,
    0xFD8F,
    0xCDEC,
    0xDDCD,
    0xAD2A,
    0xBD0B,
    0x8D68,
    0x9D49,
    0x7E97,
    0x6EB6,
    0x5ED5,
    0x4EF4,
    0x3E13,
    0x2E32,
    0x1E51,
    0x0E70,
    0xFF9F,
    0xEFBE,
    0xDFDD,
    0xCFFC,
    0xBF1B,
    0xAF3A,
    0x9F59,
    0x8F78,
    0x9188,
    0x81A9,
    0xB1CA,
    0xA1EB,
    0xD10C,
    0xC12D,
    0xF14E,
    0xE16F,
    0x1080,
    0x00A1,
    0x30C2,
    0x20E3,
    0x5004,
    0x4025,
    0x7046,
    0x6067,
    0x83B9,
    0x9398,
    0xA3FB,
    0xB3DA,
    0xC33D,
    0xD31C,
    0xE37F,
    0xF35E,
    0x02B1,
    0x1290,
    0x22F3,
    0x32D2,
    0x4235,
    0x5214,
    0x6277,
    0x7256,
    0xB5EA,
    0xA5CB,
    0x95A8,
    0x8589,
    0xF56E,
    0xE54F,
    0xD52C,
    0xC50D,
    0x34E2,
    0x24C3,
    0x14A0,
    0x0481,
    0x7466,
    0x6447,
    0x5424,
    0x4405,
    0xA7DB,
    0xB7FA,
    0x8799,
    0x97B8,
    0xE75F,
    0xF77E,
    0xC71D,
    0xD73C,
    0x26D3,
    0x36F2,
    0x0691,
    0x16B0,
    0x6657,
    0x7676,
    0x4615,
    0x5634,
    0xD94C,
    0xC96D,
    0xF90E,
    0xE92F,
    0x99C8,
    0x89E9,
    0xB98A,
    0xA9AB,
    0x5844,
    0x4865,
    0x7806,
    0x6827,
    0x18C0,
    0x08E1,
    0x3882,
    0x28A3,
    0xCB7D,
    0xDB5C,
    0xEB3F,
    0xFB1E,
    0x8BF9,
    0x9BD8,
    0xABBB,
    0xBB9A,
    0x4A75,
    0x5A54,
    0x6A37,
    0x7A16,
    0x0AF1,
    0x1AD0,
    0x2AB3,
    0x3A92,
    0xFD2E,
    0xED0F,
    0xDD6C,
    0xCD4D,
    0xBDAA,
    0xAD8B,
    0x9DE8,
    0x8DC9,
    0x7C26,
    0x6C07,
    0x5C64,
    0x4C45,
    0x3CA2,
    0x2C83,
    0x1CE0,
    0x0CC1,
    0xEF1F,
    0xFF3E,
    0xCF5D,
    0xDF7C,
    0xAF9B,
    0xBFBA,
    0x8FD9,
    0x9FF8,
    0x6E17,
    0x7E36,
    0x4E55,
    0x5E74,
    0x2E93,
    0x3EB2,
    0x0ED1,
    0x1EF0,
]


def crc16(data: bytes) -> int:
    """Calculate CRC-16-CCITT checksum."""
    crc = 0xFFFF
    for byte in data:
        crc = ((crc << 8) ^ CRC16_TABLE[(crc >> 8) ^ byte]) & 0xFFFF
    return crc


logger = logging.getLogger(__name__)


class FPBInjectError(Exception):
    """Exception for FPB inject operations."""

    pass


class FPBInject:
    """FPB Inject operations manager."""

    def __init__(self, device_state):
        self.device = device_state
        self._toolchain_path = None

    def set_toolchain_path(self, path: str):
        """Set the toolchain path."""
        if path and os.path.isdir(path):
            self._toolchain_path = path
            logger.info(f"Toolchain path set to: {path}")
        else:
            self._toolchain_path = None

    def get_tool_path(self, tool_name: str) -> str:
        """Get full path for a toolchain tool."""
        if self._toolchain_path:
            full_path = os.path.join(self._toolchain_path, tool_name)
            if os.path.exists(full_path):
                return full_path
        return tool_name

    def enter_fl_mode(self, timeout: float = 1.0) -> bool:
        """Enter fl interactive mode by sending 'fl' command."""
        ser = self.device.ser
        if not ser:
            return False

        try:
            self._log_raw("TX", "fl")
            ser.reset_input_buffer()
            ser.write(b"fl\n")
            ser.flush()

            # Wait for prompt or response
            start = time.time()
            response = ""
            while time.time() - start < timeout:
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                    response += chunk
                    if "fl>" in response or "[OK]" in response:
                        break
                time.sleep(0.01)

            self._log_raw("RX", response.strip())
            logger.debug(f"Entered fl mode: {response.strip()}")
            return True
        except Exception as e:
            logger.error(f"Error entering fl mode: {e}")
            return False

    def exit_fl_mode(self, timeout: float = 1.0) -> bool:
        """Exit fl interactive mode by sending 'exit' command."""
        ser = self.device.ser
        if not ser:
            return False

        try:
            self._log_raw("TX", "exit")
            ser.reset_input_buffer()
            ser.write(b"exit\n")
            ser.flush()

            # Wait for response
            start = time.time()
            response = ""
            while time.time() - start < timeout:
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                    response += chunk
                time.sleep(0.01)

            self._log_raw("RX", response.strip())
            logger.debug(f"Exited fl mode: {response.strip()}")
            return True
        except Exception as e:
            logger.error(f"Error exiting fl mode: {e}")
            return False

    def _send_cmd(
        self, cmd: str, timeout: float = 2.0, retry_on_missing_cmd: bool = True
    ) -> str:
        """Send command and get response."""
        ser = self.device.ser
        if not ser:
            raise FPBInjectError("Serial port not connected")

        # Build command: fl --cmd ...
        # Note: -ni flag is NOT used here - it's only for entering interactive mode
        full_cmd = f"fl {cmd}" if not cmd.strip().startswith("fl ") else cmd
        logger.debug(f"TX: {full_cmd}")

        # Log raw TX
        self._log_raw("TX", full_cmd)

        # Clear buffer
        ser.reset_input_buffer()

        # Send command
        ser.write((full_cmd + "\n").encode())
        ser.flush()

        # Read response
        response = ""
        start = time.time()
        while time.time() - start < timeout:
            if ser.in_waiting:
                chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                response += chunk
                if "[OK]" in response or "[ERR]" in response:
                    time.sleep(0.005)
                    if ser.in_waiting:
                        response += ser.read(ser.in_waiting).decode(
                            "utf-8", errors="replace"
                        )
                    break
            time.sleep(0.002)

        logger.debug(f"RX: {response.strip()}")
        # Log raw RX
        self._log_raw("RX", response.strip())

        # Check if we got "Missing --cmd" which means we're not in fl mode
        # Need to enter fl mode first and retry
        if retry_on_missing_cmd and "Missing --cmd" in response:
            logger.info("Detected 'Missing --cmd', entering fl mode and retrying...")
            self._log_raw("INFO", "Not in fl mode, entering...")
            if self.enter_fl_mode():
                # Retry the command (without retry to avoid infinite loop)
                return self._send_cmd(cmd, timeout, retry_on_missing_cmd=False)

        return response.strip()

    def _log_raw(self, direction: str, data: str):
        """Log raw serial communication to device's raw_serial_log."""
        if not data:
            return
        try:
            import time as t

            entry = {
                "id": self.device.raw_log_next_id,
                "time": t.time(),
                "dir": direction,
                "data": data,
            }
            self.device.raw_serial_log.append(entry)
            self.device.raw_log_next_id += 1
            # Trim if too large
            max_size = getattr(self.device, "raw_log_max_size", 5000)
            if len(self.device.raw_serial_log) > max_size:
                self.device.raw_serial_log = self.device.raw_serial_log[-max_size:]
        except Exception:
            pass

    def _parse_response(self, resp: str) -> dict:
        """Parse response - format: [OK] msg or [ERR] msg"""
        resp = resp.strip()
        lines = resp.split("\n")
        for line in reversed(lines):
            line = line.strip()
            if line.startswith("[OK]"):
                msg = line[4:].strip()
                return {"ok": True, "msg": msg, "raw": resp}
            elif line.startswith("[ERR]"):
                msg = line[5:].strip()
                return {"ok": False, "msg": msg, "raw": resp}
        return {"ok": False, "msg": resp, "raw": resp}

    def ping(self) -> Tuple[bool, str]:
        """Ping device."""
        try:
            resp = self._send_cmd("--cmd ping")
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def info(self) -> Tuple[Optional[dict], str]:
        """Get device info."""
        try:
            resp = self._send_cmd("--cmd info")
            result = self._parse_response(resp)

            if result.get("ok"):
                raw = result.get("raw", "")
                info = {"ok": True}
                for line in raw.split("\n"):
                    line = line.strip()
                    if line.startswith("Base:"):
                        try:
                            info["base"] = int(line.split(":")[1].strip(), 0)
                        except:
                            pass
                    elif line.startswith("Size:"):
                        try:
                            info["size"] = int(line.split(":")[1].strip())
                        except:
                            pass
                    elif line.startswith("Used:"):
                        try:
                            info["used"] = int(line.split(":")[1].strip())
                        except:
                            pass
                return info, ""
            return None, result.get("msg", "Unknown error")
        except Exception as e:
            return None, str(e)

    def alloc(self, size: int) -> Tuple[Optional[int], str]:
        """Allocate memory buffer."""
        try:
            resp = self._send_cmd(f"--cmd alloc --size {size}")
            result = self._parse_response(resp)
            if result.get("ok"):
                msg = result.get("msg", "")
                match = re.search(r"0x([0-9A-Fa-f]+)", msg)
                if match:
                    base = int(match.group(1), 16)
                    return base, ""
            return None, result.get("msg", "Alloc failed")
        except Exception as e:
            return None, str(e)

    def free(self) -> Tuple[bool, str]:
        """Free memory buffer."""
        try:
            resp = self._send_cmd("--cmd free")
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def clear(self) -> Tuple[bool, str]:
        """Clear upload buffer."""
        try:
            resp = self._send_cmd("--cmd clear")
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def upload(
        self, data: bytes, start_offset: int = 0, progress_callback=None
    ) -> Tuple[bool, dict]:
        """Upload binary data in chunks using base64 encoding."""
        total = len(data)
        data_offset = 0
        bytes_per_chunk = 48

        upload_start = time.time()
        chunk_count = 0
        total_chunks = (total + bytes_per_chunk - 1) // bytes_per_chunk

        while data_offset < total:
            chunk = data[data_offset : data_offset + bytes_per_chunk]
            b64_data = base64.b64encode(chunk).decode("ascii")
            crc = crc16(chunk)

            device_offset = start_offset + data_offset
            cmd = f"--cmd upload --addr 0x{device_offset:X} --data {b64_data} --crc 0x{crc:04X}"

            try:
                resp = self._send_cmd(cmd)
                result = self._parse_response(resp)

                if not result.get("ok"):
                    return False, {
                        "error": f"Upload failed at offset 0x{device_offset:X}: {result.get('msg')}"
                    }
            except Exception as e:
                return False, {"error": str(e)}

            data_offset += len(chunk)
            chunk_count += 1

            if progress_callback:
                progress_callback(data_offset, total)

        upload_time = time.time() - upload_start
        speed = total / upload_time if upload_time > 0 else 0

        return True, {
            "bytes": total,
            "chunks": chunk_count,
            "time": upload_time,
            "speed": speed,
        }

    def patch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set FPB patch (direct mode)."""
        try:
            cmd = f"--cmd patch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
            resp = self._send_cmd(cmd)
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def tpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set trampoline patch."""
        try:
            cmd = f"--cmd tpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
            resp = self._send_cmd(cmd)
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def dpatch(self, comp: int, orig: int, target: int) -> Tuple[bool, str]:
        """Set DebugMonitor patch."""
        try:
            cmd = f"--cmd dpatch --comp {comp} --orig 0x{orig:X} --target 0x{target:X}"
            resp = self._send_cmd(cmd)
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def unpatch(self, comp: int) -> Tuple[bool, str]:
        """Clear FPB patch."""
        try:
            cmd = f"--cmd unpatch --comp {comp}"
            resp = self._send_cmd(cmd)
            result = self._parse_response(resp)
            return result.get("ok", False), result.get("msg", "")
        except Exception as e:
            return False, str(e)

    def get_symbols(self, elf_path: str) -> Dict[str, int]:
        """Extract symbols from ELF file."""
        symbols = {}
        try:
            nm_tool = self.get_tool_path("arm-none-eabi-nm")
            result = subprocess.run(
                [nm_tool, "-C", elf_path], capture_output=True, text=True, check=True
            )
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    addr = int(parts[0], 16)
                    name = parts[2]
                    symbols[name] = addr
        except Exception as e:
            logger.error(f"Error reading symbols: {e}")
        return symbols

    def parse_compile_commands(
        self, compile_commands_path: str, verbose: bool = False
    ) -> Optional[Dict]:
        """Parse compile_commands.json to extract compiler flags."""
        import json
        import shlex

        if not os.path.exists(compile_commands_path):
            return None

        try:
            with open(compile_commands_path, "r") as f:
                commands = json.load(f)
        except Exception as e:
            logger.error(f"Error loading compile_commands.json: {e}")
            return None

        if not commands:
            return None

        # Find a suitable entry
        selected_entry = None
        for entry in commands:
            file_path = entry.get("file", "")
            if file_path.endswith(".c") and "__ASSEMBLY__" not in entry.get(
                "command", ""
            ):
                selected_entry = entry
                break

        if not selected_entry:
            return None

        command_str = selected_entry.get("command", "")
        if not command_str:
            return None

        try:
            tokens = shlex.split(command_str)
        except Exception:
            return None

        compiler = tokens[0] if tokens else "arm-none-eabi-gcc"
        includes = []
        defines = []
        cflags = []

        i = 1
        while i < len(tokens):
            token = tokens[i]

            if token == "-I" and i + 1 < len(tokens):
                includes.append(tokens[i + 1])
                i += 2
                continue
            elif token.startswith("-I"):
                includes.append(token[2:])
                i += 1
                continue

            if token == "-isystem" and i + 1 < len(tokens):
                includes.append(tokens[i + 1])
                i += 2
                continue

            if token == "-D" and i + 1 < len(tokens):
                defines.append(tokens[i + 1])
                i += 2
                continue
            elif token.startswith("-D"):
                defines.append(token[2:])
                i += 1
                continue

            if token == "-o" and i + 1 < len(tokens):
                i += 2
                continue

            if token.endswith((".c", ".cpp", ".S", ".s", ".o")):
                i += 1
                continue

            if token == "--param" and i + 1 < len(tokens):
                i += 2
                continue

            if token.startswith("-Wa,"):
                i += 1
                continue

            if any(
                token.startswith(p)
                for p in [
                    "-mthumb",
                    "-mcpu",
                    "-mtune",
                    "-march",
                    "-mfpu",
                    "-mfloat-abi",
                ]
            ):
                cflags.append(token)
            elif token in [
                "-ffunction-sections",
                "-fdata-sections",
                "-fno-common",
                "-nostdlib",
            ]:
                cflags.append(token)

            i += 1

        if "-Os" not in cflags:
            cflags.append("-Os")

        includes = list(dict.fromkeys(includes))
        defines = list(dict.fromkeys(defines))
        cflags = list(dict.fromkeys(cflags))

        compiler_dir = os.path.dirname(compiler)
        compiler_name = os.path.basename(compiler)
        objcopy_name = compiler_name.replace("gcc", "objcopy").replace("g++", "objcopy")
        objcopy = (
            os.path.join(compiler_dir, objcopy_name) if compiler_dir else objcopy_name
        )

        return {
            "compiler": compiler,
            "objcopy": objcopy,
            "includes": includes,
            "defines": defines,
            "cflags": cflags,
            "ldflags": [],
        }

    def compile_inject(
        self,
        source_content: str,
        base_addr: int,
        elf_path: str = None,
        compile_commands_path: str = None,
        verbose: bool = False,
    ) -> Tuple[Optional[bytes], Optional[Dict[str, int]], str]:
        """
        Compile injection code from source content to binary.

        Args:
            source_content: Source code content to compile
            base_addr: Base address for injection code
            elf_path: Path to main ELF for symbol resolution
            compile_commands_path: Path to compile_commands.json
            verbose: Enable verbose output

        Returns:
            Tuple of (binary_data, symbols, error_message)
        """
        config = None
        if compile_commands_path:
            config = self.parse_compile_commands(compile_commands_path, verbose=verbose)

        if not config:
            return (
                None,
                None,
                "No compile configuration found. Please provide compile_commands.json path.",
            )

        compiler = config.get("compiler", "arm-none-eabi-gcc")
        objcopy = config.get("objcopy", "arm-none-eabi-objcopy")

        if not os.path.isabs(compiler):
            compiler = self.get_tool_path(compiler)
        if not os.path.isabs(objcopy):
            objcopy = self.get_tool_path(objcopy)

        includes = config.get("includes", [])
        defines = config.get("defines", [])
        cflags = config.get("cflags", [])

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write source to file
            source_file = os.path.join(tmpdir, "inject.cpp")
            with open(source_file, "w") as f:
                f.write(source_content)

            obj_file = os.path.join(tmpdir, "inject.o")
            elf_file = os.path.join(tmpdir, "inject.elf")
            bin_file = os.path.join(tmpdir, "inject.bin")

            # Compile to object
            cmd = [compiler] + cflags + ["-c"]

            for inc in includes:
                if os.path.isdir(inc):
                    cmd.extend(["-I", inc])

            for d in defines:
                cmd.extend(["-D", d])

            cmd.extend(["-o", obj_file, source_file])

            if verbose:
                logger.info(f"Compile: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return None, None, f"Compile error:\n{result.stderr}"

            # Create linker script
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
            ld_file = os.path.join(tmpdir, "inject.ld")
            with open(ld_file, "w") as f:
                f.write(ld_content)

            # Link
            link_cmd = (
                [compiler] + cflags[:2] + ["-nostartfiles", "-nostdlib", f"-T{ld_file}"]
            )

            if elf_path and os.path.exists(elf_path):
                link_cmd.append(f"-Wl,--just-symbols={elf_path}")

            link_cmd.extend(["-o", elf_file, obj_file])

            if verbose:
                logger.info(f"Link: {' '.join(link_cmd)}")

            result = subprocess.run(link_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return None, None, f"Link error:\n{result.stderr}"

            # Extract binary
            subprocess.run([objcopy, "-O", "binary", elf_file, bin_file], check=True)

            # Read binary
            with open(bin_file, "rb") as f:
                data = f.read()

            # Get symbols
            nm_cmd = objcopy.replace("objcopy", "nm")
            result = subprocess.run(
                [nm_cmd, "-C", elf_file], capture_output=True, text=True
            )

            symbols = {}
            for line in result.stdout.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 3:
                    addr = int(parts[0], 16)
                    name = parts[2]
                    symbols[name] = addr

            return data, symbols, ""

    def inject(
        self,
        source_content: str,
        target_func: str,
        inject_func: str = None,
        patch_mode: str = "trampoline",
        comp: int = 0,
        progress_callback=None,
    ) -> Tuple[bool, dict]:
        """
        Perform full injection workflow.

        Args:
            source_content: Patch source code content
            target_func: Target function name to replace
            inject_func: Inject function name (default: auto-detect)
            patch_mode: Patch mode (trampoline, debugmon, direct)
            comp: FPB comparator index
            progress_callback: Progress callback function

        Returns:
            Tuple of (success, result_dict)
        """
        result = {
            "compile_time": 0,
            "upload_time": 0,
            "total_time": 0,
            "code_size": 0,
            "inject_func": None,
            "target_addr": None,
            "inject_addr": None,
        }

        total_start = time.time()

        # Load ELF symbols
        elf_path = self.device.elf_path
        if not elf_path or not os.path.exists(elf_path):
            return False, {"error": "ELF file not found"}

        symbols = self.get_symbols(elf_path)
        if target_func not in symbols:
            return False, {"error": f"Target function '{target_func}' not found in ELF"}

        target_addr = symbols[target_func]
        result["target_addr"] = f"0x{target_addr:08X}"

        # Get device info
        info, error = self.info()
        if error:
            return False, {"error": f"Failed to get device info: {error}"}

        is_dynamic = info and info.get("base", 0) == 0 and info.get("size", 0) == 0

        compile_start = time.time()

        if is_dynamic:
            # Dynamic allocation: compile first to get size
            data, inject_symbols, error = self.compile_inject(
                source_content,
                0x20000000,
                elf_path,
                self.device.compile_commands_path,
            )
            if error:
                return False, {"error": error}

            code_size = len(data)
            alloc_size = code_size + 8

            raw_addr, error = self.alloc(alloc_size)
            if error:
                return False, {"error": f"Alloc failed: {error}"}

            aligned_addr = (raw_addr + 7) & ~7
            align_offset = aligned_addr - raw_addr
            base_addr = aligned_addr

            # Recompile with aligned address
            data, inject_symbols, error = self.compile_inject(
                source_content,
                base_addr,
                elf_path,
                self.device.compile_commands_path,
            )
            if error:
                return False, {"error": error}
        else:
            base_addr = info.get("base", 0x20001000) if info else 0x20001000
            align_offset = 0

            data, inject_symbols, error = self.compile_inject(
                source_content,
                base_addr,
                elf_path,
                self.device.compile_commands_path,
            )
            if error:
                return False, {"error": error}

        compile_time = time.time() - compile_start
        result["compile_time"] = round(compile_time, 2)
        result["code_size"] = len(data)

        # Find inject function
        found_inject_func = None
        if inject_func:
            for name, addr in inject_symbols.items():
                if inject_func in name:
                    found_inject_func = (name, addr)
                    break
        else:
            target_lower = target_func.lower()
            for name, addr in inject_symbols.items():
                name_lower = name.lower()
                if name_lower.startswith("inject_") and target_lower in name_lower:
                    found_inject_func = (name, addr)
                    break

            if not found_inject_func:
                inject_funcs = [
                    (n, a) for n, a in inject_symbols.items() if n.startswith("inject_")
                ]
                if inject_funcs:
                    found_inject_func = min(inject_funcs, key=lambda x: x[1])

        if not found_inject_func:
            return False, {"error": "No inject_* function found in source"}

        result["inject_func"] = found_inject_func[0]
        result["inject_addr"] = f"0x{found_inject_func[1]:08X}"

        # Clear and upload
        self.clear()
        success, upload_result = self.upload(
            data, start_offset=align_offset, progress_callback=progress_callback
        )
        if not success:
            return False, {"error": upload_result.get("error", "Upload failed")}

        result["upload_time"] = round(upload_result.get("time", 0), 2)

        # Apply patch
        patch_addr = found_inject_func[1] | 1  # Thumb address

        if patch_mode == "trampoline":
            success, msg = self.tpatch(comp, target_addr, patch_addr)
        elif patch_mode == "debugmon":
            success, msg = self.dpatch(comp, target_addr, patch_addr)
        else:
            success, msg = self.patch(comp, target_addr, patch_addr)

        if not success:
            return False, {"error": f"Patch failed: {msg}"}

        result["total_time"] = round(time.time() - total_start, 2)
        result["patch_mode"] = patch_mode

        # Update device state
        self.device.inject_active = True
        self.device.last_inject_target = target_func
        self.device.last_inject_func = found_inject_func[0]
        self.device.last_inject_time = time.time()

        return True, result


def scan_serial_ports() -> List[dict]:
    """Scan for available serial ports."""
    import glob

    ports = serial.tools.list_ports.comports()
    result = [
        {"device": port.device, "description": port.description} for port in ports
    ]

    # Also scan for CH341 USB serial devices
    ch341_devices = glob.glob("/dev/ttyCH341USB*")
    existing_devices = {item["device"] for item in result}
    for dev in ch341_devices:
        if dev not in existing_devices:
            result.append({"device": dev, "description": "CH341 USB Serial"})

    return result


def serial_open(port: str, baudrate: int = 115200, timeout: float = 2.0):
    """Open a serial port."""
    try:
        ser = serial.Serial(port, baudrate, timeout=timeout, write_timeout=timeout)
        if not ser.isOpen():
            return None, f"Error opening serial port {port}"
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.1)
        return ser, None
    except serial.SerialException as e:
        return None, f"Serial error: {e}"
    except Exception as e:
        return None, f"Error: {e}"
