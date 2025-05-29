import asyncio
import logging
import re
import sys
import termios
import time
import tty
import argparse

from copy import deepcopy
from enum import Enum
from typing import AsyncGenerator, Callable, Optional, Tuple, Callable

# Setup logging to output to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    stream=sys.stderr
)

# Timeout constant
DEFAULT_CONNECTION_TIMEOUT = 30  # Timeout in seconds
ESCAPE_GUARD_TIME = 1.0  # Seconds to wait before switching back to command mode after '+++'

class TelnetState(Enum):
    DATA = 'DATA'
    IAC = 'IAC'
    IAC_OPTION = 'IAC_OPTION'
    SB = 'SB'
    SB_IAC = 'SB_IAC'

    # Telnet protocol constants
    IAC_BYTE = 255
    SB_BYTE = 250
    SE_BYTE = 240

class TelnetTranslator:
    """
    Telnet protocol translator for handling input and output data.
    This class is responsible for translating between raw byte data and
    Telnet protocol commands.
    """
    def __init__(self):
        self.state: TelnetState = TelnetState.DATA
        self.subnegotiation: bool = False

    def input_translation(self, bytes_chunk: bytes) -> bytes:
        """
        Decode Telnet protocol input from a chunk of bytes.
        """
        WILL = 251
        WONT = 252
        DO = 253
        DONT = 254

        output = bytearray()
        for byte in bytes_chunk:
            if self.state == TelnetState.DATA:
                if byte == TelnetState.IAC_BYTE.value:
                    self.state = TelnetState.IAC
                else:
                    output.append(byte)  # Normal data byte

            elif self.state == TelnetState.IAC:
                if byte == TelnetState.IAC_BYTE.value:
                    output.append(TelnetState.IAC_BYTE.value)  # Escaped 0xFF
                    self.state = TelnetState.DATA
                elif byte in (WILL, WONT, DO, DONT):
                    self.state = TelnetState.IAC_OPTION
                elif byte == TelnetState.SB_BYTE.value:
                    self.state = TelnetState.SB
                    self.subnegotiation = True
                else:
                    # Simple command, no option
                    self.state = TelnetState.DATA

            elif self.state == TelnetState.IAC_OPTION:
                # Skip option byte
                self.state = TelnetState.DATA

            elif self.state == TelnetState.SB:
                if byte == TelnetState.IAC_BYTE.value:
                    self.state = TelnetState.SB_IAC

            elif self.state == TelnetState.SB_IAC:
                if byte == TelnetState.IAC_BYTE.value:
                    self.state = TelnetState.SB
                elif byte == TelnetState.SE_BYTE.value:
                    self.subnegotiation = False
                    self.state = TelnetState.DATA
                else:
                    # Unexpected — discard SB
                    self.state = TelnetState.DATA

        return bytes(output)

    def output_translation(self, bytes_chunk: bytes) -> bytes:
        """
        Encode data into Telnet protocol format.

        :param bytes_chunk: The chunk of bytes to encode.
        :return: The Telnet encoded bytes.
        """
        output = bytearray()
        for byte in bytes_chunk:
            if byte == TelnetState.IAC_BYTE.value:
                # Escape IAC byte and append immediately
                output.extend([TelnetState.IAC_BYTE.value, TelnetState.IAC_BYTE.value])
            else:
                # Append the single byte immediately
                output.append(byte)
        return bytes(output)

#### AT Command Parser ####

class ParserMode(Enum):
    COMMAND = 'command'
    DATA = 'data'
    DIALING = 'dialing'  # New mode state

