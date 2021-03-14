# Development environment

## Support in VS Code

This workspace is inspired by "[Josverl/micropython-stubber](https://github.com/Josverl/micropython-stubber#boost-micropython-productivity-in-vscode): Generate and use stubs for different micropython firmwares to use with vscode and/or pylint"

* Clone <https://github.com/Josverl/micropython-stubs> in ../github/micropython-stubs
* Clone <https://github.com/robert-hh/ads1x15.git> in ../github/ads1x15
* Clone <https://github.com/RonaldHiemstra/picoweb/releases/tag/Br%C3%B6nald%233> in ../picoweb
* Clone <https://github.com/micropython/webrepl> in ../github/webrepl

## Prepare a micropython development environment

Create a python [anaconda](https://www.anaconda.com/products/individual) environment with support for:

* [esptool](https://github.com/espressif/esptool/)
* [mpfshell-lite](https://github.com/junhuanchen/mpfshell-lite/blob/master/English.md)

```bat
conda create -n mpydev python pylint autopep8
conda activate mpydev
pip install esptool mpfshell-lite
```

## Getting started with MicroPython on the ESP

Download firmware from [MicroPython for ESP32](https://micropython.org/download/esp32/)

Install the firmware:

```bat
esptool erase_flash
esptool --chip esp32 write_flash -z 0x1000 esp32-idf4-20210202-v1.14.bin
```

### Initial configuration

Open a serial connection to the ESP32 and get started.

``` python
import network
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.scan()                             # Scan for available access points
sta_if.connect("<AP_name>", "<password>") # Connect to an AP
sta_if.isconnected()                      # Check for successful connection
```

Enable webrepl

``` python
import webrepl_setup
```

### Upload BronartsmeiH project

Run the command script `upload_all.cmd` to upload all required files to the board.

#### Connect to webrepl

To manually interact with the device, use webrepl to upload files and run python code in the web-shell:

<http://micropython.org/webrepl/#192.168.1.31:8266/>
