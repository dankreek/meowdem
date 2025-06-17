GREEN='\e[0;92m'
RESET='\e[0m'

echo "${GREEN}"
cat << "EOF"
    /\_/\                                                                    
   ( o.o )   
    > ^ < 
MiSTer Meowdem! 
EOF
echo "${RESET}"

echo "Enabling Meowdem..."

MEOWDEM_FIRMWARE_SOURCE="https://raw.githubusercontent.com/dankreek/meowdem/refs/heads/main/meowdem.py"
MEOWDEM_FIRMWARE_DEST="${MEOWDEM_FIRMWARE_DEST:-/media/fat/linux/meowdem.py}"
echo "Downloading Meowdem firmware to ${MEOWDEM_FIRMWARE_DEST}..."
curl -fsSkL "$MEOWDEM_FIRMWARE_SOURCE" -o "$MEOWDEM_FIRMWARE_DEST"


UARTMODE="${UARTMODE:-/usr/sbin/uartmode}"
if [ ! -f "$UARTMODE" ]; then
    echo "Error: $UARTMODE not found. Please install midilink first."
    exit 1
fi

sed -i "/killall mpg123/a\	ps aux | grep '[m]eowdem.py' | awk '{print \$1}' | xargs -r kill" "$UARTMODE"

sed -i '/echo "1" >\/tmp\/uartmode4/,/wait \$!/s/midilink MENU QUIET/python \/media\/fat\/linux\/meowdem.py -s \/dev\/ttyS1 -b \$conn_speed/' "$UARTMODE"
