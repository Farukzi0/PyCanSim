#!/usr/bin/env bash
# PyCanSim Launcher Script
# Creates vcan0 only if missing, and removes it on exit when this session created it.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

CREATED_VCAN=0

setup_vcan() {
    if ip link show vcan0 &>/dev/null; then
        echo "[+] vcan0 already exists — leaving it for other tools."
        return 0
    fi

    echo "[+] Setting up SocketCAN vcan0 for this session..."
    if command -v pkexec &>/dev/null; then
        pkexec sh -c "modprobe vcan && ip link add dev vcan0 type vcan && ip link set up vcan0" 2>/dev/null || true
    elif command -v sudo &>/dev/null; then
        sudo modprobe vcan 2>/dev/null || true
        sudo ip link add dev vcan0 type vcan 2>/dev/null || true
        sudo ip link set up vcan0 2>/dev/null || true
    fi

    if ip link show vcan0 &>/dev/null; then
        CREATED_VCAN=1
        echo "[+] vcan0 is up (removed automatically when PyCanSim exits)."
    fi
}

remove_vcan() {
    ip link show vcan0 &>/dev/null || return 0
    echo "[+] Removing session vcan0..."

    if ip link delete vcan0 2>/dev/null; then
        echo "[+] vcan0 removed."
        return 0
    fi
    if command -v sudo &>/dev/null && sudo -n ip link delete vcan0 2>/dev/null; then
        echo "[+] vcan0 removed."
        return 0
    fi
    if command -v pkexec &>/dev/null; then
        pkexec ip link delete vcan0 2>/dev/null || true
    elif command -v sudo &>/dev/null; then
        sudo ip link delete vcan0 2>/dev/null || true
    fi

    if ip link show vcan0 &>/dev/null; then
        echo "[!] Could not delete vcan0. Remove with: sudo ip link delete vcan0"
    else
        echo "[+] vcan0 removed."
    fi
}

cleanup() {
    if [[ "$CREATED_VCAN" -eq 1 ]]; then
        remove_vcan
    fi
}

trap cleanup EXIT INT TERM HUP

setup_vcan

if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    "$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/pycansim/main.py"
else
    python3 "$SCRIPT_DIR/pycansim/main.py"
fi
