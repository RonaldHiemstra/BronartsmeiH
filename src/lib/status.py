"""File keeping track of the status of the brewery.

The method state.update() should be called at a regular base, to make sure LEDs will blink.
"""
import time
from machine import Pin
from config import Config
import uasyncio as asyncio

# TODO: also send the info (and alert) messages (with color info) to the webpage info bar.
# Note: update() is likely still needed in the boot process...

BLINK_INTERVAL = 0.3  # Toggle blinking LEDs every 0.3 seconds

class _Status:
    RED = 1
    GREEN = 2
    BLINK = 16

    def __init__(self):
        self._alert = dict()
        self.info = dict()
        self.last_info_key = None
        self.set_state('_Starting', self.RED | self.BLINK, 'Booting')

    def set_state(self, phase: str, color: int, info: str):
        """Set the current state of the brewery."""
        self._current_phase = phase
        self.set_info(phase, info)
        self.update(phase, color)

    def update(self, phase: str = None, color: int = None):
        """Update the status LEDs.
        params:
            phase  if specified, force an update of the LEDs.
        """

    def start_auto_update(self):
        """Update (blink) the status LEDS automatically"""
        self.set_state('_Starting', self.GREEN, 'Ready')
        loop = asyncio.get_event_loop()
        loop.create_task(self._auto_update())

    async def _auto_update(self) -> None:
        """Update the status LEDs."""
        while True:
            self.update()
            await asyncio.sleep(BLINK_INTERVAL)

    def set_info(self, key: str, message: str):
        """Store and log informational message.

        @param key      Message source.
        @param message  The message to store.
        """
        self.info[key] = message
        if self.last_info_key and self.last_info_key != key:
            print('')
            self.last_info_key = key
        print('%s: %s' % (key, message), end='\r')

    def get_info(self) -> dict:
        """Get all informational messages."""
        return self.info.copy()

    def alert(self, key: str, message: str):
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


class Status2Leds(_Status):
    """Test status, using single color LEDS, connected to the EPS digital output."""

    def __init__(self, red: str, green: str):
        io_connections = Config('hardware_config.json')
        self.red = Pin(int(io_connections.get(red)), Pin.OUT)
        self.green = Pin(int(io_connections.get(green)), Pin.OUT)
        self.red.value(0)
        self.green.value(0)
        self._last_update = 0
        self.phases = dict()
        self._blink_on = True
        self.prev_red_state = 0
        self.prev_green_state = 0
        super().__init__()

    def update(self, phase: str = None, color: int = None):
        """Update the status LEDs.
        params:
            phase  if specified, force an update of the LEDs.
        """
        # Add the given phase at the end of the list (or remove it, if no color is given)
        if phase in self.phases:
            del self.phases[phase]
        if color:
            self.phases[phase] = color

        now = time.time()
        # take the abs difference, to be robust for jumps in time due to time synchronization
        if phase is not None or abs(now - self._last_update) > BLINK_INTERVAL:
            self._last_update = now
            if phase is not None:
                self._blink_on = True  # Force an update of the LEDs
            else:
                self._blink_on = not self._blink_on  # Toggle blink status

            # Determine red and green LED state
            red_state = 0
            green_state = 0
            for cur_color in self.phases.values():
                if cur_color & self.RED:
                    red_state = cur_color
                if cur_color & self.GREEN:
                    green_state = cur_color

            if not self._blink_on:
                # Set blinking LEDs off
                if red_state & self.BLINK:
                    red_state = 0
                if green_state & self.BLINK:
                    green_state = 0

            if red_state != self.prev_red_state:
                self.prev_red_state = red_state
                self.red.value(red_state)
            if green_state != self.prev_green_state:
                self.prev_green_state = green_state
                self.green.value(green_state)


state = Status2Leds(red='led.red', green='led.green')
