echo "\033[0;32m"
cat << "EOF"
    /\_/\                                                                    
   ( o.o )   
    > ^ < 
MiSTer Meowdem! 
EOF
echo "\033[0m"

echo "Downloading Meowdem Scripts..."

MEOWDEM_ENABLE_SOURCE="https://raw.githubusercontent.com/dankreek/meowdem/refs/heads/main/scripts/MiSTer_enable_meowdem.sh"
MEOWDEM_DISABLE_SOURCE="https://raw.githubusercontent.com/dankreek/meowdem/refs/heads/main/scripts/MiSTer_disable_meowdem.sh"
MISTER_SCRIPTS_DIR="/media/fat/linux/scripts"

echo "Downloading Meowdem firmware to ${MISTER_SCRIPTS_DIR}"

if ! curl -fsSkL "$MEOWDEM_ENABLE_SOURCE" -o "$MISTER_SCRIPTS_DIR/MiSTer_enable_meowdem.sh"; then
  echo "Error: Failed to download MiSTer_enable_meowdem.sh from $MEOWDEM_ENABLE_SOURCE" >&2
  exit 1
fi

if ! curl -fsSkL "$MEOWDEM_DISABLE_SOURCE" -o "$MISTER_SCRIPTS_DIR/MiSTer_disable_meowdem.sh"; then
  echo "Error: Failed to download MiSTer_disable_meowdem.sh from $MEOWDEM_DISABLE_SOURCE" >&2
  exit 1
fi
