#!/bin/sh
set -e

SCRIPT_PATH=$(readlink -f "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")

sudo apt update
cat "$SCRIPT_DIR/prerequisites-apt.txt" | xargs sudo apt install -y
