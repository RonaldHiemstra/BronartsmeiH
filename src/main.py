"""Script to automate the brewing process for the brewery.

Script includes a hardcoded brewing schedule for Brönald #4 - Vier De Bier.
"""
import gc
import json
import logging
import time

from machine import Pin
import uasyncio as asyncio
import picoweb

from config import Config
from localtime import Localtime
from recipe import Recipe, Stage
import status
from status import state
from temperature import temperature as Temperature

logging.basicConfig(level=logging.INFO, stream=status.logging)
gc.collect()


async def push_event(**event):
    """Push an event.
    @param event  dict where key is a named div in the body and value will be filled in the div.
    """
    await _push_data(event_sinks, json.dumps(event))


MANUAL_CONTROL = 0
TARGET_TEMPERATURE = 21
HIST_GOAL = .05  # accept +/- .05 degC

SYSTEM_CONFIG = Config('system_config.json')
HARDWARE_CONFIG = Config('hardware_config.json')
PROJECT_NAME = SYSTEM_CONFIG.get('project_name', 'BronatrsmeiH')
LOCAL_TIME = Localtime(SYSTEM_CONFIG.get('utc_offset'))

# Get start time after creating the Localtime, because this will change the system time.
START_TIME = time.time()


ENVIRONMENT_TEMPERATURE = Temperature('environment temperature', HARDWARE_CONFIG, push_event)

# duration, target temperature, start time (temperature reached)
RECIPE = Recipe([Stage('Preheat', 0, 65, 'Add malt and cooked oats'),
                 Stage('Maichen phase1', 30 * 60, 63),
                 Stage('Maichen phase2', 15 * 60, 67),
                 Stage('Maichen phase3', 30 * 60, 72),
                 Stage('Maichen phase4', 5 * 60, 77, 'Filter/remove grains'),
                 Stage('Boil phase1', 30 * 60, 100, 'Add first hops'),
                 Stage('Boil phase2', 50 * 60, 100, 'Add rest of hops and sugar'),
                 Stage('Boil phase3', 10 * 60, 100, 'Whirlpool and start cooling'),
                 Stage('Cooling', 0, 20, 'Transfer wort to fermentation vessel and add yeast', False)])


class PowerSwitch():
    """Control the heater of the kettle."""

    def __init__(self, device_name, pin=13):
        self.device_name = device_name
        self.pin = Pin(pin, Pin.OUT)
        self.state = None

    def turn_on(self):
        """Turn the heater on."""
        if self.state is not 1:
            self.state = 1
            self.pin.value(self.state)
            state.set_info(self.device_name, 'ON')

    def turn_off(self):
        """Turn the heater off."""
        if self.state is not 0:
            self.state = 0
            self.pin.value(self.state)
            state.set_info(self.device_name, 'OFF')


HEATER = PowerSwitch('kettle switch', int(HARDWARE_CONFIG.get('kettle switch')))
KETTLE_TEMPERATURE = Temperature('kettle temperature', hardware_config=HARDWARE_CONFIG, callback=push_event)

TARGET_TEMPERATURE = RECIPE.stages[0].temperature
state.set_info('Target temperature', TARGET_TEMPERATURE)


class Kettle():
    """Control the brewing kettle."""

    def __init__(self, temperature: Temperature, heater: PowerSwitch, recipe, interval=0.5, callback=None):
        """Constructor.
        params:
            temperature   Temperature measurement device.
            heater        Heater switch.
            recipe        Brewing recipe.
            interval      Frequency to check recipe and temperature every [s].
        """
        self.temperature = temperature
        self.heater = heater
        self.recipe = recipe
        self.interval = interval
        self.callback = callback
        self.manual_control = False
        self.manual_target_temperature = None
        loop = asyncio.get_event_loop()
        loop.create_task(self._control())

    async def _control(self):
        """Control the temperature of the brewing kettle."""
        while True:
            temperature = self.temperature.get()

            # DEBUG: using full automation...
            if self.manual_control:
                target_temperature = self.manual_target_temperature
            else:
                target_temperature = self.recipe.get_target_temperature(temperature)

            if target_temperature is not None:
                if temperature < target_temperature:
                    if not self.heater.state:
                        self.heater.turn_on()
                        if self.callback:
                            await self.callback(**{self.heater.device_name: 'ON'})
                elif temperature > target_temperature:
                    if self.heater.state:
                        self.heater.turn_off()
                        if self.callback:
                            await self.callback(**{self.heater.device_name: 'OFF'})
            await asyncio.sleep(self.interval)