class HayesATParser:
    def __init__(self, client_output_cb: Callable[[bytes], None] = print):
        self.command_buffer: str = ''
        self.command_prefix = 'AT'
        self.mode = ParserMode.COMMAND  

        self.writer: Optional[asyncio.StreamWriter] = None  # Stores the writer, None if no connection is open
        self.dialing_task: Optional[asyncio.Task] = None  # Task that runs while dialing

        self.telnet_translator = TelnetTranslator()
        self.phonebook: dict[str, tuple[str, Optional[int]]] = {}  

        # Variables to handle escape from DATA to COMMAND mode
        self.escape_detected_time: Optional[float] = None
        self.escape_guard_time = ESCAPE_GUARD_TIME  # Use the constant here
        self.client_out_cb = client_output_cb  # Callback for client output binary data
        self.guard_time_task = asyncio.create_task(self._monitor_guard_time())
        
        # Modem state variables
        self.s_registers = {}
        self.telnet_translation_enabled: bool = False
        self.echo_enabled = True

        self.subcommand_handlers = [
            (r'^Z', self.handle_ATZ),
            (r'^I', self.handle_ATI),
            (r'^S(\d+)=(\d+)', self.handle_ats_set),
            (r'^S(\d+)\?', self.handle_ats_query),
            (r'^&Z([\w-]+)=([^\r\n]*)', self.handle_AT_amp_Z),
            (r'^&Z([\w-]+)\?', self.handle_AT_amp_Z_query),
            (r'^&Z\?', lambda: self.handle_AT_amp_Z_query('0')),
            (r'^&([A-Z])(\d+)', self.handle_amp_command),
            (r'^%([A-Z])(\d+)', self.handle_pct_command),
            (r'^D[T|P](.+)', self.handle_ATD),
            (r'^D(.+)', self.handle_ATD),
            (r'^H(0)?', self.handle_ATH),
            (r'^O', self.handle_ATO),
            (r'^E(0|1|\?)', self.handle_ATE),
            (r'^\*T(0|1)', self.handle_AT_star_T),
            (r'^\?', self.handle_ATQMARK),
        ]

    def client_out_str(self, data: str):
        """Send data to the client using the provided callback translating the string to bytes."""
        self.client_out_cb(data.encode('latin1'))  # Send the data as raw binary

    async def _monitor_guard_time(self):
        """Background task to monitor if the guard time has passed."""
        while True:
            if self.escape_detected_time is not None:
                elapsed_time = time.time() - self.escape_detected_time
                if elapsed_time >= ESCAPE_GUARD_TIME:  
                    self.mode = ParserMode.COMMAND  # Switch back to command mode
                    self.client_out_str('OK\r\n')
                    self.escape_detected_time = None  # Reset after guard time is handled

            await asyncio.sleep(0.1)  # Check every 100ms

    def receive(self, data: bytes):
        if self.telnet_translation_enabled:
            data = self.telnet_translator.input_translation(data)

        if self.mode == ParserMode.DIALING:
            if self.dialing_task and not self.dialing_task.done():
                self.dialing_task.cancel()  # Cancel the dialing operation
                self.client_out_str('NO CARRIER\r\n')
                self.mode = ParserMode.COMMAND
            return 

        for byte in data:
            char = chr(byte).upper()
            self._receive_char(byte)

    def _receive_char(self, byte: int):
        char = chr(byte)
        if self.mode == ParserMode.DATA:
            if self.writer and not self.writer.is_closing():
                try:
                    self.writer.write(bytes([byte]))  # Send the byte as raw binary
                    asyncio.create_task(self.writer.drain())  # Ensure the data is sent
                except Exception as e:
                    self.client_out_str(f"ERROR: Failed to send data: {str(e)}\r\n")

            if self.command_buffer == '+++':
                self.escape_detected_time = None
                self.command_buffer = ''
            elif '+' in self.command_buffer and char != '+':
                self.command_buffer = ''    

            # Look for a full escape sequence of '+++'
            if char == '+':
                self.command_buffer += char
                if self.command_buffer == '+++':
                    self.escape_detected_time = time.time()

            return

        # Handle backspace with echo as delete
        if char in ['\x7f', '\b']:
            if self.echo_enabled:
                self.client_out_str('\b \b') 
            self.command_buffer = self.command_buffer[:-1]
            return

        next_char = char.upper()
        self.command_buffer += next_char

        if self.echo_enabled:
            self.client_out_str(next_char)

        while "AT" in self.command_buffer:
            at_index = self.command_buffer.find('AT')
            for end_index in range(at_index + 2, len(self.command_buffer)):
                if self.command_buffer[end_index] in ['\r', '\n']:
                    command_str = self.command_buffer[at_index:end_index]
                    if self.echo_enabled:
                        self.client_out_str('\n')

                    self.execute_command(command_str)
                    self.command_buffer = self.command_buffer[end_index + 1:]
                    break
            else:
                break

    def execute_command(self, command: str):
        """ Execute a parsed AT command.  """
        # Remove spaces between 'AT' and the rest of the command for compatibility
        if command.startswith('AT'):
            command = 'AT' + command[2:].lstrip()
        else:
            self.client_out_str('ERROR: Invalid command prefix\r\n')
            return

        command_body = command[2:]
        pos = 0
        while pos < len(command_body):
            matched = False
            for pattern, handler in self.subcommand_handlers:
                match = re.match(pattern, command_body[pos:])
                if match:
                    handler(*match.groups())
                    pos += match.end()
                    matched = True
                    break
            if not matched:
                if command_body[pos] in ['Z', '&', '%', 'S', 'D', 'H', 'O']:
                    pos += 1  # Skip unsupported commands without arguments
                else:
                    self.client_out_str(f"ERROR: Unknown subcommand at: '{command_body[pos:]}'\r\n")
                    break
        else:
            if self.mode == ParserMode.COMMAND:
                self.client_out_str('OK\r\n')

    # === Handlers ===
    def handle_ATZ(self, *args):
        self.echo_enabled = True
        self.s_registers = {}
        self.telnet_translation_enabled = False

    def handle_ATI(self, *args):
        self.client_out_str('Modem Info: Python Virtual Modem v1.0\r\n')
        self.client_out_str(f"Echo enabled: {self.echo_enabled}\r\n") 
        self.client_out_str(f"Telnet translation enabled: {self.telnet_translation_enabled}\r\n")

    def handle_ats_set(self, reg, value):
        self.s_registers[int(reg)] = int(value)

    def handle_ats_query(self, reg: str):
        """ Handler for querying an S-register value. """
        reg_num = int(reg)
        value = self.s_registers.get(reg_num, 0)  # Default to 0 if not set
        self.client_out_str(f"{value}\r\n")

    def handle_amp_command(self, letter, value):
        pass

    def handle_pct_command(self, letter, value):
        pass

    def handle_ATH(self, *args):
        """Handler for the ATH command to hang up an open connection."""
        if self.writer and not self.writer.is_closing():
            self.writer.close()
            asyncio.create_task(self.writer.wait_closed())
            self.writer = None
            self.client_out_str('NO CARRIER\r\n')
        self.mode = ParserMode.COMMAND

    def handle_ATO(self, *args):
        """Handler for the ATO command to return to DATA mode."""
        if self.writer and not self.writer.is_closing():
            self.mode = ParserMode.DATA
            self.client_out_str('CONNECT\r\n')
        else:
            self.client_out_str('NO CARRIER\r\n')

    def handle_ATE(self, value: str):
        """Handler for the ATE command to toggle or query echo mode."""
        if value == '0':
            self.echo_enabled = False
            self.client_out_str('OK\r\n')
        elif value == '1':
            self.echo_enabled = True
            self.client_out_str('OK\r\n')
        elif value == '?':
            echo_status = '1' if getattr(self, 'echo_enabled', True) else '0'
            self.client_out_str(f"{echo_status}\r\n")
        else:
            self.client_out_str('ERROR\r\n')

    def handle_AT_star_T(self, value: str):
        """Handler for the custom AT*T command to toggle telnet translation."""
        if value == '1':
            self.telnet_translation_enabled = True
        elif value == '0':
            self.telnet_translation_enabled = False
        else:
            self.client_out_str('ERROR\r\n')

    def handle_ATQMARK(self, *args):
        """ Handler for the AT? command to display help text. """
        help_text = (
            'Hayes AT Command Help:\r\n'
            'ATZ            - Reset modem\r\n'
            'ATI            - Modem info\r\n'
            'ATS<n>=<v>     - Set S-register n to value v\r\n'
            'ATS<n>?        - Query S-register n\r\n'
            'ATDT<addr>     - Dial (tone) <host>:<port>\r\n'
            'ATDP<addr>     - Dial (pulse) <host>:<port>\r\n'
            'ATD<addr>      - Dial <host>:<port>\r\n'
            'ATH            - Hang up\r\n'
            'ATO            - Return to data mode\r\n'
            'ATE0/1/?       - Echo off/on/query\r\n'
            'AT*T0/1        - Telnet translation off/on\r\n'
            'AT?            - This help\r\n'
        )
        self.client_out_str(help_text)

    def handle_AT_amp_Z(self, entry_num: str, address: str) -> None:
        """ Handler for the AT&Z<n>=host[:port] command to add or remove a phonebook entry. Port is optional. If no address is given, remove the entry. """
        key: str = entry_num
        address = address.strip()
        if not address:
            # Remove entry if address is empty
            if key in self.phonebook:
                del self.phonebook[key]
                self.client_out_str('DELETED\r\n')
            else:
                self.client_out_str('NOT SET\r\n')
            return
        # Accept host or host:port
        if ':' in address:
            host, port = self._parse_address(address)
            if host is None:
                self.client_out_str('ERROR: INVALID ADDRESS. USE THE FORM <HOST>[:<PORT>]\r\n')
                return
            self.phonebook[key] = (host, port)
        else:
            # Only host provided, store with default port 23
            host = address
            if not host:
                self.client_out_str('ERROR: INVALID ADDRESS. USE THE FORM <HOST>[:<PORT>]\r\n')
                return
            self.phonebook[key] = (host, None)

    # Add handler for AT&Z<n>? query
    def handle_AT_amp_Z_query(self, entry_num: str) -> None:
        """ Handler for the AT&Z<n>? command to query a phonebook entry, or list all if no key is provided. """
        if entry_num == '0':
            if not self.phonebook:
                self.client_out_str('NO ENTRIES\r\n')
                return
            for key, (host, port) in self.phonebook.items():
                if port is not None:
                    self.client_out_str(f'{key}: {host}:{port}\r\n')
                else:
                    self.client_out_str(f'{key}: {host}\r\n')
            return
        key: str = entry_num
        entry = self.phonebook.get(key)
        if entry:
            host, port = entry
            if port is not None:
                self.client_out_str(f'{host}:{port}\r\n')
            else:
                self.client_out_str(f'{host}\r\n')
        else:
            self.client_out_str('NOT SET\r\n')

    @staticmethod
    def _parse_address(address: str, default_port: int = 23) -> Tuple[Optional[str], Optional[int]]:
        pattern = re.compile(
            r'\b(?P<host>(?:\d{1,3}\.){3}\d{1,3}|(?:[a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+)(?::(?P<port>\d{1,5}))?\b'
        )

        match = pattern.search(address.strip())
        if match:
            host: str = match.group('host')
            port: int = int(match.group('port')) if match.group('port') else default_port
            return host, port

        return None, None

    async def _handle_socket_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """ Coroutine to read from the socket and send raw data back via client_out. """
        self.writer = writer  # Set the writer when the connection is open
        try:
            while True:
                data = await reader.read(1024)  # Read up to 1024 bytes
                if not data:
                    break  # Connection closed

                if self.telnet_translation_enabled:
                    translated = self.telnet_translator.input_translation(data)
                    self.client_out_cb(translated)
                else:
                    self.client_out_cb(data)  # Output data in latin1 encoding
        except Exception as e:
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            self.writer = None  # Reset the writer when the connection is closed

    def handle_ATD(self, number: str):
        host, port = HayesATParser._parse_address(number)

        if host is None:
            self.client_out_str('INVALID ADDRESS. USE THE FORM <HOSTNAME>:<PORT>\r\n')
            return

        self.client_out_str(f"DIALING {host}:{port}...\r\n")
        self.mode = ParserMode.DIALING  # Set mode to DIALING

        async def connect():
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=DEFAULT_CONNECTION_TIMEOUT
                )
                self.client_out_str('CONNECTED\r\n')
                self.mode = ParserMode.DATA
                await self._handle_socket_connection(reader, writer)
            except Exception as e:
                self.client_out_str('NO CARRIER\r\n')
                self.writer = None  # Ensure writer is reset on error
                self.mode = ParserMode.COMMAND

        self.dialing_task = asyncio.create_task(connect())


