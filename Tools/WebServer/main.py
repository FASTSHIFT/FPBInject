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
import atexit
import logging
import os
import signal
import socket
import sys

from flask import Flask
from flask_cors import CORS

from routes import register_routes, restore_file_watcher
from state import state
from fpb_inject import serial_open
from device_worker import start_worker

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Module logger
logger = logging.getLogger(__name__)


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
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Reduce verbosity of Flask/Werkzeug request logs
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    # Check if port is already in use
    if not check_port_available(args.host, args.port):
        logger.error(f"❌ 错误: 端口 {args.port} 已被占用！")
        logger.error("   可能已有另一个 FPBInject 服务器在运行。")
        logger.error("   请先关闭占用该端口的程序，或使用 --port 指定其他端口。")
        logger.error(f"   例如: ./main.py --port {args.port + 1}")
        sys.exit(1)

    app = create_app()

    # Restore previous state (auto-connect)
    restore_state()

    logger.info(f"Starting FPBInject Web Server on http://127.0.0.1:{args.port}")
    logger.info(
        f"⚠️  建议使用 http://127.0.0.1:{args.port} 访问（避免 localhost IPv6 延迟）"
    )
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
