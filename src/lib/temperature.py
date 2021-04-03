"""File providing support to read and calibrate temperature measurements."""
from statistics import mean, stdev
from machine import ADC, Pin, I2C
import uasyncio as asyncio
import ads1x15

from calibration import Calibration
from status import state


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


class TemperatureBase():
    """Abstract base class to measure the temperature.

    The actual temperature is measured in an asynchronous loop.
    The retrieved temperature will be the predicted temperature over the past period of time.

    The derived class must implement a '_read()' method that returns the raw ADC value.
    """

    def __init__(self, calibration, period, interval=0.2):
        """Constructor.
        @param period   The duration to measure. [s]
        @param interval Issue a measurement at every interval. [s]
        """
        self.calibration = calibration
        self.measurements = list()
        self.period = period
        self.interval = interval
        for _ in range(3):
            # make sure some values are present to calculate averages
            self.measurements.append(self._read())
        loop = asyncio.get_event_loop()
        loop.create_task(self._collect())

    def _read(self):
        """Read the raw value."""

    async def _collect(self):
        """Collect the temperature measurements."""
        pending = max(1, self.period / self.interval)

        while True:
            if pending:
                pending -= 1
            else:
                self.measurements.pop(0)  # remove the first measurement
            self.measurements.append(self._read())
            await asyncio.sleep(self.interval)

    def get(self, estimate=0):
        """Get the current temperature."""
        # TODO: do a linefit through the measurements and extrapolate to estimate the value after 'estimate' seconds
        raw = mean(self.measurements)
        nr_of_measurements = len(self.measurements)
        slope, intercept = best_fit_slope_and_intercept(list(range(nr_of_measurements)), self.measurements)
        #logging.debug('slope: %.1f, intercept: %.1f' % (slope, intercept))
        predicted_temp = self.calibration.get(intercept + slope * (nr_of_measurements + (estimate / self.interval)))
        temperature = self.calibration.get(raw)
        state.set_info('Temperature',
                       '%.1f (raw temp: %.1f, stdev: %.2f); predicted: %.1f' % (temperature, raw, stdev(self.measurements),
                                                                                predicted_temp))
        return predicted_temp

    def get_calibrated_details_page(self, temperature_variable_name):
        """Get a webpage body containing details about the current measured temperature."""
        measurements = self.measurements.copy()
        raw = mean(measurements)
        return '''\
<p>Temperature measurement over past {period}s:</p>
<table>
  <tr><td>temperature:</td><td>{temperature:.1f} &deg;C</td></tr>
  <tr><td>min:</td><td>{min:.1f} &deg;C</td></tr>
  <tr><td>max:</td><td>{max:.1f} &deg;C</td></tr>
  <tr><td>raw:</td><td>{raw:.1f}</td></tr>
  <tr><td>raw stdev:</td><td>{stdev:.1f}</td></tr>
</table>
<p><form action="/calibration" method="get">
  <label for="temperature">Current temperature:</label>
  <input type="number" step="0.1" id="{variable}" name="{variable}" value="{temperature:.1f}">
  <input type="submit" formmethod="get" value="Write calibrated temperature">
</form></p>
'''.format(period=self.period,
           temperature=self.calibration.get(raw),
           min=self.calibration.get(min(measurements)),
           max=self.calibration.get(max(measurements)),
           raw=raw,
           stdev=stdev(self.measurements),
           variable=temperature_variable_name)

    def set(self, calibrated):
        """Calibrate the current temperature.

        @param calibrated  The actual measured temperature (measured by a calibrated thermometer).
        """
        self.calibration.set(int(mean(self.measurements)), calibrated)


class TemperatureESP32(TemperatureBase):
    """Class to measure the temperature using an ADC on the ESP32."""
    # This ADC is not very accurate, so it probably is not possible to control within 1 deg C (+/- 0.5).
    # But we need some value here...
    histeresis: float = 0.5

    def __init__(self, pin=32, period=15.0, interval=0.2):
        """Constructor.
        @param period   The duration to measure. [s](The sensor is very noisy :( )
        @param interval Issue a measurement at every interval. [s]
        """
        self.adc = ADC(Pin(pin))
        self.adc.atten(ADC.ATTN_11DB)  # set 11dB input attenuation (voltage range roughly 0.0v - 3.6v)
        super().__init__(calibration=Calibration('/data/temp_cal_esp-%d.json' % pin, 4096, -10, 250),
                         period=period, interval=interval)

    def _read(self):
        """Read the raw value."""
        # A new "machine.ADC.read_u16()" method is defined and implemented on stm32, esp8266, esp32 and nrf ports,
        # providing a consistent way to read an ADC that returns a value in the range 0-65535.
        # This new method should be preferred to the existing "ADC.read()" method.
        return self.adc.read(0)


class TemperatureADS1115(TemperatureBase):
    """Class to measure the temperature using an ADC on the ADS1115."""
    # This ADC is quite accurate, so it should be possible to control within .1 deg C (+/- 0.05)
    histeresis: float = 0.05

    def __init__(self, scl_pin=22, sda_pin=21, period=1.0, interval=0.2):
        """Constructor.
        @param period   The duration to measure. [s](The sensor is very noisy :( )
        @param interval Issue a measurement at every interval. [s]
        """
        i2c = I2C(scl=Pin(scl_pin), sda=Pin(sda_pin))
        assert 0x48 in i2c.scan()
        self.adc = ads1x15.ADS1115(i2c, 0x48)
        super().__init__(calibration=Calibration('/data/temp_cal_ads1115-%02d%02d.json' % (scl_pin, sda_pin), 32768, -10, 250),
                         period=period, interval=interval)

    def _read(self):
        """Read the raw value."""
        return self.adc.read(0)
