import pytest
from unittest.mock import patch
from meowdem.code import ATCommandInterpreter

@pytest.fixture
def interpreter():
    return ATCommandInterpreter()

def test_basic_command(interpreter):
    response = interpreter.receive_data("AT\r")
    assert response == "OK\r"  # Replace with the actual expected response

def test_data_mode_and_escape_sequence(interpreter):
    # Test dialing
    response = interpreter.process_data("ATD12345\r")
    assert response == "CONNECT"  # Replace with the actual expected response

    # Test sending data in data mode
    response = interpreter.process_data("Hello, this is test data!")
    assert response == "DATA SENT"  # Replace with the actual expected response

    # Test escape sequence with guard time
    with patch("time.sleep") as mock_sleep:
        interpreter.process_data("+++")
        mock_sleep.assert_called_once_with(1.1)  # Ensure guard time is respected

    response = interpreter.process_data("")  # Empty string to check status
    assert response == "COMMAND MODE"  # Replace with the actual expected response

def test_verify_command_mode(interpreter):
    response = interpreter.process_data("AT\r")
    assert response == "OK"  # Replace with the actual expected response

def test_return_to_online_mode(interpreter):
    response = interpreter.process_data("ATO\r")
    assert response == "ONLINE"  # Replace with the actual expected response

def test_sending_more_data(interpreter):
    response = interpreter.process_data("Back in data mode!")
    assert response == "DATA SENT"  # Replace with the actual expected response

def test_multiple_commands(interpreter):
    multi_commands = "AT\rATE0\rAT+CSQ\r"
    response = interpreter.process_data(multi_commands)
    assert response == "OK OK SIGNAL QUALITY"  # Replace with the actual expected response