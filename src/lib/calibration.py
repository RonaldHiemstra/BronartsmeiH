"""Calibrate a raw value to a calibrated floating point value."""
from collections import OrderedDict

import logging
from config import Config


class Calibration():
    """Convert raw measured values to calibrated floating point values."""

    def __init__(self, calibration_file, steps: int, min_temp: float, max_temp: float):
        """Constructor
        @param calibration_file Filename to store calibration data.
        @param steps            Maximum value 2^ADC_nr_of_bits
        @param min_temp         The estimated minimum temperature (raw value=0).
        @param max_temp         The estimated maximum temperature (raw value=steps-1)
        """
        self._config = Config(calibration_file)
        self._steps = dict()  # Update with _update_steps()
        cal_values = self._config.get()
        self.key_formatter = 't%0{}d'.format(len(str(steps)))
        if cal_values:
            raw_values = sorted(cal_values)
            lowest = raw_values[0]
            highest = raw_values[-1]
            if lowest == self._format_raw(0):
                if cal_values[lowest] != min_temp:
                    logging.warning('lowest temperature is already specified as %f, given %f is ignored',
                                    cal_values[lowest], min_temp)
            elif cal_values[lowest] > min_temp:
                # Set a new (initial) minimum for this sensor
                self._config.set(self._format_raw(0), min_temp)
            else:
                logging.warning('index: %s is lower (%f) than given minimum %f', lowest, cal_values[lowest], min_temp)
            if highest == self._format_raw(steps - 1):
                if cal_values[highest] != max_temp:
                    logging.warning('highest temperature is already specified as %f, given %f is ignored',
                                    cal_values[highest], max_temp)
            elif cal_values[highest] < max_temp:
                # Set a new (initial) maximum for this sensor
                self._config.set(self._format_raw(steps - 1), max_temp)
            else:
                logging.warning('index: %s is higher (%f) than given maximum %f', highest, cal_values[highest], max_temp)
        else:
            self._config.set(self._format_raw(0), min_temp)
            self._config.set(self._format_raw(steps - 1), max_temp)
        self._update_steps()

    def _format_raw(self, raw_value: int) -> str:
        """Convert the raw_value to a json key_value."""
        return self.key_formatter % raw_value

    def _update_steps(self):
        # make config sorted
        self._steps = OrderedDict([(int(key[1:]), value)
                                   for (key, value) in sorted(self._config.get().items(), key=lambda t: t[0])])
        keys = list(self._steps)
        self._min_raw = keys[0]
        self._max_raw = keys[-1]

    def get(self, raw_value: int) -> float:
        """Convert the given raw value to a calibrated temperature value."""
        lower = self._min_raw
        higher = self._max_raw
        for stored in self._steps:
            if stored <= raw_value:
                lower = stored
            elif stored > raw_value:
                higher = stored
                break
        logging.debug('lower: %s, measured: %s, higher: %s', lower, raw_value, higher)
        if higher == lower:
            return self._steps[lower]
        return self._steps[lower] + ((raw_value - lower) * (self._steps[higher] - self._steps[lower]) / (higher - lower))

    def set(self, raw_value: int, calibrated_value):
        """Update the calibration matrix with the given raw_value that represents the calibrated_value."""
        self._config.set(self._format_raw(raw_value), float(calibrated_value))
        self._update_steps()

    def remove(self, raw_value: int):
        """Remove the given calibrated value from the calibration matrix."""
        self._config.remove(self._format_raw(raw_value))
        self._update_steps()

    def web_page(self, temperature_variable_name: str):
        """Get a webpage body containing the stored calibration values."""
        html = '<table>\n'
        prev_value = -273
        html += '<tr><th>raw value</th><th>actual temperature [&deg;C]</th><th>delete</th></tr>\n'
        max_raw = list(self._steps)[-1]
        for (key, value) in self._steps.items():
            remove = ''
            if value < prev_value:
                style = ' style="color:red"'
            else:
                prev_value = value
                style = ''
            if key in [0, max_raw]:
                remove = '-'
            else:
                remove = '<b><a href="/calibration?%s.calibration.remove=%d">x</a></b>' % (temperature_variable_name, key)
            html += '<tr %s><td>%d</td><td>%s</td><td>%s</td></tr>\n' % (style, key, value, remove)
        html += '\n</table>\n'
        return html
