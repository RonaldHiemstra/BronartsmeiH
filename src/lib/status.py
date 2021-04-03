"""File keeping track of the status of the brewery.

The method state.update() should be called at a regular base, to make sure LEDs will blink.
"""
import logging
import time
from machine import Pin
# TODO: implement actual control of the LEDs.
# TODO: add asyncio support, so the call to update() is no longer needed.
# TODO: also send the info (and alert) messages (with color info) to the webpage info bar.
# Note: update() is likely still needed in the boot process...
class _Status:
    STARTING = 0
    MAICHEN = 1
    BOILING = 2
    COOLING = 3
    FERMENTING = 4
    MATURING = 5
    _NR_OF_PHASES = 6

    RED = 1
    GREEN = 2
    BLUE = 4
    WHITE = 7
    BLINK = 16

    def __init__(self):
        self._last_update = 0
        self._leds = [0 for _ in range(self._NR_OF_PHASES)]
        self._prev = self._leds.copy()
        self._blink_on = True
        self._alert = dict()
        self.info = dict()
        self.last_info_key = None
        self.set_state(self.STARTING, self.RED | self.BLINK, 'Booting')

    def set_state(self, phase, color, info):
        """Set the current state of the brewery."""
        if phase >= self._NR_OF_PHASES:
            logging.error('wrong phase: %d', phase)
            return
        self._leds[phase] = color
        self._current_phase = phase
        self.set_info(['Starting', 'Maichen', 'Boiling', 'Cooling', 'Fermenting', 'Maturing'][phase], info)
        self.update(True)

    def update(self, force_update=False):
        """Update the status LEDs."""
        if force_update:
            self._blink_on = True
        now = time.time()
        # take the abs difference, to be robust for jumps in time due to time synchronization
        if force_update or abs(now - self._last_update) > 0.3:
            self._last_update = now
            for index in range(self._NR_OF_PHASES):
                if (self._leds[index] != self._prev[index]) or (self._leds[index] & self.BLINK):
                    self._prev[index] = self._leds[index]
                    color = (self._prev[index] & (self.BLINK - 1)) if self._leds[index] & self.BLINK == 0 or self._blink_on else 0
                    print('LED %d = %d' % (index, color))
                    self._set_led(index, color)

            self._blink_on = not self._blink_on

    def _set_led(self, index: int, color: int):
        """Set the specified led to the given color."""

    def set_info(self, key: str, message: str) -> None:
        """Store and log informational message.

        @param key      Message source.
        @param message  The message to store.
        """
        self.info[key] = message
        if self.last_info_key and self.last_info_key != key:
            print('')
            self.last_info_key = key
        print('%s: %s' % (key, message), end='\r')

    def get_info(self):
        """Get all informational messages."""
        return self.info.copy()

    def alert(self, key: str, message:str) -> None:
        """Store and allert a message.

        @param key      Message source.
        @param message  The message to store. If None, the alert is served.
        """
        if message is None:
            del self._alert[key]
            return
        if self._alert.get(key) == message:
            return
        self._alert[key] = message
        if self.last_info_key:
            self.last_info_key = None
            print('')
        print('!' * 40)
        print('ALERT! %s: %s' % (key, message))

class TestStatus(_Status):
    """Test status, using single color LEDS, connected to the EPS digital output."""
    def __init__(self):
        self.pins = [Pin(pin, Pin.OUT) for pin in [12, 14, 27, 26, 25, 33]]
        assert len(self.pins) == self._NR_OF_PHASES
        super().__init__()

    def _set_led(self, index: int, color: int):
        """Set the specified led to the given color."""
        self.pins[index].value(1 if color else 0) # The test led only supports 1 color.


state = TestStatus()
