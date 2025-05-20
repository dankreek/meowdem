import pytest
import pytest_asyncio
import asyncio
from meowdem.input_handler import HayesATParser
from typing import Callable, Any

class OutputCollector:
    """ Collects output as a single string for transparent test assertions. :param output: str :return: None """
    def __init__(self) -> None:
        self.value: str = ''
    def __call__(self, new_output: bytes) -> None:
        self.value += new_output.decode('latin-1')

@pytest_asyncio.fixture
async def parser() -> tuple[HayesATParser, OutputCollector]:
    """ Fixture to create a HayesATParser and OutputCollector. :return: tuple[HayesATParser, OutputCollector] """
    collector = OutputCollector()
    p = HayesATParser(client_output_cb=collector)
    return p, collector

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
