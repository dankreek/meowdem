import re
import time

class HayesATParser:
    def __init__(self, log_callback=print):
        self.buffer = ""
        self.command_prefix = "AT"
        self.s_registers = {}
        self.mode = "command"  # can be 'command' or 'data'
        self.last_input_time = time.time()
        self.escape_detected_time = None
        self.guard_time = 1.0  # seconds before and after +++
        self.log = log_callback

        self.subcommand_handlers = [
            (r'^Z', self.handle_ATZ),
            (r'^I', self.handle_ATI),
            (r'^S(\d+)=(\d+)', self.handle_ats_set),
            (r'^&([A-Z])(\d+)', self.handle_amp_command),
            (r'^%([A-Z])(\d+)', self.handle_pct_command),
            (r'^D(.+)', self.handle_ATD),
        ]

    def receive(self, data: str):
        now = time.time()

        if data == "+++":
            if now - self.last_input_time > self.guard_time:
                self.mode = "command"
                self.log("[Modem switched to COMMAND mode]")
                self.buffer = ""
                self.escape_detected_time = now
            else:
                self.log("[Ignored '+++' - failed guard time check]")
            self.last_input_time = now
            return

        self.last_input_time = now

        if self.mode == "data":
            self.log(f"[DATA MODE] {data}")
            return

        self.buffer += data.upper()

        while "AT" in self.buffer:
            at_index = self.buffer.find("AT")
            for end_index in range(at_index + 2, len(self.buffer)):
                if self.buffer[end_index] in ['\r', '\n']:
                    command_str = self.buffer[at_index:end_index]
                    self.execute_command(command_str)
                    self.buffer = self.buffer[end_index + 1:]
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