KETTLE = Kettle(KETTLE_TEMPERATURE, HEATER, RECIPE, callback=push_event)


class Fridge():
    """Control the brewing fridge."""

    def __init__(self, temperature: Temperature, heater: PowerSwitch, cooler: PowerSwitch, interval=10, callback=None):
        """Constructor.
        params:
            temperature   Temperature measurement device.
            heater        Fridge heater switch.
            cooler        Fridge switch.
            interval      Frequency to check recipe and temperature every [s].
        """
        self.temperature = temperature
        self.heater = heater
        self.cooler = cooler
        self.interval = interval
        self.callback = callback
        # FIXME!!!
        # Target temperature for Brönald #4 is 13, but the software crashes very often :(
        # so for now just make sure the fridge is turned on and use the temperature of the fridge itself.
        self.target_temperature = 3
        self.histeresis = 0.5  # constoll within +/- 0.5 degrees
        loop = asyncio.get_event_loop()
        loop.create_task(self._control())

    async def _control(self):
        """Control the temperature of the brewing kettle."""
        while True:
            gc.collect()
            state.set_info('RAM', 'free {} alloc {}'.format(gc.mem_free(), gc.mem_alloc()))
            interval = self.interval
            temperature = self.temperature.get()

            if temperature < self.target_temperature and self.cooler.state:
                self.cooler.turn_off()
                if self.callback:
                    await self.callback(**{self.cooler.device_name: 'OFF'})
                interval = 180  # Don't switch cooler within 3 minutes
            if temperature < (self.target_temperature - self.histeresis) and not self.heater.state:
                self.heater.turn_on()
                if self.callback:
                    await self.callback(**{self.heater.device_name: 'ON'})
            if temperature > self.target_temperature and self.heater.state:
                self.heater.turn_off()
                if self.callback:
                    await self.callback(**{self.heater.device_name: 'OFF'})
            if temperature > (self.target_temperature + self.histeresis) and not self.cooler.state:
                self.cooler.turn_on()
                if self.callback:
                    await self.callback(**{self.cooler.device_name: 'ON'})
                interval = 180  # Don't switch cooler within 3 minutes
            await asyncio.sleep(interval)


FRIDGE_TEMPERATURE = Temperature('fridge temperature', hardware_config=HARDWARE_CONFIG, callback=push_event)
FRIDGE_HEATER = PowerSwitch('fridge heater switch', int(HARDWARE_CONFIG.get('fridge heater switch')))
FRIDGE_COOLER = PowerSwitch('fridge switch', int(HARDWARE_CONFIG.get('fridge switch')))
FRIDGE = Fridge(FRIDGE_TEMPERATURE, FRIDGE_HEATER, FRIDGE_COOLER, callback=push_event)


