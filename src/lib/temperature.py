"""File providing support to read and calibrate temperature measurements."""
#import logging
import math
import time
try:
    from typing import Callable, Dict, Optional
except ImportError:
    ...
from machine import Pin
import uasyncio as asyncio
import dht

from analog_in import Adc, Ads1115, AnalogInESP32

#LOG = logging.getLogger('temperature')
# LOG.setLevel(logging.INFO)


class UnsupportedException(Exception):
    """Specified temperature sensor type is not (yet) supported."""


def k2c(kelvin):
    """Convert a temperature in Kelvin to Celsius."""
    return kelvin - 273.15


def c2k(celsius):
    """Convert a temperature in Celsius to Kelvin."""
    return celsius + 273.15


class TemperatureBase():
    """Abstract base class to measure the temperature.

    The actual temperature is measured in an asynchronous loop.
    The retrieved temperature will be the predicted temperature.

    The derived class must implement a '_read()' method that returns the measured temperature.
    """

    def __init__(self, device_name: str, interval: float, callback: Callable[..., None]) -> None:
        """Constructor.

        params:
            interval: The interval to measure. [s]
            callback: Callable[[float], None]  Function which will be called every measurement.
        """
        self.device_name = device_name
        self.unit = '&deg;C'
        self.interval = interval
        self.callback = callback
        self.measurement: float = -273.15

    async def _read(self) -> float:
        """Read the raw value."""
        raise NotImplementedError

    async def run(self):
        """Collect and publish the temperature measurements."""
        while True:
            await asyncio.sleep(self.interval)

            self.measurement = await self._read()
            if self.callback is not None:
                self.callback(**{self.device_name: self.measurement})

    def get(self):
        """Get the current temperature."""
        return self.measurement


class Dht22(TemperatureBase):
    """Class to retrieve the temperature (and humidity) from a DHT22 sensor.
    note:
        The minimum interval for DHT22 is 2s.
    """

    def __init__(self, device_name: str, hardware_config: Dict[str, Dict[str, str]], callback: Callable[..., None]):
        """
        params:
            callback: Callable[[float], None]  Function which will be called every measurement.
        """
        sensor_config = hardware_config[device_name]
        if sensor_config.get('device') != 'DHT22':
            raise TypeError('invalid config')
        io_device, pin = sensor_config['pin'].split('.')
        assert io_device == 'ESP', 'Only pins on the ESP are supported to read the DHT22'
        self.dht = dht.DHT22(Pin(int(pin)))
        # The minimal interval for the DHT22 is 2s (according to the spec).
        self._start = time.ticks_ms()
        super().__init__(device_name=device_name, interval=2, callback=callback)

    async def _read(self):
        # DHT22 currently does not support asyncio...
        # Note:("HTU21D temperature/humidity sensor")[https://github.com/peterhinch/micropython-async/blob/master/v3/docs/HTU21D.md]
        # does support asyncio.
        try:
            delay_ms = time.ticks_diff(time.ticks_ms(), self._start)
            if delay_ms < (self.interval * 1e3):
                print(f'Additional sleep_ms({(self.interval * 1e3) - delay_ms})')
                await asyncio.sleep_ms((self.interval * 1e3) - delay_ms)
            self.dht.measure()
            self._start = time.ticks_ms()
        except OSError as ex:
            # Even with a timeout of 3s, the OSError(E TIMEDOUT) exception is sometimes raised.
            print(f'WARNING: {ex}, returning last known value for "{self.device_name}"')
        temp = self.dht.temperature()
        return temp


class Ntc(TemperatureBase):
    """Class to calculate the temperature based on an analog input measurement.

    The analog input measurement is the result of a voltage devision with a NCT and a known resistance.
    """

    def __init__(self, device_name: str, hardware_config: Dict[str, Dict[str, str]], callback: Callable[..., None]) -> None:
        sensor_config = hardware_config[device_name]
        if sensor_config.get('device') != 'NTC':
            raise TypeError('invalid config')
        probe = hardware_config[sensor_config['probe']]
        self.r25 = float(probe['r25'])
        self.b_value = float(probe['b_value'])
        self.r_ref = float(sensor_config['r_ref'])

        io_device, pin = sensor_config['pin'].split('.')
        device_config = hardware_config.get(io_device)
        self.adc: Optional[Adc] = None
        for sensor in (Ads1115, AnalogInESP32):
            try:
                self.adc = sensor(device_config, int(pin))
                break
            except TypeError as ex:
                print(f'INFO: incompatible "{sensor.__name__}": {ex}')
        assert self.adc is not None, 'Failed to configure %s' % device_name
        super().__init__(device_name=device_name, interval=0.3, callback=callback)

    async def _read(self):
        """Read the temperature."""
        # Read the ADC value and the reference
        raw_measurement = self.adc.read()
        # calculate the NTC resistance:
        # (v_ref - ADC) / R_ref = ADC / NTC => NTC = ADC * Rf / (v_ref - ADC)
        # LOG.debug('raw_measurement: %s', raw_measurement)
        # LOG.debug('r_ref: %s', self.r_ref)
        # LOG.debug('r25: %s', self.r25)
        # LOG.debug('b_value: %s', self.b_value)
        try:
            r_ntc = raw_measurement['raw'] * self.r_ref / (raw_measurement['ref_raw'] - raw_measurement['raw'])
            # LOG.debug('r_ntc: %s', r_ntc)
            return k2c(1.0 / ((math.log(r_ntc / self.r25)) / self.b_value + (1.0 / c2k(25))))
        except (ValueError, ZeroDivisionError):
            return k2c(0)


def temperature(device_name: str, hardware_config: dict, callback: Callable[..., None]) -> TemperatureBase:
    """Get an instance to measure the temperature for the given device.

    params:
        callback: Callable[[float], None]  Function which will be called every measurement.
    """
    for sensor in (Ntc, Dht22):
        try:
            return sensor(device_name, hardware_config, callback)
        except TypeError:
            pass
    raise UnsupportedException(f'Wrong sensor configuration for {device_name}')
