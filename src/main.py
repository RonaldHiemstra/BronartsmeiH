"""Script to automate the brewing process for the brewery.

Script includes a hardcoded brewing schedule for Brönald #3 - Lockdown.
"""
import json
import logging
import time

from machine import Pin
import uasyncio as asyncio
import picoweb

from config import Config
from localtime import Localtime
from status import state
from temperature import TemperatureADS1115 as Temperature

logging.basicConfig(level=logging.INFO)

PROJECT_NAME = 'BronatrsmeiH'

MANUAL_CONTROL = 0
TARGET_TEMPERATURE = 21
HIST_GOAL = .05  # accept +/- .05 degC

SYSTEM_CONFIG = Config('SYSTEM_CONFIG.json')
LOCAL_TIME = Localtime(SYSTEM_CONFIG.get('utc_offset'))

START_TIME = time.time()


def alert(msg):
    """Alert the operator!
    Some operator action is required.
    """
    # TODO: ALERT!!!!!
    logging.warning(msg)


class Stage():
    """A stage in the brewing process."""

    def __init__(self, name, duration, temperature, action=None, wait_for_action=True):
        self.name = name
        self.duration = duration
        self.temperature = temperature
        self.start = None
        self.wait_for_action = wait_for_action if action else False
        self.end_message = action
        self.end = None


class Recipe():
    def __init__(self, stages):
        self.stages = stages
        self.index = 0
        self.edge = None  # -1 for raising edge; 1 for falling edge

    def set_current_temperature(self, cur_temperature):
        target_temperature = self.get_target_temperature()
        stage = self.stages[self.index]
        if stage.start is None:
            if self.edge is None:
                self.edge = -1 if cur_temperature < target_temperature else 1
            delta = target_temperature - cur_temperature
            if delta * self.edge >= 0:
                logging.info('start stage %d: target=%.1f, current=%.1f, edge=%d',
                             self.index, target_temperature, cur_temperature, self.edge)
                stage.start = time.time()
                self.edge = None

    def get_target_temperature(self, default=-273):
        stage = self.stages[self.index]
        if (stage.start is not None) and (time.time() - stage.start) > stage.duration:
            if stage.wait_for_action and stage.end is None:
                alert(stage.end_message)
            else:
                if stage.end is None:
                    stage.end = time.time()
                if self.index == (len(self.stages) - 1):
                    return default
                self.index += 1

        return self.stages[self.index].temperature

    def ack_action(self, action):
        stage = self.stages[self.index]
        if stage.end_message == action:
            stage.end = time.time()
        else:
            logging.error('Action "%s" not allowed!, wrong stage[%d] expecting "%s"', action, self.index, stage.end_message)


# duration, target temperature, start time (temperature reached)
recipe = Recipe([Stage('Preheat', 0, 70, 'Add malt and cooked oats'),
                 Stage('Maichen phase1', 60 * 60, 67),
                 Stage('Maichen phase2', 10 * 60, 74, 'Filter/remove grains'),
                 Stage('Boil phase1', 30 * 60, 100, 'Add first hops'),
                 Stage('Boil phase2', 50 * 60, 100, 'Add rest of hops and sugar'),
                 Stage('Boil phase3', 10 * 60, 100, 'Whirlpool and start cooling'),
                 Stage('Cooling', 0, 20, 'Transfer wort to fermentation vessel and add yeast', False)])

recipe.index = 1
recipe.stages[1].duration = 20 * 69


class Heater():
    def __init__(self, pin=13):
        self.pin = Pin(pin, Pin.OUT)
        self.state = None

    def on(self):
        if self.state is not 1:
            self.state = 1
            self.pin.value(self.state)
            state.set_info('Heater', 'ON')

    def off(self):
        if self.state is not 0:
            self.state = 0
            self.pin.value(self.state)
            state.set_info('Heater', 'OFF')


heater = Heater()
TEMPERATURE = Temperature()

TARGET_TEMPERATURE = recipe.stages[0].temperature
state.set_info('Target temperature', TARGET_TEMPERATURE)