def get_html_header(req, _resp, project_name):
    """Get HTML header and generic top of body containing the current temperature and heater state."""
    html = """\
HTTP/1.0 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html lang="en">
  <head>
    <title>{project_name} Web Server</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" href="data:,">
    <style>
      html{{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}}
      h1{{color: #0F3376; padding: 2vh;}}
      p{{font-size: 1.5rem;}}
      .button{{display: inline-block; background-color: #e7bd3b; border: none; border-radius: 4px; color: white; padding: 16px 40px;
               text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}}
      .button_on{{background-color: #f48642;}}
      .button_off{{background-color: #86f442;}}
      table,td,th{{border: 1px solid #ddd;}}
      table{{border-collapse: collapse;margin-left:auto; margin-right:auto;}}
      th,td{{padding: 5px;}}
    </style>
    <script>
      var source = new EventSource("sse_events");
      source.onmessage = function(event) {{
        var now = new Date();
        document.getElementById("time").innerHTML = now.toLocaleString();
        var data = JSON.parse(event.data);
        if (data.temperature)
        {{
          document.getElementById("temperature").innerHTML = data.temperature.toFixed(2);
        }}
        else if (data.heater)
        {{
          document.getElementById("kettle switch").innerHTML = data.heater;
        }}
        else
        {{
            for (var key in data)
            {{
              var doc_id = document.getElementById(key)
              var value = data[key];
              if (doc_id)
              {{
                if (Number(value) === value && value % 1 !== 0)
                {{
                    value = value.toFixed(2);
                }}
                doc_id.innerHTML = value;
              }}
              else
              {{
                console.log("missing placeholder for " + key + ": " + value);
                document.body.innerHTML += '<p>' + key + '<b id="' + key + '">' + value + '</p>';
              }}
            }}
        }}
      }}
      source.onerror = function(error) {{
        console.log(error);
        var now = new Date();
        document.getElementById("log").innerHTML += now.toLocaleString() + " EventSource error:" + error + "<br>";
      }}
    </script>
  </head>
  <body>
    <h1><a href="/">{project_name} Web Server</a></h1>
    <p>Last update: <b id="time"></b></p>
    <p>Kettle Temperature: <b id="kettle temperature">~{kettle_temperature}</b> <b>{temperature_unit}</b></p>
    <p>Kettle switch: <b id="kettle switch">{heater_state}</b></p>
    <hr/>
    <p>Fridge Temperature: <b id="fridge temperature">~{fridge_temperature}</b> <b>{temperature_unit}</b></p>
    <p>Fridge switch: <b id="fridge switch">{fridge_state}</b></p>
    <p>Fridge heater switch: <b id="fridge heater switch">{fridge_heater_state}</b></p>
    <hr/>
    <p>Environment Temperature: <b id="environment temperature">~{environment_temperature}</b> <b>{temperature_unit}</b></p>
    <hr/>
""".format(project_name=project_name,
           kettle_temperature=KETTLE.temperature.get(),
           fridge_temperature=FRIDGE.temperature.get(),
           environment_temperature=ENVIRONMENT_TEMPERATURE.get(), temperature_unit=KETTLE_TEMPERATURE.unit,
           heater_state=('ON' if HEATER.state else 'OFF'),
           fridge_state=('ON' if FRIDGE.cooler.state else 'OFF'),
           fridge_heater_state=('ON' if FRIDGE.heater.state else 'OFF'))

    log_msg = list()
    req.parse_qs()
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        for attr in dir(req):
            if not attr.startswith('_'):
                member = getattr(req, attr)
                if not callable(member):
                    logging.debug('req.%s: %s', attr, member)
    for key, value in req.form.items():
        set_value(globals(), key, value, log_msg)
    if log_msg:
        html += '<p style="color:red">' + '<br/>\n'.join(log_msg) + '</p><hr/>'
    return html


def get_html_footer(current_page):
    """Get HTML generic footer of body containing the navigation to the different pages."""
    pagerefs = list()
    log_msg = ''
    if current_page != '/':
        pagerefs.append('<a href="/">Automatic control</a>')
    if current_page != '/manual':
        pagerefs.append('<a href="/manual">Manual control</a>')
    if current_page != '/log':
        pagerefs.append('<a href="/log">logging</a>')
    if len(pagerefs) == 2:
        pagerefs.append('<a href="%s">Refresh</a>' % current_page)
        pagerefs.append('<small>uptime: %d</small>' % (time.time() - START_TIME))
    else:
        log_msg = '<hr/><p style="color:red">current_page "%s" is not (yet) supported...</p>\n' % current_page
    return log_msg + """\
    <hr/>
    <p id="log"></p>
    <p>%s</p>
    <p>%s</p>
  </body>
</html>""" % (' | '.join(pagerefs), '<br/>'.join(['%d: %s %s %s' % (item) for item in state.get_info()]))


async def sse_response(resp, events):
    """Send a server send event response."""
    print("Event source %r connected" % resp)
    await picoweb.start_response(resp, content_type='text/event-stream')
    events.add(resp)
    return False

event_sinks = set()


async def sse_events(_req, resp):
    """Handle a server send event for EventSource("sse_events")."""
    await sse_response(resp, event_sinks)
    return False


async def _push_data(sinks, data):
    """Background service."""
    to_del = set()

    if not sinks:
        await asyncio.sleep(0.001)
        return

    for resp in sinks:
        try:
            await resp.awrite("data: %s\n\n" % data)
        except OSError as ex:
            print("Event source %r disconnected (%r)" % (resp, ex))
            await resp.aclose()
            # Can't remove item from set while iterating, have to have
            # second pass for that (not very efficient).
            to_del.add(resp)

    for resp in to_del:
        sinks.remove(resp)


