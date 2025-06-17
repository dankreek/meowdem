#!/usr/bin/env bash
export UARTMODE_SOURCE=https://raw.githubusercontent.com/bbond007/MiSTer_MidiLink/refs/heads/master/uartmode
export SCRATCH_DIR="${SCRATCH_DIR:-./scratch}"
export UARTMODE=$SCRATCH_DIR/uartmode
export MEOWDEM_FIRMWARE_DEST="${SCRATCH_DIR:-./scratch}/meowdem.py"

mkdir -p "$SCRATCH_DIR"

if ! command -v wget >/dev/null 2>&1; then
    echo "Error: wget is not installed. Please install wget first."
    exit 1
fi

mkdir -p "$SCRATCH_DIR"
wget "$UARTMODE_SOURCE" -O "$UARTMODE" || {
    echo "Error: Failed to download uartmode script."
    exit 1
}

./MiSTer_enable_meowdem.sh || {
    echo "Error: Failed to enable Meowdem."
    exit 1
}



