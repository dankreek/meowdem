import pytest
import pytest_asyncio
import asyncio
from meowdem.input_handler import HayesATParser


class OutputCollector:
    """ Collects output as a single string for transparent test assertions. :param output: str :return: None """
    def __init__(self) -> None:
        self.value: str = ''
    def __call__(self, new_output: bytes) -> None:
        self.value += new_output.decode('latin-1')


class DummyWriter:
    def write(self, data: bytes) -> None:
        pass
    def drain(self) -> None:
        return None
    def is_closing(self) -> bool:
        return False
    def close(self) -> None:
        pass
    async def wait_closed(self) -> None:
        pass


@pytest_asyncio.fixture
async def parser():
    """ Fixture to create a HayesATParser and OutputCollector. :return: tuple[HayesATParser, OutputCollector] """
    collector = OutputCollector()
    p = HayesATParser(client_output_cb=collector)
    try:
        yield p, collector
    finally:
        p.guard_time_task.cancel()
        try:
            await p.guard_time_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_ATZ_command(parser: tuple[HayesATParser, OutputCollector]) -> None:
    """ Test the ATZ command resets the modem and returns OK. :param parser: tuple[HayesATParser, OutputCollector] :return: None """
    p, collector = parser
    await asyncio.to_thread(p.receive, b'ATZ\r')
    assert collector.value == 'ATZ\r\nOK\r\n'


@pytest.mark.asyncio
async def test_AT_command_with_space(parser: tuple[HayesATParser, OutputCollector]) -> None:
    """ Test the ATZ command resets the modem and returns OK. :param parser: tuple[HayesATParser, OutputCollector] :return: None """
    p, collector = parser
    await asyncio.to_thread(p.receive, b'AT Z\r')
    assert collector.value == 'AT Z\r\nOK\r\n'


@pytest.mark.asyncio
async def test_escape_data_mode_with_plus(parser: tuple[HayesATParser, OutputCollector]) -> None:
    """ Test that sending '+++' escapes data mode and returns OK. :param parser: tuple[HayesATParser, OutputCollector] :return: None """
    from meowdem.input_handler import ParserMode
    p, collector = parser
    p.writer = DummyWriter()  # type: ignore
    p.mode = ParserMode.DATA
    collector.value = ''
    await asyncio.to_thread(p.receive, b'+++')
    await asyncio.sleep(1.1)
    assert 'OK' in collector.value


@pytest.mark.asyncio
async def test_ATH_command(parser: tuple[HayesATParser, OutputCollector]) -> None:
    """ Test the ATH command hangs up and returns NO CARRIER. :param parser: tuple[HayesATParser, OutputCollector] :return: None """
    from meowdem.input_handler import ParserMode
    p, collector = parser
    p.writer = DummyWriter()  # type: ignore
    p.mode = ParserMode.COMMAND
    collector.value = ''
    p.receive(b'ATH\r')
    assert 'NO CARRIER' in collector.value
    assert p.writer is None

