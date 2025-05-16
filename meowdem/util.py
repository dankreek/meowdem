from typing import Generator
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

class TelnetTranslator:
    def __init__(self):
        self.state: TelnetState = TelnetState.DATA
        self.subnegotiation: bool = False

    def input_translation(self) -> Generator[bytes, bytes, None]:
        """
        Generator to decode Telnet protocol input.
        """
        WILL = 251
        WONT = 252
        DO = 253
        DONT = 254

        while True:
            bytes_chunk: bytes = yield  # Receive a chunk of bytes at a time

            output = bytearray()
            for byte in bytes_chunk:
                if self.state == TelnetState.DATA:
                    if byte == TelnetState.IAC_BYTE:
                        self.state = TelnetState.IAC
                    else:
                        output.append(byte)  # Normal data byte

                elif self.state == TelnetState.IAC:
                    if byte == TelnetState.IAC_BYTE:
                        output.append(TelnetState.IAC_BYTE)  # Escaped 0xFF
                        self.state = TelnetState.DATA
                    elif byte in (WILL, WONT, DO, DONT):
                        self.state = TelnetState.IAC_OPTION
                    elif byte == TelnetState.SB_BYTE:
                        self.state = TelnetState.SB
                        self.subnegotiation = True
                    else:
                        # Simple command, no option
                        self.state = TelnetState.DATA

                elif self.state == TelnetState.IAC_OPTION:
                    # Skip option byte
                    self.state = TelnetState.DATA

                elif self.state == TelnetState.SB:
                    if byte == TelnetState.IAC_BYTE:
                        self.state = TelnetState.SB_IAC

                elif self.state == TelnetState.SB_IAC:
                    if byte == TelnetState.IAC_BYTE:
                        self.state = TelnetState.SB
                    elif byte == TelnetState.SE_BYTE:
                        self.subnegotiation = False
                        self.state = TelnetState.DATA
                    else:
                        # Unexpected — discard SB
                        self.state = TelnetState.DATA

            yield bytes(output)

    def output_translation(self) -> Generator[None, bytes, bytes]:
        """
        Generator to encode data into Telnet protocol format.
        """
        while True:
            bytes_chunk: bytes = yield  # Receive a chunk of bytes at a time

            output = bytearray()
            for byte in bytes_chunk:
                if byte == TelnetState.IAC_BYTE:
                    # Escape IAC byte and append immediately
                    output.extend([TelnetState.IAC_BYTE, TelnetState.IAC_BYTE])
                else:
                    # Append the single byte immediately
                    output.append(byte)

            yield bytes(output)
