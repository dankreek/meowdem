UARTMODE=https://raw.githubusercontent.com/bbond007/MiSTer_MidiLink/refs/heads/master/uartmode
MEOWDEM_FIRMWARE_DEST="${MEOWDEM_FIRMWARE_DEST:-/media/fat/linux/meowdem.py}"

echo "Disabling Meowdem..."

if [ -f "$UARTMODE" ]; then
    echo "Restoring original uartmode script from ${UARTMODE}..."
    curl -fsSkL "$UARTMODE" -o /usr/sbin/uartmode
else
    echo "Error: $UARTMODE not found. Please check the URL or your internet connection."
    exit 1
fi

if [ -f "$MEOWDEM_FIRMWARE_DEST" ]; then
    echo "Removing Meowdem firmware from ${MEOWDEM_FIRMWARE_DEST}..."
    rm -f "$MEOWDEM_FIRMWARE_DEST"
else
    echo "No Meowdem firmware found at ${MEOWDEM_FIRMWARE_DEST}."
fi
