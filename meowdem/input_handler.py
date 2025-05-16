import re
import time
import asyncio
from typing import Optional, Tuple, Callable
from enum import Enum
from meowdem.util import TelnetTranslator

# Timeout constant
DEFAULT_CONNECTION_TIMEOUT = 30  # Timeout in seconds
ESCAPE_GUARD_TIME = 1.0  # Seconds to wait before switching back to command mode after '+++'

class ParserMode(Enum):
    COMMAND = 'command'
    DATA = 'data'
    DIALING = 'dialing'  # New mode state

class HayesATParser:
    def __init__(self, client_output_cb: Callable[[bytes], None] = print):
        self.command_buffer: str = ''
        self.command_prefix = 'AT'
        self.mode = ParserMode.COMMAND  

        # Variables to handle escape from DATA to COMMAND mode
        self.escape_detected_time: Optional[float] = None
        self.escape_guard_time = ESCAPE_GUARD_TIME  # Use the constant here
        self.client_out_cb = client_output_cb  # Callback for client output binary data
        self.guard_time_task = asyncio.create_task(self._monitor_guard_time())
        
        self.writer: Optional[asyncio.StreamWriter] = None  # Store the writer, None if no connection is open
        self.dialing_task: Optional[asyncio.Task] = None  # Store the dialing task

        # Modem state variables
        self.s_registers = {}
        self.telnet_translation_enabled: bool = False
        self.echo_enabled = True

        self.telnet_translator = TelnetTranslator()

        self.subcommand_handlers = [
            (r'^Z', self.handle_ATZ),
            (r'^I', self.handle_ATI),
            (r'^S(\d+)=(\d+)', self.handle_ats_set),
            (r'^S(\d+)\?', self.handle_ats_query),
            (r'^&([A-Z])(\d+)', self.handle_amp_command),
            (r'^%([A-Z])(\d+)', self.handle_pct_command),
            (r'^D[T|P](.+)', self.handle_ATD),
            (r'^D(.+)', self.handle_ATD),
            (r'^H(0)?', self.handle_ATH),
            (r'^O', self.handle_ATO),
            (r'^E(0|1|\?)', self.handle_ATE),
            (r'^\*T(0|1)', self.handle_AT_star_T),
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
        if self.mode == ParserMode.DIALING:
            if self.dialing_task and not self.dialing_task.done():
                self.dialing_task.cancel()  # Cancel the dialing operation
                self.client_out_str('NO CARRIER\r\n')
                self.mode = ParserMode.COMMAND
            return 

        for byte in data:
            char = chr(byte)
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
        if not command.startswith('AT'):
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
            self.client_out_str(f"ERROR: {str(e)}\r\n")
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
            except asyncio.TimeoutError:
                self.client_out_str('NO CARRIER\r\n')
                self.writer = None  # Ensure writer is reset on error
                self.mode = ParserMode.COMMAND
            except Exception as e:
                self.client_out_str(f"\r\nERROR: {str(e)}\r\n")
                self.client_out_str('NO CARRIER\r\n')
                self.writer = None  # Ensure writer is reset on error
                self.mode = ParserMode.COMMAND

        self.dialing_task = asyncio.create_task(connect())
