#!/usr/bin/env python3
"""
ADB Shell to Virtual Serial Port Bridge

Creates a virtual serial port pair and bridges ADB shell to it.
Your tools can connect to the virtual serial port as if it were a real device.

Usage:
    python adb2serial.py                    # Use default device
    python adb2serial.py -s <device_id>     # Specify device
    python adb2serial.py --list             # List available devices

Requirements:
    - Linux: socat (apt install socat)
    - macOS: socat (brew install socat)
    - Windows: com0com or similar virtual serial port driver

Example:
    # Terminal 1: Start bridge
    python adb2serial.py
    # Output: Virtual serial port created: /dev/pts/3

    # Terminal 2: Connect your tool to /dev/pts/3
    python -m fpbinject.webserver  # Then select /dev/pts/3 as port
"""

import argparse
import os
import platform
import pty
import select
import signal
import subprocess
import sys
import threading
import time


class AdbSerialBridge:
    """Bridge ADB shell to virtual serial port"""

    def __init__(self, device_id=None):
        self.device_id = device_id
        self.adb_process = None
        self.master_fd = None
        self.slave_fd = None
        self.slave_name = None
        self.running = False

    def list_devices(self):
        """List available ADB devices"""
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            print("Available ADB devices:")
            print("-" * 40)
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            devices = []
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        device_id = parts[0]
                        status = parts[1]
                        devices.append((device_id, status))
                        marker = " *" if status == "device" else ""
                        print(f"  {device_id}\t{status}{marker}")
            if not devices:
                print("  (no devices found)")
            print("-" * 40)
            return devices
        except FileNotFoundError:
            print("Error: adb not found. Please install Android SDK platform-tools.")
            return []
        except Exception as e:
            print(f"Error listing devices: {e}")
            return []

    def create_pty(self):
        """Create pseudo-terminal pair"""
        self.master_fd, self.slave_fd = pty.openpty()
        self.slave_name = os.ttyname(self.slave_fd)
        return self.slave_name

    def start_adb_shell(self):
        """Start ADB shell process"""
        cmd = ["adb"]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.append("shell")

        self.adb_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        return self.adb_process.poll() is None

    def bridge_loop(self):
        """Main bridge loop - forward data between PTY and ADB"""
        self.running = True

        # Set non-blocking
        os.set_blocking(self.master_fd, False)
        os.set_blocking(self.adb_process.stdout.fileno(), False)

        print(f"\n{'=' * 50}")
        print(f"ADB Shell <-> Virtual Serial Bridge")
        print(f"{'=' * 50}")
        print(f"Virtual serial port: {self.slave_name}")
        print(f"Device: {self.device_id or '(default)'}")
        print(f"{'=' * 50}")
        print(f"\nConnect your tool to: {self.slave_name}")
        print("Press Ctrl+C to stop\n")

        try:
            while self.running:
                # Wait for data from either side
                readable, _, _ = select.select(
                    [self.master_fd, self.adb_process.stdout],
                    [],
                    [],
                    0.1,
                )

                for fd in readable:
                    if fd == self.master_fd:
                        # Data from serial port -> ADB
                        try:
                            data = os.read(self.master_fd, 4096)
                            if data:
                                self.adb_process.stdin.write(data)
                                self.adb_process.stdin.flush()
                        except (OSError, BlockingIOError):
                            pass

                    elif fd == self.adb_process.stdout:
                        # Data from ADB -> serial port
                        try:
                            data = self.adb_process.stdout.read(4096)
                            if data:
                                os.write(self.master_fd, data)
                        except (OSError, BlockingIOError):
                            pass

                # Check if ADB process is still running
                if self.adb_process.poll() is not None:
                    print("\nADB shell disconnected")
                    break

        except KeyboardInterrupt:
            print("\n\nStopping bridge...")

    def stop(self):
        """Stop the bridge"""
        self.running = False

        if self.adb_process:
            self.adb_process.terminate()
            try:
                self.adb_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.adb_process.kill()

        if self.master_fd:
            os.close(self.master_fd)
        if self.slave_fd:
            os.close(self.slave_fd)

    def run(self):
        """Run the bridge"""
        # Create PTY
        pty_name = self.create_pty()
        print(f"Created virtual serial port: {pty_name}")

        # Start ADB shell
        print("Starting ADB shell...")
        if not self.start_adb_shell():
            print("Error: Failed to start ADB shell")
            self.stop()
            return False

        # Run bridge loop
        try:
            self.bridge_loop()
        finally:
            self.stop()

        return True


def main():
    parser = argparse.ArgumentParser(
        description="ADB Shell to Virtual Serial Port Bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    Start bridge with default device
  %(prog)s -s DEVICE_ID       Start bridge with specific device
  %(prog)s --list             List available ADB devices
        """,
    )
    parser.add_argument(
        "-s",
        "--serial",
        dest="device_id",
        help="ADB device serial number",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available ADB devices",
    )

    args = parser.parse_args()

    # Check platform
    if platform.system() == "Windows":
        print("Error: This script requires PTY support (Linux/macOS only)")
        print("For Windows, use com0com or similar virtual serial port driver")
        print("and manually bridge with: adb shell < COM_IN > COM_OUT")
        sys.exit(1)

    bridge = AdbSerialBridge(device_id=args.device_id)

    if args.list:
        bridge.list_devices()
        sys.exit(0)

    # Handle signals
    def signal_handler(sig, frame):
        bridge.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Check for available devices if no device specified
    if not args.device_id:
        devices = bridge.list_devices()
        available = [d for d, s in devices if s == "device"]
        if not available:
            print("\nNo available devices. Please connect a device and try again.")
            sys.exit(1)
        elif len(available) > 1:
            print(f"\nMultiple devices found. Using first one: {available[0]}")
            print("Use -s <device_id> to specify a different device.\n")
            bridge.device_id = available[0]

    # Run bridge
    if not bridge.run():
        sys.exit(1)


if __name__ == "__main__":
    main()
