#!/usr/bin/env python3
"""Argparse construction for the FPBInject CLI.

Extracted from ``fpb_cli.main`` to keep that module under the file-size
limit. ``build_parser(prog)`` returns the fully-configured ArgumentParser;
``fpb_cli.main`` parses and dispatches.
"""

import argparse
import os

from fpbinject.version import __version__ as FPB_VERSION
from fpbinject.cli.server_proxy import DEFAULT_SERVER_URL
from fpbinject.cli.connection_plan import CommandPolicy


def build_parser(prog: str) -> argparse.ArgumentParser:
    """Build the CLI ArgumentParser (all subcommands)."""
    epilog = f"""
Examples:
  # ELF analysis works offline — no device, no --port:
  {prog} analyze firmware.elf digitalWrite
  {prog} search firmware.elf gpio
  {prog} compile patch.c --elf firmware.elf --compile-commands build/compile_commands.json

  # Local device commands — first time, --port triggers auto-launch:
  {prog} --port /dev/ttyACM0 info
  {prog} --port /dev/ttyACM0 inject digitalWrite patch.c --elf firmware.elf

  # Once a local server has the device connected, --port is no longer needed:
  {prog} info
  {prog} file-stat /etc/init.d/rcS

  # Remote control — the device lives on the server, so no --port needed:
  {prog} --server-url http://192.168.1.20:5500 --token TOKEN info
  # Only pass --port to tell the remote server which port to open if it has none:
  {prog} --server-url http://192.168.1.20:5500 --token TOKEN --port /dev/ttyACM0 connect

Notes:
  The serial port belongs to the WebServer, not the CLI. In proxy mode (local
  or remote) --port is optional whenever the server already has a connected
  device; it is only required to open a port when no device is connected yet,
  or for direct/auto-launch on a fresh local environment.
  --token (or FPB_TOKEN env) is required for remote servers.
  Output is JSON on stdout; pipe to jq for filtering.
  Run '{prog} <command> --help' for command-specific options.

Complex / multi-step workflows -> use the Python SDK instead of chaining
this CLI. Anything the CLI does, the SDK does in-process with real return
values (no JSON re-parsing), which is far easier for loops, retries and
multi-device orchestration. Minimal example:

  from fpbinject import Client
  with Client.direct("/dev/ttyACM0") as dev:      # or Client.discover(token=...)
      dev.inject("digitalWrite", "patch.c", elf="firmware.elf")
      dev.file_upload("app.bin", "/data/app.bin",
                      progress=lambda done, total: None)
      print(dev.test_serial())                    # tuning probe

Good SDK fits: batch-inject many functions, download-then-verify loops,
retry-with-tuning on serial loss, driving several devices in parallel.
The full API surface (constructor, class methods, every device / file / mem
call) is documented in the `Client` class docstring; from a REPL run
`from fpbinject import Client; help(Client)` — or read
`fpbinject/client.py` in the installed package.
        """
    description = (
        "FPBInject CLI - Lightweight interface for binary patching.\n"
        "\n"
        "Before you start (mental model):\n"
        "  1. Analysis (analyze/search/disasm) is OFFLINE - no device, no --port.\n"
        "  2. The serial port belongs to the WebServer; once a device is\n"
        "     connected, device commands need NO --port (--baudrate defaults to\n"
        "     115200, rarely changed).\n"
        "  3. Serial transfers/reads are slow & windowed: progress on stderr,\n"
        "     small tail by default - a long-but-progressing op is NOT a hang.\n"
        "  4. Stuck on serial loss? run `%(prog)s doctor`.\n"
        "  5. Multi-step automation? use the Python SDK - see the epilog\n"
        "     below for a minimal example, then `help(fpbinject.Client)`.\n"
    ) % {"prog": prog}
    parser = argparse.ArgumentParser(
        prog=prog,
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )

    # Global options
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stderr transfer notices/progress (stdout JSON only).",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {FPB_VERSION}"
    )
    # Serial/connection and transfer flags (--port, --baudrate, --data-bits,
    # --serial-tx-fragment-size, ...) are generated from the shared config
    # schema so the CLI and the server expose the same options and names.
    from fpbinject.core.arg_schema import add_connection_args

    add_connection_args(parser)
    parser.add_argument("--elf", help="Path to ELF file")
    parser.add_argument("--compile-commands", help="Path to compile_commands.json")
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Force direct serial connection (skip WebServer proxy detection).",
    )
    parser.add_argument(
        "-s",
        "--server",
        type=str,
        default=None,
        help="Server to talk to. Accepts a discovery handle (e.g. "
        "'bench:5501'), a hostname when unique on the LAN, or a full URL. "
        "Falls back to FPB_SERVER env var, then auto-discovery.",
    )
    parser.add_argument(
        "--server-url",
        dest="server_url_legacy",
        type=str,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-discovery",
        action="store_true",
        help=f"Disable mDNS auto-discovery and fall back to {DEFAULT_SERVER_URL}.",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.environ.get("FPB_TOKEN"),
        help="Auth token for the WebServer. Required when the server returns "
        "401/403. Can also be set via the FPB_TOKEN environment variable.",
    )

    parser.set_defaults(command_policy=CommandPolicy.DEVICE)
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze function")
    analyze_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    analyze_parser.add_argument("elf_path", help="Path to ELF file")
    analyze_parser.add_argument("func_name", help="Function name to analyze")

    # disasm command
    disasm_parser = subparsers.add_parser("disasm", help="Get disassembly")
    disasm_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    disasm_parser.add_argument("elf_path", help="Path to ELF file")
    disasm_parser.add_argument("func_name", help="Function name")

    # decompile command
    decomp_parser = subparsers.add_parser("decompile", help="Decompile function")
    decomp_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    decomp_parser.add_argument("elf_path", help="Path to ELF file")
    decomp_parser.add_argument("func_name", help="Function name")

    # signature command
    sig_parser = subparsers.add_parser("signature", help="Get function signature")
    sig_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    sig_parser.add_argument("elf_path", help="Path to ELF file")
    sig_parser.add_argument("func_name", help="Function name")

    # search command
    search_parser = subparsers.add_parser("search", help="Search functions")
    search_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    search_parser.add_argument("elf_path", help="Path to ELF file")
    search_parser.add_argument("pattern", help="Search pattern")

    # get-symbols command
    symbols_parser = subparsers.add_parser(
        "get-symbols", help="Get all symbols from ELF file (via nm)"
    )
    symbols_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    symbols_parser.add_argument("elf_path", help="Path to ELF file")
    symbols_parser.add_argument(
        "--filter", default="", help="Filter pattern (case-insensitive)"
    )
    symbols_parser.add_argument(
        "--limit", type=int, default=0, help="Max results (0=unlimited)"
    )

    # compile command
    compile_parser = subparsers.add_parser("compile", help="Compile patch source")
    compile_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    compile_parser.add_argument("source_file", help="Source C file")
    compile_parser.add_argument(
        "--addr",
        type=lambda x: int(x, 0),
        default=0x20001000,
        help="Base address (default: 0x20001000)",
    )

    # info command (requires device)
    subparsers.add_parser("info", help="Get device FPB info (requires device)")

    # test-serial command (requires device)
    test_serial_parser = subparsers.add_parser(
        "test-serial",
        help="Test serial throughput to find max transfer size (requires device)",
    )
    test_serial_parser.add_argument(
        "--start-size",
        type=int,
        default=16,
        help="Starting test size in bytes (default: 16)",
    )
    test_serial_parser.add_argument(
        "--max-size",
        type=int,
        default=4096,
        help="Maximum test size in bytes (default: 4096)",
    )
    test_serial_parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Timeout per test in seconds (default: 2.0)",
    )
    test_serial_parser.add_argument(
        "--trials",
        type=int,
        default=8,
        help="Round-trips sampled per size for reliability (default: 8)",
    )
    test_serial_parser.add_argument(
        "--min-success-rate",
        type=float,
        default=1.0,
        help="Success fraction required to accept a size (default: 1.0)",
    )

    # doctor command (requires device) — diagnose serial loss + suggest tuning
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Diagnose serial reliability and print copy-paste tuning flags "
        "(requires device)",
    )
    doctor_parser.add_argument(
        "--start-size", type=int, default=16, help="Starting probe size (default: 16)"
    )
    doctor_parser.add_argument(
        "--max-size", type=int, default=512, help="Maximum probe size (default: 512)"
    )
    doctor_parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Timeout per probe in seconds (default: 2.0)",
    )
    doctor_parser.add_argument(
        "--trials",
        type=int,
        default=8,
        help="Round-trips sampled per size (default: 8)",
    )

    # inject command (requires device)
    inject_parser = subparsers.add_parser(
        "inject", help="Inject patch to device (requires device)"
    )
    inject_parser.add_argument("target_func", help="Target function name to replace")
    inject_parser.add_argument("source_file", help="Source C file")
    inject_parser.add_argument(
        "--mode",
        choices=["trampoline", "debugmon", "direct"],
        default="trampoline",
        help="Patch mode (default: trampoline)",
    )
    inject_parser.add_argument(
        "--comp", type=int, default=-1, help="FPB comparator slot (-1 for auto)"
    )
    inject_parser.add_argument(
        "--verify", action="store_true", help="Verify patch after injection"
    )

    # unpatch command (requires device)
    unpatch_parser = subparsers.add_parser(
        "unpatch", help="Remove patch (requires device)"
    )
    unpatch_parser.add_argument(
        "--comp", type=int, default=0, help="FPB comparator slot to unpatch"
    )
    unpatch_parser.add_argument("--all", action="store_true", help="Remove all patches")

    # mem-read command (requires device)
    memread_parser = subparsers.add_parser(
        "mem-read", help="Read memory from device (requires device)"
    )
    memread_parser.add_argument(
        "addr", type=lambda x: int(x, 0), help="Memory address (hex: 0x20000000)"
    )
    memread_parser.add_argument(
        "length", type=lambda x: int(x, 0), help="Number of bytes to read"
    )
    memread_parser.add_argument(
        "--fmt",
        choices=["hex", "raw", "u32"],
        default="hex",
        help="Output format: hex (dump), raw (hex string), u32 (32-bit words)",
    )

    # mem-write command (requires device)
    memwrite_parser = subparsers.add_parser(
        "mem-write", help="Write memory to device (requires device)"
    )
    memwrite_parser.add_argument(
        "addr", type=lambda x: int(x, 0), help="Memory address (hex: 0x20000000)"
    )
    memwrite_parser.add_argument(
        "data", help="Hex data to write (e.g., DEADBEEF01020304)"
    )

    # mem-dump command (requires device)
    memdump_parser = subparsers.add_parser(
        "mem-dump", help="Dump memory region to file (requires device)"
    )
    memdump_parser.add_argument(
        "addr", type=lambda x: int(x, 0), help="Start address (hex: 0x20000000)"
    )
    memdump_parser.add_argument(
        "length", type=lambda x: int(x, 0), help="Number of bytes to dump"
    )
    memdump_parser.add_argument("output", help="Output binary file path")

    # serial-send command (requires device)
    serial_send_parser = subparsers.add_parser(
        "serial-send", help="Send data to device serial port (requires device)"
    )
    serial_send_parser.add_argument("data", help="String to send to device")
    serial_send_parser.add_argument(
        "--no-read",
        action="store_true",
        help="Don't read response after sending",
    )
    serial_send_parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Response read timeout in seconds (default: 1.0)",
    )

    # serial-read command (requires device)
    serial_read_parser = subparsers.add_parser(
        "serial-read", help="Read recent serial output (requires device)"
    )
    serial_read_parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="How long to wait for data in seconds (default: 1.0)",
    )
    serial_read_parser.add_argument(
        "--lines",
        type=int,
        default=50,
        help="Max number of log lines to return (default: 50)",
    )
    serial_read_parser.add_argument(
        "--since",
        type=int,
        default=0,
        help="Cursor from a previous 'next' for incremental paging (default: 0). "
        "Walks the backlog without loss.",
    )
    serial_read_parser.add_argument(
        "--max-bytes",
        dest="max_bytes",
        type=int,
        default=4096,
        help="Hard cap on returned data bytes (default: 4096). Keeps a large "
        "backlog from blowing up your context.",
    )
    serial_read_parser.add_argument(
        "--tail",
        type=int,
        default=0,
        help="Return only the newest N bytes (adb logcat -t style); ignores --since.",
    )
    serial_read_parser.add_argument(
        "--drop",
        action="store_true",
        help="Skip the buffered backlog and just advance the cursor "
        "(adb logcat -c style); returns the new 'next'.",
    )

    # file-list command (requires device)
    file_list_parser = subparsers.add_parser(
        "file-list", help="List directory contents on device (requires device)"
    )
    file_list_parser.add_argument(
        "path", nargs="?", default="/", help="Directory path on device (default: /)"
    )

    # file-stat command (requires device)
    file_stat_parser = subparsers.add_parser(
        "file-stat", help="Get file/directory info on device (requires device)"
    )
    file_stat_parser.add_argument("path", help="File or directory path on device")

    # file-download command (requires device)
    file_download_parser = subparsers.add_parser(
        "file-download", help="Download file from device (requires device)"
    )
    file_download_parser.add_argument(
        "remote_path", help="Source file path on device (e.g., /data/log.bin)"
    )
    file_download_parser.add_argument(
        "local_path", help="Destination path on local machine (e.g., /tmp/log.bin)"
    )

    # file-upload command (requires device)
    file_upload_parser = subparsers.add_parser(
        "file-upload", help="Upload local file to device (requires device)"
    )
    file_upload_parser.add_argument(
        "local_path", help="Source file path on local machine"
    )
    file_upload_parser.add_argument(
        "remote_path", help="Destination path on device (e.g., /data/log.bin)"
    )

    # file-remove command (requires device)
    file_remove_parser = subparsers.add_parser(
        "file-remove", help="Remove file on device (requires device)"
    )
    file_remove_parser.add_argument("path", help="File path to remove on device")

    # file-mkdir command (requires device)
    file_mkdir_parser = subparsers.add_parser(
        "file-mkdir", help="Create directory on device (requires device)"
    )
    file_mkdir_parser.add_argument("path", help="Directory path to create on device")

    # file-rename command (requires device)
    file_rename_parser = subparsers.add_parser(
        "file-rename", help="Rename file or directory on device (requires device)"
    )
    file_rename_parser.add_argument("old_path", help="Current path on device")
    file_rename_parser.add_argument("new_path", help="New path on device")

    # connect command
    subparsers.add_parser("connect", help="Connect to device (requires device)")

    # disconnect command
    disconnect_parser = subparsers.add_parser(
        "disconnect", help="Disconnect from device"
    )
    disconnect_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)

    # vserial-start command — create virtual serial passthrough (proxy mode only)
    vserial_start_parser = subparsers.add_parser(
        "vserial-start",
        help="Create virtual serial passthrough on the server (requires server)",
    )
    vserial_start_parser.add_argument(
        "--symlink",
        default=None,
        help="Stable symlink path for the virtual serial device. Omit to use "
        "the server config (default 'auto': derived from the port name, "
        "e.g. /dev/ttyACM0 -> /tmp/fpb-ttyACM0). Pass a path to override.",
    )

    # vserial-stop command — remove virtual serial passthrough
    subparsers.add_parser(
        "vserial-stop",
        help="Remove virtual serial passthrough on the server (requires server)",
    )

    # vserial-status command — query virtual serial passthrough
    subparsers.add_parser(
        "vserial-status",
        help="Query virtual serial passthrough status (requires server)",
    )

    # discover command — list FPBInject WebServers visible via mDNS
    discover_parser = subparsers.add_parser(
        "discover", help="List FPBInject WebServers visible via mDNS"
    )
    discover_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    discover_parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Discovery timeout in seconds (default: 3.0).",
    )
    discover_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the default human table.",
    )

    # server-stop command
    server_stop_parser = subparsers.add_parser(
        "server-stop", help="Stop a CLI-launched WebServer background process"
    )
    server_stop_parser.set_defaults(command_policy=CommandPolicy.SERVER_ADMIN)
    server_stop_parser.add_argument(
        "--server-port",
        type=int,
        default=0,
        help="Port of the CLI server to stop (default: auto-detect or 5500)",
    )

    return parser
