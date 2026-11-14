#!/usr/bin/env bash

set -euo pipefail

INSTALL_DIR="$HOME/.local/share/lerobot"
LAUNCHER="$HOME/.local/bin/lerobot"

echo "========================================"
echo " LeRobot Host Uninstallation"
echo "========================================"

read -r -p "Remove LeRobot TUI installation? [y/N]: " CONFIRM

if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

# Remove launcher
if [[ -f "$LAUNCHER" ]]; then
    echo "Removing launcher..."
    rm -f "$LAUNCHER"
fi

# Remove virtual environment
if [[ -d "$INSTALL_DIR" ]]; then
    echo "Removing Python virtual environment..."
    rm -rf "$INSTALL_DIR"
fi

echo ""
echo "LeRobot TUI successfully uninstalled."
echo ""
echo "The following components were preserved:"
echo "  - Docker"
echo "  - Docker Compose"
echo "  - Python system packages"
echo "  - LeRobot source code"
echo ""
