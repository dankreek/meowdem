import termios
import sys
import tty
import asyncio
import termios
from copy import deepcopy
from typing import List, AsyncGenerator

from meowdem.input_handler import HayesATParser


def make_raw_with_signals(fd) -> list:
    """ Set terminal to raw mode but keep signal generation (e.g., Ctrl-C). 
    
    :param fd: File descriptor of the terminal (usually sys.stdin.fileno()).
    :return: Original terminal settings.
    """
    old_settings = termios.tcgetattr(fd)
    new_settings = deepcopy(old_settings)

    # Modify the new settings to make the terminal raw
    new_settings[tty.IFLAG] &= ~(termios.IGNBRK | termios.BRKINT | termios.IGNPAR |
                             termios.PARMRK | termios.INPCK | termios.ISTRIP |
                             termios.INLCR | termios.IGNCR | termios.ICRNL |
                             termios.IXON | termios.IXANY | termios.IXOFF)
    new_settings[tty.OFLAG] &= ~termios.OPOST
    new_settings[tty.CFLAG] &= ~(termios.PARENB | termios.CSIZE)
    new_settings[tty.CFLAG] |= termios.CS8
    new_settings[tty.LFLAG] &= ~(termios.ECHO | termios.ECHOE | termios.ECHOK |
                             termios.ECHONL | termios.ICANON | termios.IEXTEN |
                             termios.NOFLSH | termios.TOSTOP)
    new_settings[tty.LFLAG] |= termios.ISIG  # Re-enable signal generation (Ctrl-C, etc.)
    new_settings[tty.CC][termios.VMIN] = 1
    new_settings[tty.CC][termios.VTIME] = 0

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


def client_out(data: bytes):
    print(data.decode('latin1'), end='', flush=True)

async def main():
    parser = HayesATParser(client_out)

    async for next_char in stdin_without_echo():
        parser.receive(next_char.encode('latin1'))


if __name__ == "__main__":
    asyncio.run(main())