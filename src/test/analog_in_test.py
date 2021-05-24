"""Test the analog_in module.

>>> import analog_in_test
>>> import logging
>>> analog_in_test.test(logging.INFO)
12092870 ticks   fridge temperature: 20.95      kettle temperature: 21.17       _spare.temperature: -273.15
"""
import logging
import time

from config import Config
import analog_in


def test(log_level=logging.DEBUG):
    """Test the Ntc class returned by the analog_in function."""
    logging.basicConfig(level=log_level)

    hardware_config = Config('hardware_config.json')
    t_kettle = analog_in.analog_in('kettle temperature', '&deg;C', hardware_config=hardware_config)
    t_fridge = analog_in.analog_in('fridge temperature', '&deg;C', hardware_config=hardware_config)
    t_spare = analog_in.analog_in('_spare.temperature', '&deg;C', hardware_config=hardware_config)

    while True:
        result = list()
        start = time.ticks_cpu()  # pylint: disable=no-member
        for temperature in (t_fridge, t_kettle, t_spare):
            try:
                result.append('%s: %.2f' % (temperature.device_name, temperature.get()))
            except ValueError:
                result.append('%s: #NA' % (temperature.device_name, ))
        duration = time.ticks_diff(time.ticks_cpu(), start)  # pylint: disable=no-member
        print(duration, 'ticks\t', '\t'.join(result))
        time.sleep(1)
