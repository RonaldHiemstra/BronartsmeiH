# This file is executed on every boot (including wake-boot from deepsleep)
import gc
import time
import esp
import network
import webrepl
from config import Config


esp.osdebug(None)
gc.collect()

system_config = Config('system_config.json')

station = network.WLAN(network.STA_IF)
station.active(True)
station.connect(system_config.get('ssid'), system_config.get('__password'))
while not station.isconnected():
    time.sleep(0.5)
    # TODO: start as accesspoint if no connection can be made within 1 minute...
print('WiFi Connection:', station.ifconfig())

webrepl.start()
