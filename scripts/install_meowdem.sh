AMBER='\033[38;2;255;191;0m'
RESET='\033[0m'

echo ${AMBER}"
cat << "EOF"
    /\_/\                                                                    
   ( o.o )   
    > ^ < 
MiSTer Meowdem! 
EOF
echo "${RESET}"

echo -e "Downloading Meowdem Scripts..."

MEOWDEM_ENABLE_SOURCE="https://raw.githubusercontent.com/dankreek/meowdem/refs/heads/main/scripts/MiSTer_enable_meowdem.sh"
MEOWDEM_DISABLE_SOURCE="https://raw.githubusercontent.com/dankreek/meowdem/refs/heads/main/scripts/MiSTer_disable_meowdem.sh"
MISTER_SCRIPTS_DIR="/media/fat/Scripts"

echo "Downloading Meowdem firmware to ${MISTER_SCRIPTS_DIR}"

if ! curl -fsSkL "$MEOWDEM_ENABLE_SOURCE" -o "$MISTER_SCRIPTS_DIR/MiSTer_enable_meowdem.sh"; then
  echo "Error: Failed to download MiSTer_enable_meowdem.sh from $MEOWDEM_ENABLE_SOURCE" >&2
  exit 1
fi

if ! curl -fsSkL "$MEOWDEM_DISABLE_SOURCE" -o "$MISTER_SCRIPTS_DIR/MiSTer_disable_meowdem.sh"; then
  echo "Error: Failed to download MiSTer_disable_meowdem.sh from $MEOWDEM_DISABLE_SOURCE" >&2
  exit 1
fi
