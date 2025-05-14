from typing import Generator, Optional
from enum import Enum

class TelnetState(Enum):
    DATA = "DATA"
    IAC = "IAC"
    IAC_OPTION = "IAC_OPTION"
    SB = "SB"
    SB_IAC = "SB_IAC"

def telnet_filter() -> Generator[Optional[int], int, None]:
    IAC = 255
    SB = 250
    SE = 240
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
            if byte == IAC:
                state = TelnetState.IAC
            else:
                yield byte  # Normal data byte

        elif state == TelnetState.IAC:
            if byte == IAC:
                yield IAC  # Escaped 0xFF
                state = TelnetState.DATA
            elif byte in (WILL, WONT, DO, DONT):
                state = TelnetState.IAC_OPTION
                option_length = 1
            elif byte == SB:
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
            if byte == IAC:
                state = TelnetState.SB_IAC
            else:
                sb_data.append(byte)

        elif state == TelnetState.SB_IAC:
            if byte == IAC:
                sb_data.append(IAC)  # Escaped IAC inside SB
                state = TelnetState.SB
            elif byte == SE:
                subnegotiation = False
                sb_data = []
                state = TelnetState.DATA
            else:
                # Unexpected — discard SB
                state = TelnetState.DATA

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
