from typing import Generator
from enum import Enum

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
