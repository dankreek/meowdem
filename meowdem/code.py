class ATCommandInterpreter:
    def __init__(self):
        self.echo_enabled = True
        self.verbose_mode = True
        self.registered_commands = {
            "AT": self.handle_at_command,
            "ATE": self.handle_echo,
            "ATV": self.handle_verbose,
            "ATH": self.handle_hangup,
            "ATD": self.handle_dial,
            "ATZ": self.handle_reset,
            "AT+CMGR": self.handle_read_sms,
            "AT+CMGS": self.handle_send_sms,
            "AT&F": self.handle_factory_reset,
            "AT&W": self.handle_write_settings,
            "AT+CSQ": self.handle_signal_quality,
            "ATO": self.handle_online,
        }
        self.connected = False
        self.dialing = False
        # Buffer to store incomplete commands
        self.command_buffer = ""
        # Mode tracking
        self.in_command_mode = True
        self.in_data_mode = False
        # For handling +++ escape sequence
        self.escape_buffer = ""
        self.escape_time = None
        self.guard_time = 1.0  # Guard time in seconds for escape sequence
        self.last_char_time = 0
        
    def receive_data(self, data):
        """Process data, handling it differently based on current mode"""
        import time
        current_time = time.time()
        
        # If in data mode, check for escape sequence
        if self.in_data_mode:
            # Process each character for potential escape sequence
            for char in data:
                # Check if enough time has passed since the last character
                if current_time - self.last_char_time > self.guard_time:
                    # Reset escape buffer if guard time was respected
                    self.escape_buffer = ""
                
                self.last_char_time = current_time
                
                # Add character to escape buffer and keep only the last 3
                self.escape_buffer += char
                if len(self.escape_buffer) > 3:
                    self.escape_buffer = self.escape_buffer[-3:]
                
                # Check if escape sequence is complete
                if self.escape_buffer == "+++":
                    # Mark when escape sequence was detected
                    self.escape_time = current_time
                    # We'll transition to command mode after respecting guard time
                    
            # Check if escape sequence followed by guard time
            if self.escape_buffer == "+++" and current_time - self.escape_time >= self.guard_time:
                self.in_command_mode = True
                self.in_data_mode = False
                self.escape_buffer = ""
                return self._format_response(True, "OK", "Switched to command mode")
            
            # In data mode, just echo data (this would normally go to the connected device)
            return f"[DATA]: {data}"
        else:
            # In command mode, parse as AT commands
            return self.parse_multiple_commands(data)
    
    def parse_multiple_commands(self, input_str):
        """Parse a string that may contain multiple AT commands and return all responses"""
        # Check for escape sequence first (special case)
        if input_str == "+++":
            # In a real implementation, we would start a timer here and wait for guard time
            return ""  # No immediate response to +++
        
        # Add new input to our buffer
        self.command_buffer += input_str
        
        responses = []
        
        # Process commands one by one
        while True:
            # Check for command termination characters
            terminator_index = -1
            for term in ["\r", "\n", ";", "\r\n"]:
                if term in self.command_buffer:
                    idx = self.command_buffer.find(term)
                    if terminator_index == -1 or idx < terminator_index:
                        terminator_index = idx
            
            # If no terminator found, we need more input
            if terminator_index == -1:
                break
                
            # Extract the command
            command = self.command_buffer[:terminator_index].strip()
            
            # Update buffer, removing the command and terminator
            terminator = self.command_buffer[terminator_index]
            if terminator == "\r" and len(self.command_buffer) > terminator_index + 1 and self.command_buffer[terminator_index + 1] == "\n":
                # Handle \r\n as a single terminator
                self.command_buffer = self.command_buffer[terminator_index + 2:]
            else:
                self.command_buffer = self.command_buffer[terminator_index + 1:]
            
            # Process command if not empty
            if command:
                response = self.parse_command(command)
                responses.append(response)
            
            # If buffer is empty now, we're done
            if not self.command_buffer.strip():
                break
        
        return "".join(responses) if responses else ""
    
    def parse_command(self, command_str):
        """Parse an AT command string and execute the corresponding handler"""
        command_str = command_str.strip()
        
        # Return if empty command
        if not command_str:
            return ""
            
        # Echo command if enabled
        if self.echo_enabled:
            print(command_str)
        
        # Check if it's an AT command
        if not command_str.upper().startswith("AT"):
            return self._format_response(False, "ERROR", "Unknown command")
            
        # Find the matching command
        for cmd_prefix, handler in self.registered_commands.items():
            if command_str.upper().startswith(cmd_prefix):
                # Extract parameters (anything after the command)
                params = command_str[len(cmd_prefix):]
                return handler(params)
                
        return self._format_response(False, "ERROR", "Command not supported")
        
    def _format_response(self, success, response_code, message=""):
        """Format response according to verbose mode"""
        if self.verbose_mode:
            if success:
                return f"\r\n{response_code}\r\n"
            else:
                return f"\r\n{response_code}: {message}\r\n"
        else:
            # In numeric mode
            return f"\r\n{0 if success else 4}\r\n"
    
    # Command handlers
    def handle_at_command(self, params):
        """Basic AT command - checks if modem is responsive"""
        return self._format_response(True, "OK")
        
    def handle_echo(self, params):
        """ATE command - controls command echo"""
        if params == "0":
            self.echo_enabled = False
            return self._format_response(True, "OK")
        elif params == "1":
            self.echo_enabled = True
            return self._format_response(True, "OK")
        else:
            return self._format_response(False, "ERROR", "Invalid parameter")
            
    def handle_verbose(self, params):
        """ATV command - controls verbosity of responses"""
        if params == "0":
            self.verbose_mode = False
            return self._format_response(True, "OK")
        elif params == "1":
            self.verbose_mode = True
            return self._format_response(True, "OK")
        else:
            return self._format_response(False, "ERROR", "Invalid parameter")
            
    def handle_hangup(self, params):
        """ATH command - hangup current connection"""
        if self.connected:
            self.connected = False
            self.in_data_mode = False
            return self._format_response(True, "OK", "Connection terminated")
        return self._format_response(True, "OK", "No active connection")
        
    def handle_dial(self, params):
        """ATD command - dial a number"""
        if not params:
            return self._format_response(False, "ERROR", "Number required")
            
        self.dialing = True
        self.connected = True
        # By default, enter data mode after successful connection
        self.in_data_mode = True
        self.in_command_mode = False
        
        return f"\r\nDIALING {params}\r\nCONNECTED\r\n"
    
    def handle_online(self, params):
        """ATO command - return to online/data mode"""
        if not self.connected:
            return self._format_response(False, "ERROR", "No active connection")
        
        self.in_data_mode = True
        self.in_command_mode = False
        return "\r\nCONNECTED\r\n"
        
    def handle_reset(self, params):
        """ATZ command - reset modem"""
        old_command_buffer = self.command_buffer
        self.__init__()  # Reset to initial state
        self.command_buffer = old_command_buffer  # Preserve command buffer
        return self._format_response(True, "OK", "Modem reset")
        
    def handle_read_sms(self, params):
        """AT+CMGR command - read SMS message"""
        if not params:
            return self._format_response(False, "ERROR", "Message index required")
            
        try:
            index = int(params.strip("="))
            # In a real implementation, you would retrieve the message from storage
            return f"\r\n+CMGR: \"REC UNREAD\",\"+12345678901\",\"\",\"2023/01/01,12:00:00\"\r\nThis is a sample SMS message #{index}\r\n\r\nOK\r\n"
        except ValueError:
            return self._format_response(False, "ERROR", "Invalid parameter")
            
    def handle_send_sms(self, params):
        """AT+CMGS command - send SMS message"""
        if not params.startswith("="):
            return self._format_response(False, "ERROR", "Invalid format")
            
        try:
            # In a real implementation, this would wait for message input and send
            return "\r\n> "  # Prompt for message content
            # After receiving message content and CTRL+Z:
            # return self._format_response(True, "OK", "Message sent")
        except Exception:
            return self._format_response(False, "ERROR", "Failed to send message")
            
    def handle_factory_reset(self, params):
        """AT&F command - factory reset"""
        old_command_buffer = self.command_buffer
        self.__init__()  # Reset to initial state
        self.command_buffer = old_command_buffer  # Preserve command buffer
        return self._format_response(True, "OK", "Factory settings restored")
        
    def handle_write_settings(self, params):
        """AT&W command - write current settings to memory"""
        # In a real implementation, this would save settings to non-volatile memory
        return self._format_response(True, "OK", "Settings saved")
        
    def handle_signal_quality(self, params):
        """AT+CSQ command - get signal quality"""
        # In a real implementation, this would return actual signal metrics
        return "\r\n+CSQ: 28,0\r\n\r\nOK\r\n"  # Example: good signal strength