#### Main ####

async def handle_tcp_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """ Async handler for each TCP client using HayesATParser. 
    :param reader: StreamReader for the client.
    :param writer: StreamWriter for the client.
    :return: None
    """
    def tcp_client_out(data: bytes) -> None:
        """ Output function for HayesATParser to send data to TCP client. 
        :param data: Data to send.
        :return: None
        """
        writer.write(data)
        # Schedule drain asynchronously
        asyncio.create_task(writer.drain())

    logging.info('Connection is connected')

    parser = HayesATParser(tcp_client_out)
    try:
        while True:
            data = await reader.read(1024)
            if not data:
                break
            parser.receive(data)
    except Exception:
        pass
    finally:
        writer.close()
        await writer.wait_closed()


def stdio_client_task() -> asyncio.Task:
    """ Start the stdin processing loop as a background task. 
    :return: The asyncio Task handling stdin.
    """
    def send_to_stdout(data: bytes) -> None:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()

    async def read_from_stdin(parser: HayesATParser) -> None:
        loop = asyncio.get_running_loop()
        while True:
            data = await loop.run_in_executor(None, sys.stdin.buffer.read, 1)
            if not data:
                break
            parser.receive(data)

    parser = HayesATParser(send_to_stdout)
    return asyncio.create_task(read_from_stdin(parser))


