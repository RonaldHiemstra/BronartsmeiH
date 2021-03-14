# BronartsmeiH

Hardware and software development for BronartsmeiH brewery

## Initial version

Used to brew my first self composed beer: Brönald #3 - Lockdown

## Development environment

Configure [Visual Studio code](devenv.md) for development.

## Hardware components

[Used hardware](hardware/README.md)

## Kettle Control

Future functionality:

* webserver
  * Show current time
  * Show current temperature
  * Define list of target temperatures
    * for a specified duration
* control thread (endless loop)
  * log measured temperature to MQTT server
  * check to update target temperature
  * control heater (check measured temperature against target temperature)
