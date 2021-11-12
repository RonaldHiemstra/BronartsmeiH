# BronartsmeiH

Hardware and software development for BronartsmeiH brewery

## Versions

Brönald#3 - Lockdown
Brönald#4 - Vier De Bier

## Development environment

Configure [Visual Studio code](devenv.md) for development.

## Hardware components

[Used hardware](hardware/README.md)

## Kettle Control

### Current functionality

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

### Future functionality

* Publish data to MQTT server
* webserver
  * Configure and select recipes
  * Calibrate the measured temperature (on the fly)
* control threads
  * log measured temperature to MQTT server

Interesting features to implement:

* [Dynamically create a HTML element, if a new unknown entity is pushed](https://www.javascripttutorial.net/javascript-dom/javascript-createelement/)