def tcp_client_task(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> asyncio.Task:
    """ Return an asyncio Task for handling a TCP client. 
    :param reader: StreamReader for the client.
    :param writer: StreamWriter for the client.
    :return: The asyncio Task handling the client.
    """
    return asyncio.create_task(handle_tcp_client(reader, writer))


def serial_client_task(serial_port_path: str, baudrate: int = 9600) -> asyncio.Task:
    """ Start the serial port processing loop as a background task. 
    :param serial_port_path: Path to the serial port device (e.g., /dev/ttyS0).
    :param baudrate: Baud rate for the serial port.
    :return: The asyncio Task handling the serial port.
    """
    import os
    import fcntl
    import termios
    serial_fd = os.open(serial_port_path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    # Set serial port to raw mode and baud rate
    attrs = termios.tcgetattr(serial_fd)
    tty.setraw(serial_fd)
    # Set input and output baud rate (Linux only, using termios attribute indices)
    # termios.ISPEED and OSPEED are indices 4 and 5 in attrs
    import termios
    BAUD_RATES = {
        0: termios.B0,
        50: termios.B50,
        75: termios.B75,
        110: termios.B110,
        134: termios.B134,
        150: termios.B150,
        200: termios.B200,
        300: termios.B300,
        600: termios.B600,
        1200: termios.B1200,
        1800: termios.B1800,
        2400: termios.B2400,
        4800: termios.B4800,
        9600: termios.B9600,
        19200: termios.B19200,
        38400: termios.B38400,
        57600: termios.B57600,
        115200: termios.B115200,
        230400: termios.B230400,
    }
    baud_const = BAUD_RATES.get(baudrate, termios.B9600)
    attrs[4] = baud_const  # ISPEED
    attrs[5] = baud_const  # OSPEED

    # Enable hardware flow control (CRTSCTS)
    if hasattr(termios, 'CRTSCTS'):
        attrs[2] |= termios.CRTSCTS

    # Turn echo off (disable ECHO flag)
    if hasattr(termios, 'ECHO'):
        attrs[3] &= ~termios.ECHO

    # Turn off input and output buffering (set VMIN=1, VTIME=0)
    if hasattr(termios, 'VMIN') and hasattr(termios, 'VTIME'):
        attrs[6][termios.VMIN] = 1
        attrs[6][termios.VTIME] = 0

    termios.tcsetattr(serial_fd, termios.TCSANOW, attrs)

    # Set the CTS modem bit high after enabling hardware flow control
    if hasattr(termios, 'TIOCM_CTS') and hasattr(termios, 'TIOCMBIS'):
        import struct
        fcntl.ioctl(serial_fd, termios.TIOCMBIS, struct.pack('I', termios.TIOCM_CTS))

    def send_to_serial(data: bytes) -> None:
        os.write(serial_fd, data)

    async def read_from_serial(parser: HayesATParser) -> None:
        loop = asyncio.get_running_loop()
        while True:
            data = await loop.run_in_executor(None, os.read, serial_fd, 1)
            if not data:
                break
            parser.receive(data)

    parser_serial = HayesATParser(send_to_serial)
    return asyncio.create_task(read_from_serial(parser_serial))


async def main() -> None:
    """ Main entry point: handles both stdin and TCP connections. 
    :return: None
    """
    parser = argparse.ArgumentParser(
        description='Meowdem: A Hayes-compatible modem emulator supporting AT commands, TCP, and Telnet translation.',
        epilog='Example usage: python meowdem.py -c 2323.'
    )
    parser.add_argument(
        '-c', '--tcp-client-port',
        type=int,
        default=None,
        help='Port to listen for TCP client connections (optional, e.g., 2323). If omitted, only stdin is used.'
    )
    parser.add_argument(
        '-s', '--serial-port',
        type=str,
        default=None,
        help='Serial port device to attach to (e.g., /dev/ttyS0). If specified, meowdem will use this serial port as a client interface.'
    )
    parser.add_argument(
        '--serial-baud',
        '-b',
        type=int,
        default=9600,
        help='Baud rate for the serial port (default: 9600). Only used if --serial-port is specified.'
    )
    args = parser.parse_args()

    tasks = []
    if args.serial_port is not None:
        tasks.append(serial_client_task(args.serial_port, args.serial_baud))
    else:
        tasks.append(stdio_client_task())

    if args.tcp_client_port is not None:
        server = await asyncio.start_server(handle_tcp_client, '0.0.0.0', args.tcp_client_port)
        tasks.append(server.serve_forever())
        async with server:
            await asyncio.gather(*tasks)
    else:
        await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())