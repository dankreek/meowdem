from typing import Generator, Optional

def telnet_bytewise_filter() -> Generator[Optional[int], int, None]:
    IAC = 255
    SB = 250
    SE = 240
    WILL = 251
    WONT = 252
    DO = 253
    DONT = 254

    state: str = "DATA"
    subnegotiation: bool = False
    sb_data: list[int] = []

    while True:
        byte: int = yield  # Receive one byte at a time

        if state == "DATA":
            if byte == IAC:
                state = "IAC"
            else:
                yield byte  # Normal data byte

        elif state == "IAC":
            if byte == IAC:
                yield IAC  # Escaped 0xFF
                state = "DATA"
            elif byte in (WILL, WONT, DO, DONT):
                state = "IAC_OPTION"
                option_length = 1
            elif byte == SB:
                state = "SB"
                subnegotiation = True
                sb_data = []
            else:
                # Simple command, no option
                state = "DATA"

        elif state == "IAC_OPTION":
            # Skip option byte
            state = "DATA"

        elif state == "SB":
            if byte == IAC:
                state = "SB_IAC"
            else:
                sb_data.append(byte)

        elif state == "SB_IAC":
            if byte == IAC:
                sb_data.append(IAC)  # Escaped IAC inside SB
                state = "SB"
            elif byte == SE:
                subnegotiation = False
                sb_data = []
                state = "DATA"
            else:
                # Unexpected — discard SB
                state = "DATA"

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
