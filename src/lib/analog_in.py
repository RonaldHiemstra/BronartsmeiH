"""File providing support to read and calibrate analog input measurements."""
import logging

from machine import ADC, Pin, I2C
import ads1x15

LOG = logging.getLogger('analog_in')
LOG.setLevel(logging.INFO)

class Adc:
    """Base class for a single analog to digital converter."""

    def read(self):
        """Read the raw value."""
        raise NotImplementedError


class AnalogInESP32(Adc):
    """Class to measure the analog input using an ADC on the ESP32."""
    # This ADC is not very accurate, so it probably is not possible to control within 1 deg C (+/- 0.5).
    # But we need some value here...
    histeresis: float = 0.5

    def __init__(self, device_config: dict, pin: int, *, period: float = 15.0, interval: float = 0.2):
        """Constructor.
        @param period   The duration to measure. [s](The sensor is very noisy :( )
        @param interval Issue a measurement at every interval. [s]
        """
        self.ref_pin = int(device_config.get('u_ref.pin'))
        self.ref_gain = float(device_config.get('u_ref.gain'))
        self.adc = ADC(Pin(pin))
        self.adc.atten(ADC.ATTN_11DB)  # set 11dB input attenuation (voltage range roughly 0.0v - 3.6v)
        self.device_unit = "&deg;C"
        self.period = period
        self.interval = interval

    def read(self):
        """Read the raw value."""
        # A new "machine.ADC.read_u16()" method is defined and implemented on stm32, esp8266, esp32 and nrf ports,
        # providing a consistent way to read an ADC that returns a value in the range 0-65535.
        # This new method should be preferred to the existing "ADC.read()" method.
        return dict(raw=self.adc.read(0),
                    ref_raw=65535)


class Ads1115(Adc):
    """Class to measure the ADC value of a single pin of the ADS1115.
    Note: The ADS1115 is able to measure up to 4 analog inputs.
    """
    # This ADC is very accurate (with a stable power supply)
#    histeresis: float = 0.01
    __adc_s = dict()

    class _Ads1115():
        """The ADS1115 supports up to 4 16-bit analog inputs.
        The last input can be used as a reference measurement.
        """
        UNUSED_PIN = 4

        def __init__(self, ads1115_config: dict):
            """Initialize the ADS1115.
            It is controlled by I2C and requires the scl and sda pins in the hardware configuration.
            """
            scl_pin = int(ads1115_config.get('SDA').split('.')[-1])  # ADS.sda is connected to ESP.scl
            sda_pin = int(ads1115_config.get('SCL').split('.')[-1])  # ADS.scl is connected to ESP.sda
            i2c = I2C(scl=Pin(scl_pin), sda=Pin(sda_pin))
            if 0x48 not in i2c.scan():
                LOG.error('ADS1115 not detected!')
            else:
                self.adc = ads1x15.ADS1115(i2c, 0x48)
            self.active_pins = set()
            self.pins_read = list(range(4))
            self.values = list(0 for _ in range(5))

        def read(self, pin, ref_pin=UNUSED_PIN, ref_gain=0):
            """Read the raw values for all used pins."""
            if ref_pin < self.UNUSED_PIN:
                assert pin != ref_pin
                self.active_pins.add(ref_pin)
            if pin in self.pins_read or pin not in self.active_pins:
                self.active_pins.add(pin)
                self.pins_read = [pin]
                for pin_to_read in self.active_pins:
                    self.values[pin_to_read] = self.adc.read(channel1=pin_to_read)
            else:
                self.pins_read.append(pin)
            return dict(raw=self.values[pin],
                        ref_raw=self.values[ref_pin] * ref_gain)

    def __init__(self, device_config: dict, pin: int):
        if device_config.get('device') != 'ADS1115':
            raise TypeError('invalid config')
        ads1115id = '{SDA}_{SCL}'.format(**device_config)
        if ads1115id not in Ads1115.__adc_s:
            Ads1115.__adc_s[ads1115id] = Ads1115._Ads1115(device_config)
        self.adc = Ads1115.__adc_s[ads1115id]
        self.ref_pin = int(device_config.get('u_ref.pin'))
        self.ref_gain = float(device_config.get('u_ref.gain'))
        self.pin = pin

    def read(self):
        """Read the analog input value."""
        return self.adc.read(self.pin, self.ref_pin, self.ref_gain)
