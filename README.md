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

Create a virtual environment and install test dependencies:

```zsh
uv venv
uv sync
```

## Usage

You can run Meowdem in two modes:

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

```zsh
uv run pytest -v
```

## License

This project is licensed under the GNU General Public License v3.0. See the LICENSE file for details.

## Author

Justin May (<may.justin@gmail.com>)
