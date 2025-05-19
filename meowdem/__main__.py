import termios
import sys
import tty
import asyncio
import termios
from copy import deepcopy
from typing import List, AsyncGenerator, Callable
import multiprocessing

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


async def handle_tcp_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """ Async handler for each TCP client using HayesATParser. 
    :param reader: StreamReader for the client.
    :param writer: StreamWriter for the client.
    :return: None
    """
    def tcp_client_out(data: bytes) -> None:
        """ Output function for HayesATParser to send data to TCP client. 
        :param data: Data to send.
        :return: None
        """
        writer.write(data)
        # Schedule drain asynchronously
        asyncio.create_task(writer.drain())

    print('Connection is connected')
    parser = HayesATParser(tcp_client_out)
    try:
        while True:
            data = await reader.read(1024)
            if not data:
                break
            parser.receive(data)
    except Exception:
        pass
    finally:
        writer.close()
        await writer.wait_closed()

async def _stdin_loop(parser: HayesATParser) -> None:
    """ Read from stdin and send to parser. 
    :param parser: HayesATParser instance.
    :return: None
    """
    async for next_char in stdin_without_echo():
        parser.receive(next_char.encode('latin1'))

async def main() -> None:
    """ Main entry point: handles both stdin and TCP connections. 
    :return: None
    """
    parser = HayesATParser(client_out)
    server = await asyncio.start_server(handle_tcp_client, '0.0.0.0', 2323)
    async with server:
        stdin_task = asyncio.create_task(_stdin_loop(parser))
        await server.serve_forever()
        await stdin_task


if __name__ == '__main__':
    asyncio.run(main())