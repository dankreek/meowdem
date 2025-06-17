# Meowdem
<img src="doc/meowdem-logo.png" alt="Meowdem Logo" width="200">

A Hayes-compatible software modem emulator for really weird nerds. Meowdem emulates a classic modem interface, supporting AT commands, TCP connections, and Telnet protocol translation. It is written in Python and is intended for use on the [MiSTer FPGA](https://misterfpga.org/) as a more fully featured alternative to its the standard modem emulation.

## Features

- Hayes AT command set emulation
- TCP client support (connect to remote hosts as a modem would)
- Telnet protocol translation (optional)
- Phonebook for quick dialing
- Command and data modes, including escape sequence handling
- Works via stdin/stdout or as a TCP server

## Requirements

- Python 3.4 or newer
- [uv](https://github.com/astral-sh/uv) (for running and testing, optional but recommended)

## Installation

Clone the repository:

```zsh
# Clone the repository
 git clone https://github.com/dankreek/meowdem.git
 cd meowdem
```

## Quick Install with curl

You can install Meowdem using the provided install script directly from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/dankreek/meowdem/main/scripts/install_meowdem.sh | sh
```

This command downloads and executes the latest install script. Review the script before running for security best practices.

## Usage

You can run Meowdem in several modes, using command line options:

### Command Line Options

```
python meowdem.py [options]
```

- `-c`, `--tcp-client-port <PORT>`: Listen for incoming TCP client connections on the specified port (e.g., 2323). If omitted, only stdin/stdout mode is used.
- `-s`, `--serial-port <DEVICE>`: Attach to a serial port device (e.g., `/dev/ttyS0`). If specified, Meowdem will use this serial port as a client interface.
- `--serial-baud <BAUD>`, `-b <BAUD>`: Set the baud rate for the serial port (default: 9600). Only used if `--serial-port` is specified.

### 1. Stdin/Stdout Mode

```zsh
python meowdem.py
```

This will start the modem emulator using your terminal for input and output.

### 2. TCP Server Mode

Listen for incoming TCP client connections (e.g., from a terminal program or telnet client):

```zsh
python meowdem.py -c 2323
```

This will listen on TCP port 2323 for incoming connections.

### 3. Serial Port Mode

Connect to a serial port device (e.g., for use with hardware):

```zsh
python meowdem.py -s /dev/ttyS0 --serial-baud 19200
```

This will use `/dev/ttyS0` at 19200 baud as the modem interface.

## Supported AT Commands

- `ATZ` — Reset modem
- `ATI` — Modem info
- `ATS<n>=<v>` — Set S-register n to value v
- `ATS<n>?` — Query S-register n
- `ATDT<host>:<port>` — Dial (tone) host:port
- `ATDP<host>:<port>` — Dial (pulse) host:port
- `ATD<host>:<port>` — Dial host:port
- `ATH` — Hang up
- `ATO` — Return to data mode
- `ATE0/1/?` — Echo off/on/query
- `AT*T0/1` — Telnet translation off/on
- `AT?` — Show help
- `AT&Z<n>=host[:port]` — Set phonebook entry
- `AT&Z<n>?` — Query phonebook entry

## Testing

To run the unit tests:

Create a virtual environment and install test dependencies:

```zsh
uv venv
uv sync
```

Execute tests:

```zsh
uv run pytest -v
```

## License

This project is licensed under the GNU General Public License v3.0. See the LICENSE file for details.

## Author

Justin May (<may.justin@gmail.com>)
