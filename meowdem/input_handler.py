import re
import time
import asyncio
from typing import Optional, Tuple 

class HayesATParser:
    def __init__(self, client_output_cb=print):
        self.command_buffer = ""
        self.command_prefix = "AT"
        self.s_registers = {}
        self.mode = "command"  # can be 'command' or 'data'
        self.last_input_time = time.time()
        self.escape_detected_time = None
        self.guard_time = 1.0  # Seconds to wait before switching back to command mode after '+++'
        self.client_out = client_output_cb
        self.guard_time_task = asyncio.create_task(self._monitor_guard_time())

        self.subcommand_handlers = [
            (r'^Z', self.handle_ATZ),
            (r'^I', self.handle_ATI),
            (r'^S(\d+)=(\d+)', self.handle_ats_set),
            (r'^&([A-Z])(\d+)', self.handle_amp_command),
            (r'^%([A-Z])(\d+)', self.handle_pct_command),
            (r'^D[T|P](.+)', self.handle_ATD),
            (r'^D(.+)', self.handle_ATD),
        ]

    async def _monitor_guard_time(self):
        """Background task to monitor if the guard time has passed."""
        while True:
            if self.escape_detected_time is not None:
                elapsed_time = time.time() - self.escape_detected_time
                if elapsed_time >= self.guard_time:
                    self.mode = "command"  # Switch back to command mode
                    self.client_out("OK\r\n")
                    self.escape_detected_time = None  # Reset after guard time is handled

            await asyncio.sleep(0.1)  # Check every 100ms

    def receive(self, data: str):
        for char in data:
            self._receive_char(char)

    def _receive_char(self, char: str):
        now = time.time()
        self.last_input_time = now

        if self.mode == "data":
            if self.command_buffer == '+++':
                self.escape_detected_time = None
                self.command_buffer = ''
            elif '+' in self.command_buffer and char != '+':
                self.command_buffer = ''    

            # Look for a full escape sequence of '+++'
            if char == '+':
                self.command_buffer += char
                if self.command_buffer == '+++':
                    self.escape_detected_time = now

            return

        next_char = char.upper()
        self.command_buffer += next_char
        self.client_out(next_char)

        while "AT" in self.command_buffer:
            at_index = self.command_buffer.find("AT")
            for end_index in range(at_index + 2, len(self.command_buffer)):
                if self.command_buffer[end_index] in ['\r', '\n']:
                    command_str = self.command_buffer[at_index:end_index]
                    self.client_out("\n")
                    self.execute_command(command_str)
                    self.command_buffer = self.command_buffer[end_index + 1:]
                    break
            else:
                break

    def execute_command(self, command: str):
        if not command.startswith("AT"):
            self.client_out("ERROR: Invalid command prefix\r\n")
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
                self.client_out(f"ERROR: Unknown subcommand at: '{command_body[pos:]}'\r\n")
                break
        else:
            if self.mode == 'command':
                self.client_out("OK\r\n")

    # === Handlers ===
    def handle_ATZ(self, *args):
        pass

    def handle_ATI(self, *args):
        self.client_out("Modem Info: Python Virtual Modem v1.0\r\n")

    def handle_ats_set(self, reg, value):
        self.s_registers[int(reg)] = int(value)

    def handle_amp_command(self, letter, value):
        pass

    def handle_pct_command(self, letter, value):
        pass

    @staticmethod
    def _parse_address(address: str, default_port: int = 23) -> Tuple[Optional[str], Optional[int]]:
        pattern = re.compile(
            r'\b(?P<host>(?:\d{1,3}\.){3}\d{1,3}|(?:[a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+)(?::(?P<port>\d{1,5}))?\b'
        )

        match = pattern.search(address.strip())
        if match:
            host: str = match.group("host")
            port: int = int(match.group("port")) if match.group("port") else default_port
            return host, port

        return None, None

    def handle_ATD(self, number: str):
        host, port = HayesATParser._parse_address(number)

        if host is None:
            self.client_out('INVALID ADDRESS. USE THE FORM <HOSTNAME>:<PORT>')
            return

        self.client_out(f"Dialing {host}:{port}...\r\n")
        self.mode = "data"
