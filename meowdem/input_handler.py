import re
import time
import asyncio 

class HayesATParser:
    def __init__(self, log_callback=print):
        self.command_buffer = ""
        self.command_prefix = "AT"
        self.s_registers = {}
        self.mode = "command"  # can be 'command' or 'data'
        self.last_input_time = time.time()
        self.escape_detected_time = None
        self.guard_time = 1.0  # seconds before and after +++
        self.log = log_callback
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
                    self.log(f"Guard time passed: {elapsed_time:.2f}s switching to command mode")
                    self.escape_detected_time = None  # Reset after guard time is handled
                else:
                    self.log(f"Guard time not yet passed: {elapsed_time:.2f}s")
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
                    self.log("[Escape sequence detected]")
                    self.escape_detected_time = now

            self.log(f"[DATA MODE] {char}")
            return

        self.command_buffer += char.upper()

        # TODO: Change this to assume only one character is received at a time
        while "AT" in self.command_buffer:
            at_index = self.command_buffer.find("AT")
            for end_index in range(at_index + 2, len(self.command_buffer)):
                if self.command_buffer[end_index] in ['\r', '\n']:
                    command_str = self.command_buffer[at_index:end_index]
                    self.execute_command(command_str)
                    self.command_buffer = self.command_buffer[end_index + 1:]
                    self.log(f"[COMMAND BUFFER] {self.command_buffer}")
                    break
            else:
                break

    def execute_command(self, command: str):
        self.log(f"[Executing] {command}")
        if not command.startswith("AT"):
            self.log("ERROR: Invalid command prefix")
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
                self.log(f"ERROR: Unknown subcommand at: '{command_body[pos:]}'")
                break
        else:
            self.log("OK")

    # === Handlers ===
    def handle_ATZ(self, *args):
        self.log("Resetting modem...")

    def handle_ATI(self, *args):
        self.log("Modem Info: Python Virtual Modem v1.0")

    def handle_ats_set(self, reg, value):
        self.s_registers[int(reg)] = int(value)
        self.log(f"Set S{reg} = {value}")

    def handle_amp_command(self, letter, value):
        self.log(f"Set &{letter} = {value}")

    def handle_pct_command(self, letter, value):
        self.log(f"Set %{letter} = {value}")

    def handle_ATD(self, number):
        self.log(f"Dialing {number}...")
        self.mode = "data"
        self.log("[Modem switched to DATA mode]")
