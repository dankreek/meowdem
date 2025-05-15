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

def telnet_input_translation() -> Generator[Optional[int], int, None]:
    # Use the constants from TelnetState
    WILL = 251
    WONT = 252
    DO = 253
    DONT = 254

    state: TelnetState = TelnetState.DATA
    subnegotiation: bool = False
    sb_data: list[int] = []

    while True:
        byte: int = yield  # Receive one byte at a time

        if state == TelnetState.DATA:
            if byte == TelnetState.IAC_BYTE:
                state = TelnetState.IAC
            else:
                yield byte  # Normal data byte

        elif state == TelnetState.IAC:
            if byte == TelnetState.IAC_BYTE:
                yield TelnetState.IAC_BYTE  # Escaped 0xFF
                state = TelnetState.DATA
            elif byte in (WILL, WONT, DO, DONT):
                state = TelnetState.IAC_OPTION
                option_length = 1
            elif byte == TelnetState.SB_BYTE:
                state = TelnetState.SB
                subnegotiation = True
                sb_data = []
            else:
                # Simple command, no option
                state = TelnetState.DATA

        elif state == TelnetState.IAC_OPTION:
            # Skip option byte
            state = TelnetState.DATA

        elif state == TelnetState.SB:
            if byte == TelnetState.IAC_BYTE:
                state = TelnetState.SB_IAC
            else:
                sb_data.append(byte)

        elif state == TelnetState.SB_IAC:
            if byte == TelnetState.IAC_BYTE:
                sb_data.append(TelnetState.IAC_BYTE)  # Escaped IAC inside SB
                state = TelnetState.SB
            elif byte == TelnetState.SE_BYTE:
                subnegotiation = False
                sb_data = []
                state = TelnetState.DATA
            else:
                # Unexpected — discard SB
                state = TelnetState.DATA

def telnet_output_translation() -> Generator[None, Optional[int], bytes]:
    """
    Generator to encode data into Telnet protocol format.
    Send one byte at a time to the generator, and it will yield encoded bytes.
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

## Example: feeding bytes into the generator and printing output
#def run_bytewise_example(data):
#    f = telnet_bytewise_filter()
#    next(f)  # Prime the generator
#
#    for b in data:
#        output = f.send(b)
#        if output is not None:
#            print(f"Output byte: {output!r}")

## Example stream: includes 'H', 'e', 'l', 'l', 'o', then IAC DO 1, then 'W'
# test = b'Hello\xff\xfd\x01W'
# run_bytewise_example(test)