class Kettle():
    def __init__(self, temperature, heater, recipe, interval=1):
        """Constructor.
        @param period   The duration to measure. [s]
        @param interval Issue a measurement at every interval. [s]
        """
        self.temperature = temperature
        self.heater = heater
        self.recipe = recipe
        self.interval = interval
        self.manual_control = False
        self.manual_target_temperature = None
        loop = asyncio.get_event_loop()
        loop.create_task(self._control())

    async def _control(self):
        """Control the temperature of the brewing kettle."""
        while True:
            temperature = self.temperature.get()
            await push_event(temperature=temperature)

            self.recipe.set_current_temperature(temperature)
            # DEBUG: using full automation...
            if self.manual_control:
                target_temperature = self.manual_target_temperature
            else:
                target_temperature = recipe.get_target_temperature()

            if target_temperature is not None:
                if temperature < (target_temperature - temperature.histeresis):
                    self.heater.on()
                elif temperature > (target_temperature + temperature.histeresis):
                    self.heater.off()
            await asyncio.sleep(1)


async def temp_control():
    """Control the temperature of the brewing kettle."""
    # TODO: use Kettle class!
    while True:
        temp = TEMPERATURE.get()
        await push_event(temperature=temp)

        recipe.set_current_temperature(temp)
        # DEBUG: using full automation...
        if MANUAL_CONTROL:
            target_temperature = TARGET_TEMPERATURE
        else:
            target_temperature = recipe.get_target_temperature()

        if target_temperature is not None:
            if temp < (target_temperature - HIST_GOAL):
                if not heater.state:
                    await push_event(heater_state='ON')
                    heater.on()
            elif temp > (target_temperature + HIST_GOAL):
                if heater.state:
                    await push_event(heater_state='OFF')
                    heater.off()
        await asyncio.sleep(1)


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
        var data = JSON.parse(event.data);
        if (data.temperature)
        {{
          var now = new Date();
          document.getElementById("temperature").innerHTML = data.temperature.toFixed(2);
          document.getElementById("time").innerHTML = now.toLocaleString();
        }}
        if (data.heater)
        {{
          document.getElementById("heater_state").innerHTML = data.heater;
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
    <p>Temperature: <b id="temperature">{temperature}</b><b> &deg;C</b></p>
    <p>Kettle state: <b id="heater_state">{heater_state}</b></p>
    <hr/>
""".format(project_name=project_name, temperature=TEMPERATURE.get(), heater_state=('ON' if heater.state else 'OFF'))

    log_msg = list()
    req.parse_qs()
    if logging._level <= logging.DEBUG:
        for d in dir(req):
            if not d.startswith('_'):
                m = getattr(req, d)
                if not callable(m):
                    logging.debug('req.%s: %s', d, m)
    for key, value in req.form.items():
        set_value(globals(), key, value, log_msg)
    if log_msg:
        html += '<p style="color:red">' + '<br/>\n'.join(log_msg) + '</p><hr/>'
    return html


def get_html_footer(current_page):
    pagerefs = list()
    log_msg = ''
    if current_page != '/':
        pagerefs.append('<a href="/">Automatic control</a>')
    if current_page != '/manual':
        pagerefs.append('<a href="/manual">Manual control</a>')
    if current_page != '/calibration':
        pagerefs.append('<a href="/calibration">Temperature calibration</a>')
    if len(pagerefs) == 2:
        pagerefs.append('<a href="%s">Refresh</a>' % current_page)
    else:
        log_msg = '<hr/><p style="color:red">current_page "%s" is not (yet) supported...</p>\n' % current_page
    return log_msg + """\
    <hr/>
    <p>%s</p>
  </body>
</html>""" % ' | '.join(pagerefs)


async def sse_response(resp, events):
    print("Event source %r connected" % resp)
    yield from resp.awrite("HTTP/1.0 200 OK\r\n")
    yield from resp.awrite("Content-Type: text/event-stream\r\n")
    yield from resp.awrite("\r\n")
    events.add(resp)
    return False

event_sinks = set()

def sse_events(req, resp):
    await sse_response(resp, event_sinks)
    return False


async def _push_data(sinks, data):
    """Background service."""
    to_del = set()

    for resp in sinks:
        try:
            await resp.awrite("data: %s\n\n" % data)
        except OSError as e:
            print("Event source %r disconnected (%r)" % (resp, e))
            await resp.aclose()
            # Can't remove item from set while iterating, have to have
            # second pass for that (not very efficient).
            to_del.add(resp)

    for resp in to_del:
        sinks.remove(resp)


async def push_event(**event):
    """Push an event.
    @param event  dict where key is a named div in the body and value will be filled in the div.
    """
    await _push_data(event_sinks, json.dumps(event))


def web_page():
    html = '<h2>Recipe</h2>\n'
    html += '<p>Start: %04d-%02d-%02d %02d:%02d</p>\n' % time.localtime(START_TIME)[:5]
    html += '<p><table>\n'
    html += '<tr><th>duration<br/>[min]</th><th>temperature<br/>[&deg;C]</th><th>start</th><th>end</th><th>progress<br/>[%]</th>'
    html += '<th style="text-align:left">action</th></tr>\n'
    message = None
    for stage in recipe.stages:
        action = stage.end_message if stage.end_message else ''
        if stage.start is None:
            row_style = ''
            t_start = '-'
            t_end = '-'
            p = 0
        elif stage.end is None:
            row_style = ' style="background-color:yellow"'
            t_start = '%02d:%02d' % time.localtime(stage.start)[3:5]
            t_end = '%02d:%02d' % time.localtime(stage.start + stage.duration)[3:5]
            progress = time.time() - stage.start
            if progress >= stage.duration:
                p = 100
            else:
                print(time.time(), stage.start, progress, stage.duration)
                p = 100 * progress / stage.duration
            if p == 100:
                message = stage.end_message
                t_end = '<b>%s</b>' % t_end
                if action:
                    action = '<a href="/?recipe.ack_action=%s">%s</a>' % (action, action)
        else:
            row_style = ' style="background-color:gray"'
            t_start = '%02d:%02d' % time.localtime(stage.start)[3:5]
            t_end = '%02d:%02d' % time.localtime(stage.end)[3:5]
            p = 100
        html += '''<tr%s><td>%d</td><td>%d</td><td>%s</td><td>%s</td><td>%.1f</td><td style="text-align:left">%s</td></tr>
''' % (row_style, stage.duration // 60, stage.temperature, t_start, t_end, p, action)
    html += '</table></p>\n'
    if message is not None:
        html += '<p style="color:red"><b>%s</b></p>\n' % message
        html += '<p><a href="/?recipe.ack_action=%s"><button class="button button_on">action performed</button></a></p>\n' % message
    return html


def set_value(obj, key, value, log_msg):
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
    # if req.method == "POST": # don't know how to handle post messages...
    #     yield from picoweb.http_error(resp, "405")
    yield from resp.awrite(get_html_header(req, resp, PROJECT_NAME))
    if MANUAL_CONTROL:
        yield from resp.awrite('''\
<h2 style="color:red">Manual mode is enabled</h2>
<p><a href="/?MANUAL_CONTROL=0"><button class="button button_on">Disable manual mode</button></a></p>
''')
    yield from resp.awrite(web_page())
    yield from resp.awrite(get_html_footer('/'))


def calibration(req, resp):
    yield from resp.awrite(get_html_header(req, resp, PROJECT_NAME))
    yield from resp.awrite(TEMPERATURE.calibration.web_page('TEMPERATURE'))
    yield from resp.awrite('<hr/>\n')
    yield from resp.awrite(TEMPERATURE.get_calibrated_details_page('TEMPERATURE'))
    yield from resp.awrite(get_html_footer('/calibration'))


def manual(req, resp):
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
''' % (recipe.get_target_temperature())

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

    if heater.state:
        html += '''\
<p><a href="/manual?heater=off&TARGET_TEMPERATURE="><button class="button button_off">turn kettle OFF</button></a></p>
'''
    else:
        html += '''\
<p><a href="/manual?heater=on&TARGET_TEMPERATURE="><button class="button button_on">turn kettle ON</button></a></p>
'''
    yield from resp.awrite(html)
    yield from resp.awrite(get_html_footer('/manual'))


def main():
    """Main routine.

    * Control the heater according to the specified recipe.
    * Run a webserver to show the status of the brewery.
    """
    routes = [
        ("/", index),
        ('/calibration', calibration),
        ('/manual', manual),
        ("/sse_events", sse_events),
    ]

    app = picoweb.WebApp(__name__, routes)

    loop = asyncio.get_event_loop()
    loop.create_task(temp_control())

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
