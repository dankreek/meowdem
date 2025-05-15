from typing import Generator, Optional
from enum import Enum

class TelnetState(Enum):
    DATA = "DATA"
    IAC = "IAC"
    IAC_OPTION = "IAC_OPTION"
    SB = "SB"
    SB_IAC = "SB_IAC"

    # Telnet protocol constants
    IAC_BYTE = 255
    SB_BYTE = 250
    SE_BYTE = 240

class TelnetSession:
    def __init__(self):
        self.state: TelnetState = TelnetState.DATA
        self.subnegotiation: bool = False
        self.sb_data: list[int] = []

    def input_translation(self) -> Generator[Optional[int], int, None]:
        """
        Generator to decode Telnet protocol input.
        """
        WILL = 251
        WONT = 252
        DO = 253
        DONT = 254

        while True:
            byte: int = yield  # Receive one byte at a time

            if self.state == TelnetState.DATA:
                if byte == TelnetState.IAC_BYTE:
                    self.state = TelnetState.IAC
                else:
                    yield byte  # Normal data byte

            elif self.state == TelnetState.IAC:
                if byte == TelnetState.IAC_BYTE:
                    yield TelnetState.IAC_BYTE  # Escaped 0xFF
                    self.state = TelnetState.DATA
                elif byte in (WILL, WONT, DO, DONT):
                    self.state = TelnetState.IAC_OPTION
                elif byte == TelnetState.SB_BYTE:
                    self.state = TelnetState.SB
                    self.subnegotiation = True
                    self.sb_data = []
                else:
                    # Simple command, no option
                    self.state = TelnetState.DATA

            elif self.state == TelnetState.IAC_OPTION:
                # Skip option byte
                self.state = TelnetState.DATA

            elif self.state == TelnetState.SB:
                if byte == TelnetState.IAC_BYTE:
                    self.state = TelnetState.SB_IAC
                else:
                    self.sb_data.append(byte)

            elif self.state == TelnetState.SB_IAC:
                if byte == TelnetState.IAC_BYTE:
                    self.sb_data.append(TelnetState.IAC_BYTE)  # Escaped IAC inside SB
                    self.state = TelnetState.SB
                elif byte == TelnetState.SE_BYTE:
                    self.subnegotiation = False
                    self.sb_data = []
                    self.state = TelnetState.DATA
                else:
                    # Unexpected — discard SB
                    self.state = TelnetState.DATA

    def output_translation(self) -> Generator[None, Optional[int], bytes]:
        """
        Generator to encode data into Telnet protocol format.
        Outputs as few bytes as necessary at one time.
        """
        while True:
            byte: Optional[int] = yield  # Receive one byte at a time

            if byte is None:
                # End of input, no more bytes to process
                return

            if byte == TelnetState.IAC_BYTE:
                # Escape IAC byte and yield immediately
                yield bytes([TelnetState.IAC_BYTE, TelnetState.IAC_BYTE])
            else:
                # Yield the single byte immediately
                yield bytes([byte])
