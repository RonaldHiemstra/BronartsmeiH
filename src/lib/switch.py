from machine import Pin


class PowerSwitch():
    """Control the heater of the kettle."""

    def __init__(self, device_name, pin=13):
        self.device_name = device_name
        self.pin = Pin(pin, Pin.OUT)
        self.state = None

    def turn_on(self):
        """Turn the heater on."""
        if self.state is not 1:
            self.state = 1
            self.pin.value(self.state)
#            state.set_info(self.device_name, 'ON')

    def turn_off(self):
        """Turn the heater off."""
        if self.state is not 0:
            self.state = 0
            self.pin.value(self.state)
#            state.set_info(self.device_name, 'OFF')
