import pytest
from unittest.mock import patch
from meowdem.input_handler import HayesATParser


@pytest.fixture
def parser():
    logs = []
    p = HayesATParser(client_output_cb=logs.append)
    return p, logs


def test_simple_command(parser):
    p, logs = parser
    p.receive("ATZ\r")
    assert "Resetting modem..." in logs
    assert "OK" in logs


def test_compound_command(parser):
    p, logs = parser
    p.receive("ATS0=1Z&C1%F0\r")
    assert "Set S0 = 1" in logs
    assert "Resetting modem..." in logs
    assert "Set &C = 1" in logs
    assert "Set %F = 0" in logs
    assert "OK" in logs


def test_dial_command_enters_data_mode(parser):
    p, logs = parser
    p.receive("ATD5551212\r")
    assert "Dialing 5551212..." in logs
    assert "[Modem switched to DATA mode]" in logs
    assert p.mode == "data"


@patch("time.time")
def test_escape_sequence_success(mock_time, parser):
    p, logs = parser
    mock_time.side_effect = [0, 2, 3.1]  # ATDT, then +++

    p.receive("ATDT123\r")
    p.receive("+++")
    assert "[Modem switched to COMMAND mode]" in logs
    assert p.mode == "command"


@patch("time.time")
def test_escape_sequence_failure_due_to_guard_time(mock_time, parser):
    p, logs = parser
    mock_time.side_effect = [0, 0.5, 0.7]  # Not enough guard time

    p.receive("ATDT123\r")
    p.receive("+++")
    assert "[Ignored '+++' - failed guard time check]" in logs
    assert p.mode == "data"


def test_data_mode_ignores_commands(parser):
    p, logs = parser
    p.mode = "data"
    p.receive("ATZ\r")
    assert "[DATA MODE] ATZ\r" in logs
    assert "Resetting modem..." not in logs
