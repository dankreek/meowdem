#!/usr/bin/env bash
export SCRATCH_DIR="${SCRATCH_DIR:-./scratch}"
export UARTMODE="$SCRATCH_DIR/uartmode"
export MEOWDEM_FIRMWARE_DEST="$SCRATCH_DIR/meowdem.py"

mkdir -p "$SCRATCH_DIR"

./MiSTer_disable_meowdem.sh || {
    echo "Error: Failed to disble Meowdem."
    exit 1
}
