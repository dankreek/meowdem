import termios
import sys
import tty
import asyncio
from copy import deepcopy
from typing import List, AsyncGenerator

from meowdem.input_handler import HayesATParser


def make_raw_with_signals(fd) -> List[int]:
    """ Set terminal to raw mode but keep signal generation (e.g., Ctrl-C). 
    
    :param fd: File descriptor of the terminal (usually sys.stdin.fileno()).
    :return: Original terminal settings.
    """
    old_settings = termios.tcgetattr(fd)
    new_settings = deepcopy(old_settings)

    # Modify the new settings to make the terminal raw
    new_settings[tty.IFLAG] &= ~(tty.IGNBRK | tty.BRKINT | tty.IGNPAR |
                                     tty.PARMRK | tty.INPCK | tty.ISTRIP |
                                     tty.INLCR | tty.IGNCR | tty.ICRNL |
                                     tty.IXON | tty.IXANY | tty.IXOFF)
    new_settings[tty.OFLAG] &= ~tty.OPOST
    new_settings[tty.CFLAG] &= ~(tty.PARENB | tty.CSIZE)
    new_settings[tty.CFLAG] |= tty.CS8
    new_settings[tty.LFLAG] &= ~(tty.ECHO | tty.ECHOE | tty.ECHOK |
                                     tty.ECHONL | tty.ICANON | tty.IEXTEN |
                                     tty.NOFLSH | tty.TOSTOP)
    new_settings[tty.LFLAG] |= tty.ISIG  # Re-enable signal generation (Ctrl-C, etc.)
    new_settings[tty.CC][tty.VMIN] = 1
    new_settings[tty.CC][tty.VTIME] = 0

    # Apply the new settings
    termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)
    return old_settings


async def stdin_without_echo() -> AsyncGenerator[str, None]:
    fd = sys.stdin.fileno()
    old_settings = make_raw_with_signals(fd)

    try:
        loop = asyncio.get_running_loop()
        while True:
            # Use asyncio to read a single character asynchronously
            next_char = await loop.run_in_executor(None, sys.stdin.read, 1)
            yield next_char
    finally:
        # Restore the original terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def client_out(char: str):
    print(char, end='', flush=True)

async def main():
    parser = HayesATParser(client_out)

    async for next_char in stdin_without_echo():
        parser.receive(next_char)


if __name__ == "__main__":
    asyncio.run(main())