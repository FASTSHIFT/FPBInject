#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
FPBInject Web Server
A web-based control interface for FPBInject runtime code injection.

Module structure:
- state.py: Application state management
- device_worker.py: Device worker thread management
- fpb_inject.py: FPB injection operations
- file_watcher.py: File system monitoring
- routes.py: Flask API routes
- main.py: Application entry point
"""

import argparse
import importlib
import importlib.metadata
import logging
import os
import shutil
import socket
import subprocess
import sys
import webbrowser
import threading

from flask import Flask
from flask_cors import CORS

from routes import register_routes
from core.state import state
from fpb_inject import serial_open
from services.device_worker import start_worker
from services.file_watcher_manager import restore_file_watcher

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Module logger
logger = logging.getLogger(__name__)


def check_requirements():
    """Check if all required packages from requirements.txt are installed.

    Returns True if all packages are available or user chose to continue.
    """
    req_path = os.path.join(SCRIPT_DIR, "..", "requirements.txt")
    if not os.path.exists(req_path):
        return True

    missing = []
    with open(req_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Extract package name (strip version specifiers)
            pkg_name = line.split(">=")[0].split("==")[0].split("<")[0].strip()
            if not pkg_name:
                continue
            # Use importlib.metadata to check by distribution (pip) name
            # This correctly handles cases like pyserial (pip) -> serial (import)
            try:
                importlib.metadata.distribution(pkg_name)
            except importlib.metadata.PackageNotFoundError:
                missing.append(line)

    if not missing:
        return True

    print(f"\n⚠️  Missing {len(missing)} required package(s):")
    for pkg in missing:
        print(f"   - {pkg}")
    print()

    # Non-interactive mode (CI, piped stdin): skip
    if not sys.stdin.isatty():
        print("Non-interactive mode, skipping install prompt.")
        return True

    try:
        answer = (
            input("Install now? [Y/n/q] (Y=install, n=skip, q=quit): ").strip().lower()
        )
    except (EOFError, KeyboardInterrupt):
        return True

    if answer == "q":
        print("Aborted.")
        sys.exit(0)
    elif answer in ("", "y", "yes"):
        print(f"Installing: {' '.join(missing)}")
        ret = subprocess.call([sys.executable, "-m", "pip", "install"] + missing)
        if ret != 0:
            print("⚠️  Some packages failed to install, continuing anyway...")
        else:
            print("✅ All packages installed successfully.")
    else:
        print("Skipping install, continuing...")

    return True


def check_toolchain():
    """Check if gdb-multiarch is installed.

    Returns True if available or user chose to continue.
    """
    if shutil.which("gdb-multiarch"):
        return True

    print("\n⚠️  'gdb-multiarch' not found in PATH.")
    print("   GDB features (symbol lookup, struct layout, watch expressions)")
    print("   will not be available without it.")
    print()
    print("   Install on Debian/Ubuntu:")
    print("     sudo apt-get install gdb-multiarch")
    print()

    # Non-interactive mode: skip
    if not sys.stdin.isatty():
        print("Non-interactive mode, continuing without gdb-multiarch.")
        return True

    try:
        answer = (
            input("Continue without GDB? [Y/n/q] (Y=continue, q=quit): ")
            .strip()
            .lower()
        )
    except (EOFError, KeyboardInterrupt):
        return True

    if answer == "q":
        print("Aborted.")
        sys.exit(0)

    return True


def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(SCRIPT_DIR, "templates"),
        static_folder=os.path.join(SCRIPT_DIR, "static"),
    )
    CORS(app)
    register_routes(app)
    return app


def check_port_available(host, port):
    """Check if the port is available."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex(("127.0.0.1", port))
        if result == 0:
            return False
        return True
    except Exception:
        return True
    finally:
        sock.close()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="FPBInject Web Server")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the server (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5500,
        help="Port to run the server (default: 5500)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode",
    )
    parser.add_argument(
        "--skip-port-check",
        action="store_true",
        help="Skip port availability check (use with caution)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not auto-open browser on startup",
    )
    return parser.parse_args()


def restore_state():
    """Restore serial connection state and file watcher."""
    device = state.device

    # Restore file watcher if auto_compile is enabled
    if device.auto_compile and device.watch_dirs:
        logger.info(
            f"Restoring file watcher for {len(device.watch_dirs)} directories..."
        )
        restore_file_watcher()
        logger.info("File watcher restored")

    # Restore ELF file watcher if elf_path is configured
    if device.elf_path:
        from services.file_watcher_manager import start_elf_watcher

        logger.info(f"Restoring ELF file watcher for: {device.elf_path}")
        if start_elf_watcher(device.elf_path):
            logger.info("ELF file watcher restored")
        else:
            logger.warning("Failed to restore ELF file watcher")

    # Restore log file recording if enabled
    if device.log_file_enabled and device.log_file_path:
        from services.log_recorder import log_recorder

        logger.info(f"Restoring log file recording: {device.log_file_path}")
        success, error = log_recorder.start(device.log_file_path)
        if success:
            logger.info("Log file recording restored")
        else:
            logger.warning(f"Failed to restore log recording: {error}")
            device.log_file_enabled = False

    # Start GDB integration if ELF path is configured (works offline too)
    if device.elf_path and os.path.exists(device.elf_path):
        from core.gdb_manager import start_gdb_async

        logger.info(f"Auto-starting GDB for ELF: {device.elf_path}")
        start_gdb_async(state)

    # Check auto-connect conditions
    if not device.auto_connect or not device.port:
        return

    logger.info(f"Auto-connecting to {device.port}...")

    # Start worker first
    start_worker(device)

    ser, error = serial_open(device.port, device.baudrate, device.timeout)
    if error:
        logger.warning(f"Auto-connect failed: {error}")
        return

    device.ser = ser
    logger.info(f"Auto-connected to {device.port}")


def main():
    """Main entry point."""
    args = parse_args()

    # Configure logging early
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [TID:%(thread)d] [%(levelname)s] %(name)s: %(message)s",
    )

    # Reduce verbosity of Flask/Werkzeug request logs
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    # Check dependencies
    check_requirements()

    # Check toolchain (gdb-multiarch)
    check_toolchain()

    # Check if port is already in use, unless skipped
    if not args.skip_port_check:
        if not check_port_available(args.host, args.port):
            logger.error(f"❌ Error: Port {args.port} is already in use!")
            logger.error("   Another FPBInject server may already be running.")
            logger.error(
                "   Please close the program occupying this port, or use --port to specify another port."
            )
            logger.error(f"   Example: ./main.py --port {args.port + 1}")
            logger.error("   Or use --skip-port-check to force start (not recommended)")
            sys.exit(1)

    app = create_app()

    # Restore previous state (auto-connect)
    restore_state()

    local_url = f"http://127.0.0.1:{args.port}"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip = "unavailable"
    lan_url = f"http://{lan_ip}:{args.port}"

    logger.info("")
    logger.info("  ╔══════════════════════════════════════════════╗")
    logger.info("  ║        FPBInject Web Server Started          ║")
    logger.info("  ╠══════════════════════════════════════════════╣")
    logger.info(f"  ║  🏠 Local:   {local_url:<32s}║")
    logger.info(f"  ║  🌐 Network: {lan_url:<32s}║")
    logger.info("  ╚══════════════════════════════════════════════╝")
    logger.info("")

    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=[local_url]).start()

    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
