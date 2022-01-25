"""Module controlling the temperature of the kettle.

TODO: rename this to temperature_control... This module could also be used for controlling the temperature of the fridge!
"""
from recipe import Recipe
import uasyncio as asyncio
from switch import PowerSwitch
from temperature import TemperatureBase


class KettleControl():
    """Control the brewing kettle."""

    def __init__(self, temperature: TemperatureBase, heater: PowerSwitch, recipe: Recipe, interval=0.5):
        """Constructor.
        params:
            temperature   Temperature measurement device.
            heater        Heater switch.
            recipe        Brewing recipe.
            interval      Frequency to check recipe and temperature every [s].
        """
        self.temperature = temperature
        self.heater = heater
        self.recipe = recipe
        self.interval = interval
        self.manual_control = False
        self.manual_target_temperature = None

    async def run(self):
        """Control the temperature of the brewing kettle."""
        while True:
            temperature = self.temperature.get()

            # DEBUG: using full automation...
            if self.manual_control:
                target_temperature = self.manual_target_temperature
            else:
                target_temperature = self.recipe.get_target_temperature(temperature)

            if target_temperature is not None:
                if temperature < target_temperature:
                    if not self.heater.state:
                        self.heater.turn_on()
                elif temperature > target_temperature:
                    if self.heater.state:
                        self.heater.turn_off()
            await asyncio.sleep(self.interval)
