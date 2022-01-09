import uasyncio as asyncio
from switch import PowerSwitch
from temperature import temperature as TemperatureSensor


class KettleControl():
    """Control the brewing kettle."""

    def __init__(self, temperature: TemperatureSensor, heater: PowerSwitch, recipe, interval=0.5, callback=None):
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
        self.callback = callback
        self.manual_control = False
        self.manual_target_temperature = None
        loop = asyncio.get_event_loop()
        loop.create_task(self._control())

    async def _control(self):
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
                        if self.callback:
                            await self.callback(**{self.heater.device_name: 'ON'})
                elif temperature > target_temperature:
                    if self.heater.state:
                        self.heater.turn_off()
                        if self.callback:
                            await self.callback(**{self.heater.device_name: 'OFF'})
            await asyncio.sleep(self.interval)
