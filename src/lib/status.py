"""File keeping track of the status of the brewery.

The method state.update() should be called at a regular base, to make sure LEDs will blink.
"""
import logging
import time

# TODO: implement actual controll of the LEDs.
# TODO: add asyncio support, so the call to update() is no longer needed.
# TODO: also send the info messages (with color info) to the webpage info bar.
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
        self.set_state(self.STARTING, self.RED | self.BLINK, 'Booting')

    def set_state(self, phase, color, info):
        """Set the current state of the brewery."""
        if phase >= self._NR_OF_PHASES:
            logging.error('wrong phase: %d', phase)
            return
        self._leds[phase] = color
        if phase:
            self._current_phase = phase
        if info:
            self._info = info
        self.update(True)

    def update(self, force_update=False):
        """Update the status LEDs.
        """
        if force_update:
            self._blink_on = True
        now = time.time()
        # take the abs difference, to be robust for jumps in time due to time synchronization
        if force_update or abs(now - self._last_update) > 0.3:
            self._last_update = now
            for index in range(self._NR_OF_PHASES):
                if self._leds[index] != self._prev[index]:
                    self._prev[index] = self._leds[index] & (self.BLINK - 1)  # Don't copy the blink bit
                    # TODO: turn led on or off depending on blink bit and color setting
                    print('LED %d = %d' % (index,
                                           self._prev[index] if self._leds[index] & self.BLINK == 0 or self._blink_on else 0))

            self._blink_on = not self._blink_on

state = _Status()
