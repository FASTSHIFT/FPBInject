#!/usr/bin/env python3
import serial
import time
import sys

port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyACM0'
ser = serial.Serial(port, 115200, timeout=2)
time.sleep(0.5)

# Clear buffer
ser.reset_input_buffer()

# Try different command formats
tests = [
    'fl --cmd ping',
    '--cmd ping', 
    'fl -c ping',
    '-c ping',
]

for cmd in tests:
    print(f'Testing: {cmd!r}')
    ser.write((cmd + '\n').encode())
    ser.flush()
    time.sleep(0.3)
    resp = ser.read(ser.in_waiting).decode('utf-8', errors='replace')
    print(f'Response: {resp!r}')
    print()

ser.close()
