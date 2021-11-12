"""File providing support to read and calibrate temperature measurements."""
import logging
import math
from statistics import mean, stdev
import sys
from machine import Pin
import uasyncio as asyncio
import dht

from analog_in import Ads1115, AnalogInESP32

LOG = logging.getLogger('temperature')
LOG.setLevel(logging.INFO)

def best_fit_slope_and_intercept(x_points, y_points):
    """Line of best fit for a set of points."""
    # https://stackoverflow.com/questions/22239691/code-for-best-fit-straight-line-of-a-scatter-plot-in-python
    x_bar = sum(x_points)/len(x_points)
    y_bar = sum(y_points)/len(y_points)
    nr_of_points = len(x_points)  # or len(y_points)
    num = sum([xi*yi for xi, yi in zip(x_points, y_points)]) - nr_of_points * x_bar * y_bar
    de_num = sum([xi**2 for xi in x_points]) - nr_of_points * x_bar**2
    gain = num / de_num
    offset = y_bar - gain * x_bar
    #print('best fit line:\ny = {:.2f} + {:.2f}x'.format(offset, gain))
    return gain, offset


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

    def __init__(self, device_name: str, period: float, interval: float, callback):
        """Constructor.
        @param period   The duration to measure. [s]
        @param interval Issue a measurement at every interval. [s]
        """
        self.device_name = device_name
        self.unit = '&deg;C'
        self.period = period
        self.interval = interval
        self.callback = callback
        initial = self._read()
        # make sure some values are present to calculate averages
        self.measurements = [initial for _ in range(3)]
        loop = asyncio.get_event_loop()
        loop.create_task(self._collect())

    def _read(self):
        """Read the raw value."""

    async def _collect(self):
        """Collect the temperature measurements."""
        pending = max(1, int(self.period / self.interval) - len(self.measurements))
        progress = 0

        while True:
            await asyncio.sleep(self.interval)
            if pending:
                pending -= 1
            else:
                self.measurements.pop(0)  # remove the first measurement
            self.measurements.append(self._read())
            if self.callback is not None:
                progress += self.interval
                if progress > self.period:
                    await self.callback(**{self.device_name: self.get()})
                    progress = 0

    def get(self, estimate=0):
        """Get the current temperature."""
        avg_temperature = mean(self.measurements)
        nr_of_measurements = len(self.measurements)
        slope, intercept = best_fit_slope_and_intercept(list(range(nr_of_measurements)), self.measurements)
        #LOG.debug('slope: %.1f, intercept: %.1f' % (slope, intercept))
        predicted_temp = intercept + slope * (nr_of_measurements + (estimate / self.interval))
        LOG.debug('%s: %.1f (stdev: %.2f); predicted: %.1f',
                  self.device_name, avg_temperature, stdev(self.measurements), predicted_temp)
        return predicted_temp


class Dht22(TemperatureBase):
    """Class to retrieve the temperature (and humidity) from a DHT22 sensor.
    note:
        The minimum interval for DHT22 is 2s.
    """
    def __init__(self, device_name: str, hardware_config: dict, callback):
        sensor_config: dict = hardware_config.get(device_name)
        if sensor_config.get('device') != 'DHT22':
            raise TypeError('invalid config')
        io_device, pin = sensor_config.get('pin').split('.')
        assert io_device == 'ESP', 'Only pins on the ESP are supported to read the DHT22'
        self.dht = dht.DHT22(Pin(int(pin)))
        super().__init__(device_name=device_name, period=15, interval=5, callback=callback)

    def _read(self):
        self.dht.measure()
        return self.dht.temperature()

class Ntc(TemperatureBase):
    """Class to calculate the temperature based on an analog input measurement.

    The analog input measurement is the result of a voltage devision with a NCT and a known resistance.
    """

    def __init__(self, device_name: str, hardware_config: dict, callback):
        sensor_config: dict = hardware_config.get(device_name)
        if sensor_config.get('device') != 'NTC':
            raise TypeError('invalid config')
        probe: dict = hardware_config.get(sensor_config.get('probe'))
        self.r25 = float(probe.get('r25'))
        self.b_value = float(probe.get('b_value'))
        self.r_ref = float(sensor_config.get('r_ref'))

        io_device, pin = sensor_config.get('pin').split('.')
        device_config = hardware_config.get(io_device)
        self.adc = None
        for sensor in (Ads1115, AnalogInESP32):
            try:
                self.adc = sensor(device_config, int(pin))
                break
            except TypeError as ex:
                sys.print_exception(ex)  # pylint: disable=no-member
        assert self.adc is not None, 'Failed to configure %s' % device_name
        super().__init__(device_name=device_name, period=2, interval=0.3, callback=callback)

    def _read(self):
        """Read the temperature."""
        # Read the ADC value and the reference
        raw_measurement = self.adc.read()
        # calculate the NTC resistance:
        # (v_ref - ADC) / R_ref = ADC / NTC => NTC = ADC * Rf / (v_ref - ADC)
        LOG.debug('raw_measurement: %s', raw_measurement)
        LOG.debug('r_ref: %s', self.r_ref)
        LOG.debug('r25: %s', self.r25)
        LOG.debug('b_value: %s', self.b_value)
        try:
            r_ntc = raw_measurement['raw'] * self.r_ref / (raw_measurement['ref_raw'] - raw_measurement['raw'])
            LOG.debug('r_ntc: %s', r_ntc)
            return k2c(1.0 / ((math.log(r_ntc / self.r25)) / self.b_value + (1.0 / c2k(25))))
        except (ValueError, ZeroDivisionError):
            return k2c(0)


def temperature(device_name: str, hardware_config: dict, callback=None):
    """Get an instance to measure the temperature for the given device.

    params:
        callback  Async function which will be called every period of measurements.
    """
    for sensor in (Ntc, Dht22):
        try:
            return sensor(device_name, hardware_config, callback)
        except TypeError:
            pass
    LOG.error('Wrong sensor configuration for %s', device_name)
