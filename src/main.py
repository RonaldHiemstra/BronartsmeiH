"""Script to automate the brewing process.

Functionality:
* Publish sensor measurements to a MQTT server.
* Measure the environment temperature (TODO: and humidity).
* TODO: Measure the kettle temperature.
* TODO: Show the current kettle temperature.
* TODO: Show the kettle heater state.
* TODO: Add recipe handling for the beer to brew.
* TODO: Support control switch to acknowledge manual actions in the brew process.
* TODO: Control the kettle temperature.
* TODO: Add fridge control.

"""
try:
    from typing import Callable, List, Union  # to please lint...
except ImportError:
    ...
import uasyncio as asyncio
import micropython

micropython.alloc_emergency_exception_buf(100)
from kettle import KettleControl
from switch import PowerSwitch
from mqtt import MQTTClient
from temperature import temperature as TemperatureSensor
from recipe5 import get_recipe

from config import Config


class DeployCallbacks:
    """Deploy a callback to multiple callback routines."""

    def __init__(self, callbacks: List[Callable[..., None]]) -> None:
        self.callbacks = callbacks

    def __call__(self, **measurements):
        for callback in self.callbacks:
            callback(**measurements)


class ReduceCallbacks:
    """Collect measurements and forward the average of the measurements once per `nr_of_measurements`."""

    def __init__(self, sensor_name: str, callback: Callable[..., None], nr_of_measurements: int = 1) -> None:
        self.sensor_name = sensor_name
        self.callback = callback
        self.index = 0
        self.measurements = [0.0 for _ in range(max(1, nr_of_measurements))]

    def __call__(self, **measurements):
        """Collect the measurement."""
        for sensor_name, value in measurements.items():
            if sensor_name != self.sensor_name:
                print(f'ERROR: sensor "{sensor_name}" was not expected!')
                continue
            self.measurements[self.index] = value
            self.index += 1
            if self.index >= len(self.measurements):
                # TODO: use mode to remove outliers (measurement errors)
                self.callback(**{self.sensor_name: sum(self.measurements) / len(self.measurements)})
                self.index = 0

    def set_nr_of_measurements(self, value: Union[int, float]):
        """Change the number of measurements.
        Note: all collected measurements will be flushed.
        """
        self.index = 0
        self.measurements = [0.0 for _ in range(max(1, int(value)))]

async def main():
    """Main brewery task.

    This task manely creates the different tasks for the brewery to operate and monitors the state of those tasks.
    """
    network_config = Config('network_config.json')
    config = Config('config.json')

    mqtt_server = MQTTClient(config['mqtt']['server_ip'], config['project_name'],
                             ssid=network_config['ssid'], wifi_pw=network_config['__password'])

    sensor_name = 'environment temperature'
    mqtt_server.add_device(sensor_name, 'temperature', '°C')
    reduce_environment_temperature = ReduceCallbacks(sensor_name, callback=mqtt_server.publish)
    environment_temperature_sensor = TemperatureSensor(sensor_name, hardware_config=config['hardware'],
                                                       callback=reduce_environment_temperature)
    reduce_environment_temperature.set_nr_of_measurements(10 / environment_temperature_sensor.interval)

    sensor_name = 'kettle temperature'
    mqtt_server.add_device(sensor_name, 'temperature', '°C')
    reduce_kettle_temperature = ReduceCallbacks(sensor_name, callback=mqtt_server.publish)
    kettle_temperature_sensor = TemperatureSensor(sensor_name, hardware_config=config['hardware'],
                                                  callback=reduce_kettle_temperature)
    reduce_kettle_temperature.set_nr_of_measurements(10 / kettle_temperature_sensor.interval)

    actuator_name = 'kettle switch'
    mqtt_server.add_device(actuator_name, 'outlet')
    recipe = get_recipe(callback=mqtt_server.publish)
    mqtt_server.add_device('target temperature', 'temperature', '°C', recipe.set_target_temperature) # TODO: this is related to get_recipe...
    mqtt_server.add_device('recipe', 'actions', None)
    mqtt_server.add_device('recipe_ack_action', 'action', None, recipe.ack_action)
    mqtt_server.add_device('recipe_stage', 'action', None, recipe.set_stage)
    kettle_control = KettleControl(kettle_temperature_sensor,
                                   PowerSwitch(actuator_name, int(config['hardware']['kettle switch']),
                                               callback=mqtt_server.publish),
                                   recipe)

    asyncio.create_task(mqtt_server.run())
    asyncio.create_task(environment_temperature_sensor.run())
    asyncio.create_task(kettle_temperature_sensor.run())
    asyncio.create_task(kettle_control.run())

    uptime = 0
    while True:
        await asyncio.sleep(10)
        uptime += 10
        uptime_str = f'{uptime//3600}:{(uptime//60)%60:02}:{uptime%60:02}'
        mqtt_server.publish(uptime=uptime_str)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()
