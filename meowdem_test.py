import pytest
import pytest_asyncio
import asyncio
import unittest.mock

from .meowdem import HayesATParser

class OutputCollector:
    """ Collects output as a single string for transparent test assertions. :param output: str :return: None """
    def __init__(self) -> None:
        self.value: str = ''
    def __call__(self, new_output: bytes) -> None:
        self.value += new_output.decode('latin-1')


class MockStreamWriter:
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


class MockStreamReader:
    async def read(self, n: int) -> bytes:
        await asyncio.sleep(0.01)
        return b''


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
    from .meowdem import ParserMode
    p, collector = parser
    p.writer = MockStreamWriter()  # type: ignore
    p.mode = ParserMode.DATA
    collector.value = ''
    await asyncio.to_thread(p.receive, b'+++')
    await asyncio.sleep(1.1)
    assert 'OK' in collector.value


@pytest.mark.asyncio
async def test_ATH_command(parser: tuple[HayesATParser, OutputCollector]) -> None:
    """ Test the ATH command hangs up and returns NO CARRIER. :param parser: tuple[HayesATParser, OutputCollector] :return: None """
    from .meowdem import ParserMode
    p, collector = parser
    p.writer = MockStreamWriter()  # type: ignore
    p.mode = ParserMode.COMMAND
    collector.value = ''
    p.receive(b'ATH\r')
    assert 'NO CARRIER' in collector.value
    assert p.writer is None


@pytest.mark.asyncio
async def test_ATD_command(parser: tuple[HayesATParser, OutputCollector]) -> None:
    p, collector = parser
    collector.value = ''

    async def dummy_open_connection(*args, **kwargs):
        return MockStreamReader(), MockStreamWriter()

    with unittest.mock.patch('asyncio.open_connection', dummy_open_connection):
        p.receive(b'ATD127.0.0.1:2323\r')
        # Wait up to 2 seconds for CONNECT
        for _ in range(20):
            if 'CONNECTED' in collector.value:
                break
            await asyncio.sleep(0.1)
        assert 'CONNECTED' in collector.value


@pytest.mark.asyncio
async def test_ATD_connect_failure(parser: tuple[HayesATParser, OutputCollector]) -> None:
    p, collector = parser
    collector.value = ''

    async def dummy_open_connection(*args, **kwargs):
        raise OSError('connection failed')

    with unittest.mock.patch('asyncio.open_connection', dummy_open_connection):
        p.receive(b'ATD127.0.0.1:2323\r')
        # Wait up to 2 seconds for NO CARRIER
        for _ in range(20):
            if 'NO CARRIER' in collector.value:
                break
            await asyncio.sleep(0.1)
        assert 'NO CARRIER' in collector.value


@pytest.mark.asyncio
async def test_enable_telnet_translation(parser: tuple[HayesATParser, OutputCollector]) -> None:
    p, collector = parser
    collector.value = ''
    await asyncio.to_thread(p.receive, b'AT*T1\r')
    assert p.telnet_translation_enabled is True


@pytest.mark.asyncio
async def test_disable_telnet_translation(parser: tuple[HayesATParser, OutputCollector]) -> None:
    p, collector = parser
    p.telnet_translation_enabled = True
    collector.value = ''
    await asyncio.to_thread(p.receive, b'AT*T0\r')
    assert p.telnet_translation_enabled is False


@pytest.mark.asyncio
async def test_ATE0_command(parser: tuple[HayesATParser, OutputCollector]) -> None:
    p, collector = parser
    p.echo_enabled = True
    collector.value = ''
    await asyncio.to_thread(p.receive, b'ATE0\r')
    assert p.echo_enabled is False
    assert 'OK' in collector.value


@pytest.mark.asyncio
async def test_ATE1_command(parser: tuple[HayesATParser, OutputCollector]) -> None:
    p, collector = parser
    p.echo_enabled = False
    collector.value = ''
    await asyncio.to_thread(p.receive, b'ATE1\r')
    assert p.echo_enabled is True
    assert 'OK' in collector.value


@pytest.mark.asyncio
async def test_ATO_command(parser: tuple[HayesATParser, OutputCollector]) -> None:
    """ Test the ATO command returns CONNECT and sets mode to DATA if writer is present. :param parser: tuple[HayesATParser, OutputCollector] :return: None """
    from .meowdem import ParserMode
    p, collector = parser
    p.writer = MockStreamWriter()  # type: ignore
    p.mode = ParserMode.COMMAND
    collector.value = ''
    await asyncio.to_thread(p.receive, b'ATO\r')
    assert 'CONNECT' in collector.value
    assert p.mode == ParserMode.DATA

@pytest.mark.asyncio
async def test_ATO_command_no_carrier(parser: tuple[HayesATParser, OutputCollector]) -> None:
    """ Test the ATO command returns NO CARRIER if writer is None. :param parser: tuple[HayesATParser, OutputCollector] :return: None """
    from .meowdem import ParserMode
    p, collector = parser
    p.writer = None
    p.mode = ParserMode.COMMAND
    collector.value = ''
    await asyncio.to_thread(p.receive, b'ATO\r')
    assert 'NO CARRIER' in collector.value
    assert p.mode == ParserMode.COMMAND
