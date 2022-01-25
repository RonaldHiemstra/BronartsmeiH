"""Module to communicate with a MQTT server.

usage:
    from config import Config
    network_config = Config('network_config.json')
    mqttServer = MQTTClient('192.168.1.1', 'test', network_config.get('ssid'), network_config.get('__password'))
    try:
        asyncio.run(mqttServer.run())
    finally:
        asyncio.new_event_loop()
"""
import json
try:
    from typing import Callable, Dict, Optional  # to please lint...
except ImportError:
    ...
import machine
import ubinascii
import uasyncio as asyncio

import mqtt_as.mqtt_as as mqtt_as


class MQTTClient:
    """MQTT client to publish sensor measurements to a MQTT server."""

    def __init__(self, server_ip: str, base_topic: str, ssid: str, wifi_pw: str) -> None:
        mqtt_as.config['server'] = server_ip
        mqtt_as.config['ssid'] = ssid
        mqtt_as.config['wifi_pw'] = wifi_pw
        mqtt_as.config['subs_cb'] = self.callback
        mqtt_as.config['connect_coro'] = self.conn_han
        self.base_topic = base_topic
        self.unique_id = ubinascii.hexlify(machine.unique_id()).decode('utf-8')

        mqtt_as.MQTTClient.DEBUG = True  # Optional: print diagnostic messages
        self.client: mqtt_as.MQTTClient = mqtt_as.MQTTClient(mqtt_as.config)
        self._data_available = asyncio.Event()  # Triggered by put, tested by get
        self.topics: Dict[str, Optional[Dict]] = dict()  # sensor name -> state_topic to publish
        self.callbacks: Dict[str, Callable[..., None]] = dict()

    def callback(self, topic, msg, retained):
        """Handle messages received from subscribed topics."""
        #  (TODO: respond to requests).
        print((topic, msg, retained))
        requests = json.loads(msg)
        print(requests)
        for device, message in requests.items():
            if device in self.callbacks:
                try:
                    self.callbacks[device](message)
                except Exception as ex:
                    print(f'ERROR: MQTT({topic}, {msg}, {retained}): {ex}')

    async def conn_han(self, client: mqtt_as.MQTTClient):
        """Subscribe to config change requests."""
        await client.subscribe(f'{self.base_topic}/config', 1)

    async def run(self):
        """Run the client.
        Publish measurements and sensor configuration.
        """
        await self.client.connect()

        # At start, publish all configurations before publishing the values
        for sensor in self.topics:
            message = self.topics[sensor]
            if sensor.endswith('_home') and message is not None:
                self.topics[sensor] = None
                print(f'MQTT.publish({message})')
                await self.client.publish(**message)
        while True:
            # If WiFi is down the following will pause for the duration.
            await self._data_available.wait()
            for sensor in self.topics:
                message = self.topics[sensor]
                if message is not None:
                    self.topics[sensor] = None
                    print(f'MQTT.publish({message})')
                    await self.client.publish(**message)

    def add_device(self, sensor_name: str, device_class: str,
                   unit: Optional[str] = None, callback: Optional[Callable[..., None]] = None):
        """Add a new sensor."""
        assert self.topics.get(
            sensor_name + '_home') is None, f'{sensor_name} is already present. Sensor names in Home Assistant should be unique!'
        if callback is not None:
            self.callbacks[sensor_name] = callback
        sensor_id = sensor_name.replace(' ', '_')
        state_topic = f'{self.base_topic}/{sensor_id}'
        msg_info = dict(name=f'{sensor_name}',
                        unique_id=f'{self.unique_id}_{sensor_id}',
                        state_topic=state_topic,
                        #value_template=f'{{ value_json }}',
                        device=dict(name=f'{self.base_topic}',
                                    identifiers=[f'{self.unique_id}'])
                        )
        if unit is not None:
            msg_info['unit_of_measurement'] = unit

        if device_class in ['temperature']:
            msg_info['device_class'] = device_class
            topic = f'homeassistant/sensor/{self.unique_id}/{sensor_id}/config'
        elif device_class in ['outlet']:
            msg_info['payload_off'] = 'OFF'
            msg_info['payload_on'] = 'ON'
            topic = f'homeassistant/switch/{self.unique_id}/{sensor_id}/config'
        else:
            msg_info['device_class'] = device_class
            topic = f'homeassistant/device_automation/{self.unique_id}/{sensor_id}/config'

        self.topics[sensor_name + '_home'] = dict(topic=topic,
                                                  msg=json.dumps(msg_info) + ' ',
                                                  retain=True)
        self._data_available.set()  # Schedule waiting tasks
        self._data_available.clear()

    def publish(self, **measurements) -> None:
        """Publish data of previously configured devices.
        Note: devices should have been registered using add_device() to be visible in Home Assistant.
        """
        for sensor_name, value in measurements.items():
            if (sensor_name + '_home') not in self.topics:
                print(f'sensor "{sensor_name}" is not known in HomeAssistant')
                self.topics[sensor_name + '_home'] = None  # Only log once
            sensor_id = sensor_name.replace(' ', '_')
            state_topic = f'{self.base_topic}/{sensor_id}'

            self.topics[sensor_name] = dict(topic=state_topic,
                                            msg=str(value))
            self._data_available.set()  # Schedule waiting tasks
            self._data_available.clear()