def set_value(obj, key, value, log_msg):
    """write the given value to the member defined by key."""
    print('set_value: %s="%s"' % (key, value))
    msg = ''
    if '.' in key:
        root, key = key.split('.', 1)
        if hasattr(obj, root):
            obj = getattr(obj, root)
            set_value(obj, key, value, log_msg)
        elif root in obj:
            set_value(obj[root], key, value, log_msg)
        else:
            msg = r'Unknown arg: .*\.%s.%s=%s' % (root, key, value)
    elif isinstance(obj, dict):
        if key in obj and isinstance(obj[key], (int, float)):
            obj[key] = None if value == '' else float(value)
        elif key in obj and hasattr(obj[key], 'set'):
            obj[key].set(value)
        elif key in obj and hasattr(obj[key], value):  # call specified method name
            getattr(obj[key], value)()
        elif key in obj and obj[key] is None:
            obj[key] = None if value == '' else float(value)
        else:
            msg = 'Unknown dict element: %s="%s"' % (key, value)
    else:
        if hasattr(obj, key) and isinstance(getattr(obj, key), (int, float)):
            setattr(obj, key, float(value))
        elif hasattr(obj, key) and hasattr(getattr(obj, key), 'set'):
            getattr(obj, key).set(value)
        elif hasattr(obj, key) and hasattr(getattr(obj, key), value):  # call specified method name
            getattr(getattr(obj, key), value)()
        elif callable(getattr(obj, key)):
            getattr(obj, key)(value)
        else:
            msg = 'Unknown object member: %s=%s' % (key, value)
    if msg:
        logging.error(msg)
        log_msg.append(msg)


def index(req, resp):
    """Main web page."""
    # if req.method == "POST": # don't know how to handle post messages...
    #     yield from picoweb.http_error(resp, "405")
    yield from resp.awrite(get_html_header(req, resp, PROJECT_NAME))
    if MANUAL_CONTROL:
        yield from resp.awrite('''\
<h2 style="color:red">Manual mode is enabled</h2>
<p><a href="/?MANUAL_CONTROL=0"><button class="button button_on">Disable manual mode</button></a></p>
''')
    yield from resp.awrite(RECIPE.web_page('RECIPE'))
    yield from resp.awrite(get_html_footer('/'))


def manual(req, resp):
    """Manual control web page."""
    yield from resp.awrite(get_html_header(req, resp, PROJECT_NAME))
    if not MANUAL_CONTROL:
        yield from resp.awrite('''\
<h2 style="color:red">Manual mode is disabled</h2>
<p><a href="/manual?MANUAL_CONTROL=1"><button class="button button_on">Enable manual mode</button></a></p>
''')

    html = '''
<form action="/manual" method="get">
  <label for="TARGET_TEMPERATURE">Target temperature:</label>
  <input type="number" id="TARGET_TEMPERATURE" name="TARGET_TEMPERATURE" value="%.0f">
  <input type="submit" formmethod="get" value="Submit">
</form>
''' % (RECIPE.get_target_temperature())

    if TARGET_TEMPERATURE is None:
        html += '''\
<h2>Manual control</h2>
<p>Press 'turn kettle ON|OFF' to control the heater.</p>
'''
    else:
        html += '''\
<h2>Control target temperature</h2>
<p>Target temperature: %.1f (%.2f..%.2f)</p>
''' % (TARGET_TEMPERATURE, TARGET_TEMPERATURE - HIST_GOAL, TARGET_TEMPERATURE + HIST_GOAL)

    if HEATER.state:
        html += '''\
<p><a href="/manual?HEATER=turn_off&TARGET_TEMPERATURE="><button class="button button_off">turn kettle OFF</button></a></p>
'''
    else:
        html += '''\
<p><a href="/manual?HEATER=turn_on&TARGET_TEMPERATURE="><button class="button button_on">turn kettle ON</button></a></p>
'''
    yield from resp.awrite(html)
    yield from resp.awrite(get_html_footer('/manual'))


def log(req, resp):
    """Manual control web page."""
    yield from resp.awrite(get_html_header(req, resp, PROJECT_NAME))

    yield from resp.awrite('''\
<h2>Logging</h2>
<p>%s</p>
''' % '<br/>'.join(status.logging.get()))

    yield from resp.awrite(get_html_footer('/log'))


def main():
    """Main routine.

    * Control the heater according to the specified recipe.
    * Run a webserver to show the status of the brewery.
    """
    routes = [
        ("/", index),
        ('/manual', manual),
        ('/log', log),
        ("/sse_events", sse_events),
    ]

    app = picoweb.WebApp(__name__, routes)

    weblog = logging.getLogger("picoweb")
    weblog.setLevel(logging.WARNING)

    # debug values:
    # -1 disable all logging
    # 0 (False) normal logging: requests and errors
    # 1 (True) debug logging
    # 2 extra debug logging
    app.run(debug=1, host='0.0.0.0', port=80, log=weblog)


if __name__ == '__main__':
    main()
