# Kettle control

## Hardware

### Hothap Grill thermometer

[Hothap Grill thermometer spare sensor 6.5 inch, BBQ roasting thermometer grill thermometer probe waterproof](https://www.amazon.nl/dp/B0865L3K7N/ref=pe_19967891_404437601_TE_item?language=en_GB)

1. High-quality food grade stainless steel probe compatible with the digital meat thermometer Maveric BB-22.
2. This kitchen food thermometer is designed for high temperatures and can withstand temperatures up to 380 °C.
3. Cooking thermometer probe length: 166 mm (6 1/2 inches), hybrid probe: monitor meat or ambient temperature (smoker / grill). Cable length of the digital thermometer probe cable: 40 inch stainless steel grid cable.
4. Waterproof thermometer hybrid probe replacement for family EAAGD.
5. 6.5 inch thermopro replacement probe made of food grade stainless steel temperature probe, also for Thermopro Eagd.

![Hothap Grill thermometer](./images/518WUiv-04L._AC_SL1024_.jpg)

Resistance per temperature:

| kohm | degC |
| --- | --- |
| 7 | 100 |
| 105 | 24 |
| 255 | 6 |

### ESP32 devkitC V4

[Documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/hw-reference/modules-and-boards.html#esp32-devkitc-v4)

![functional overview](./images/esp32-devkitc-functional-overview.jpg)

#### ADC (analog to digital conversion)

On the ESP32 ADC functionality is available on Pins 32-39. Note that, when using the default configuration, input voltages on the ADC pin must be between 0.0v and 1.0v (anything above 1.0v will just read as 4095). Attenuation must be applied in order to increase this usable voltage range.

Use the machine.ADC class:

``` python
from machine import ADC

adc = ADC(Pin(32))          # create ADC object on ADC pin
adc.read()                  # read value, 0-4095 across voltage range 0.0v - 1.0v

adc.atten(ADC.ATTN_11DB)    # set 11dB input attenuation (voltage range roughly 0.0v - 3.6v)
adc.width(ADC.WIDTH_9BIT)   # set 9 bit return values (returned range 0-511)
adc.read()                  # read value using the newly configured attenuation and width
```

ESP32 specific ADC class method reference:

`ADC.atten(attenuation)`

This method allows for the setting of the amount of attenuation on the input of the ADC. This allows for a wider possible input voltage range, at the cost of accuracy (the same number of bits now represents a wider range). The possible attenuation options are:

* ADC.ATTN_0DB: 0dB attenuation, gives a maximum input voltage of 1.00v - this is the default configuration
* ADC.ATTN_2_5DB: 2.5dB attenuation, gives a maximum input voltage of approximately 1.34v
* ADC.ATTN_6DB: 6dB attenuation, gives a maximum input voltage of approximately 2.00v
* ADC.ATTN_11DB: 11dB attenuation, gives a maximum input voltage of approximately 3.6v

### RaspberryPi running DietPi

[Download the DietPi image](https://dietpi.com/) and install on the RaspberryPi.

Use a RaspberryPi to show the logging of the ESP on a display.

set `CONFIG_SERIAL_CONSOLE_ENABLE=1` in `/boot/dietpi.txt` to enable serial communication with the ESP

Find the serial tty, list its settings and open a session:

```sh
dmesg | grep tty
stty -f /dev/ttyUSB0
screen /dev/ttyUSB0 115200,sc8
```

To exit a screen session: Press ctrl-A,k

## Check this

Bunch of interesting links: <http://awesome-micropython.com/>

ESP32 links:

* <https://github.com/lemariva/uPyLoRaWAN>
* <https://github.com/tve/mqboard> or <https://github.com/miketeachman/micropython-thingspeak-mqtt-esp8266>
* <https://github.com/tve/esp32-backtrace>

VSCode links:

* <https://github.com/BradenM/micropy-cli>
* <https://github.com/Josverl/micropython-stubber>
* <https://marketplace.visualstudio.com/items?itemName=dphans.micropython-ide-vscode>
* <https://marketplace.visualstudio.com/items?itemName=SWC-Fablab.micropython-replink>

Shell on host:

* <https://github.com/dhylands/rshell>
* <https://github.com/scientifichackers/ampy>
* <https://github.com/wendlers/mpfshell>
* <https://micropython.org/webrepl>

## Board info

<https://randomnerdtutorials.com/esp32-pinout-reference-gpios/>
