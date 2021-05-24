# BronartsmeiH

Hardware and software development for BronartsmeiH brewery

## Initial version

Used to brew my first self composed beer: Brönald #3 - Lockdown

## Development environment

Configure [Visual Studio code](devenv.md) for development.

## Hardware components

[Used hardware](hardware/README.md)

## Kettle Control

Current functionality:

* webserver
  * Show current time
  * Show current temperatures (kettle, fridge and environment)
  * Define list of target temperatures (recipe)
    * for a specified duration
* heater control thread
  * check to update target temperature (according to the recipe)
  * control heater of the kettle (check measured temperature against target temperature)
* fridge control thread
  * control fridge (cooling and heating) (check measured temperature against target temperature)

Future functionality:

* webserver
  * Configure and select recipes
  * Reenable: Calibrate the measured temperature (on the fly)
* control threads
  * log measured temperature to MQTT server
