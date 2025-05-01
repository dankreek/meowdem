from meowdem.code import ATCommandInterpreter

def main():
    import time
    
    interpreter = ATCommandInterpreter()
    
    print("=== Hayes AT Command Interpreter Demo ===")
    
    # Basic command test
    print("\n-- Basic Command Test --")
    response = interpreter.parse_command("AT")
    print("Response:", response)
    
    # Test data mode and escape sequence
    print("\n-- Data Mode and Escape Sequence Test --")
    
    print("Dialing...")
    response = interpreter.process_data("ATD12345\r")
    print(response)
    
    print("\nSending data in data mode:")
    response = interpreter.process_data("Hello, this is test data!")
    print(response)
    
    print("\nSending escape sequence with guard time:")
    # Send escape sequence
    print("Sending: +++")
    interpreter.process_data("+++")
    
    # Wait for guard time
    print("Waiting for guard time...")
    time.sleep(1.1)  # Slightly more than guard time
    
    # Any character after guard time should trigger mode switch
    response = interpreter.process_data("")  # Empty string to check status
    print("Response after guard time:", response)
    
    # Verify we're in command mode
    print("\nVerifying command mode:")
    response = interpreter.process_data("AT\r")
    print(response)
    
    # Return to online mode
    print("\nReturning to online mode:")
    response = interpreter.process_data("ATO\r")
    print(response)
    
    # Send data again in data mode
    print("\nSending more data:")
    response = interpreter.process_data("Back in data mode!")
    print(response)
    
    # Multiple command test
    print("\n-- Multiple Command Test --")
    multi_commands = "AT\rATE0\rAT+CSQ\r"
    print(f"Sending multiple commands: {multi_commands}")
    response = interpreter.process_data(multi_commands)
    print("Response:", response)
# Demo usage
if __name__ == "__main__":
    main()