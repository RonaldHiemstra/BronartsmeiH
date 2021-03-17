"""Script to automate the brewing process for the BronartsmeiH brewery.

Script includes a hardcoded brewing schedule for Brönald #3 - Lockdown.
"""
from collections import OrderedDict
import logging
import time
from statistics import mean, stdev

from machine import ADC, Pin
import uasyncio as asyncio
import picoweb

from config import Config
from localtime import Localtime
from logger import Logger

logging.basicConfig(level=logging.INFO)

PROJECT_NAME = 'BronatrsmeiH'

MANUAL_CONTROL = 0
TARGET_TEMPERATURE = 21
HIST_GOAL = .5  # accept +/- .5 degC

SYSTEM_CONFIG = Config('SYSTEM_CONFIG.json')
LOCAL_TIME = Localtime(SYSTEM_CONFIG.get('utc_offset'))
LOGGER = Logger(LOCAL_TIME)

START_TIME = time.time()


def alert(msg):
    """Alert the operator!
    Some operator action is required.
    """
    #TODO: ALERT!!!!!
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
            self.print_state()

    def off(self):
        if self.state is not 0:
            self.state = 0
            self.pin.value(self.state)
            self.print_state()

    def print_state(self):
        msg = 'Heater %s' % ('ON' if self.state else 'OFF')
        LOGGER.log(msg)


class Calibration():
    def __init__(self, calibration_file, steps, min_temp, max_temp):
        self._config = Config(calibration_file)
        self._steps = dict()  # Update with update_steps()
        cal_values = self._config.get()
        if cal_values:
            raw_values = sorted(cal_values)
            lowest = raw_values[0]
            highest = raw_values[-1]
            if lowest == 't0000':
                if cal_values[lowest] != min_temp:
                    logging.warning('lowest temperature is already specified as %f, given %f is ignored',
                                    cal_values[lowest], min_temp)
            elif cal_values[lowest] > min_temp:
                # Set a new (initial) minimum for this sensor
                self._config.set('t0000', min_temp)
            else:
                logging.warning('index: %s is lower (%f) than given minimum %f', lowest, cal_values[lowest], min_temp)
            if highest == 't%04d' % (steps - 1):
                if cal_values[highest] != max_temp:
                    logging.warning('highest temperature is already specified as %f, given %f is ignored',
                                    cal_values[highest], max_temp)
            elif cal_values[highest] < max_temp:
                # Set a new (initial) maximum for this sensor
                self._config.set('t%04d' % (steps - 1), max_temp)
            else:
                logging.warning('index: %s is higher (%f) than given maximum %f', highest, cal_values[highest], max_temp)
        else:
            self._config.set('t0000', min_temp)
            self._config.set('t%04d' % (steps - 1), max_temp)
        self.update_steps()

    def update_steps(self):
        # make config sorted
        self._steps = OrderedDict([(int(key[1:]), value)
                                   for (key, value) in sorted(self._config.get().items(), key=lambda t: t[0])])
        keys = list(self._steps)
        print('keys =', keys)
        self._min_raw = keys[0]
        self._max_raw = keys[-1]

    def get(self, raw_value):
        lower = self._min_raw
        higher = self._max_raw
        for stored in self._steps:
            if stored <= raw_value:
                lower = stored
            elif stored > raw_value:
                higher = stored
                break
        logging.debug('lower: %s, measured: %s, higher: %s', lower, raw_value, higher)
        if higher == lower:
            return self._steps[lower]
        return self._steps[lower] + ((raw_value - lower) * (self._steps[higher] - self._steps[lower]) / (higher - lower))

    def set(self, raw_value, calibrated_value):
        self._config.set('t%04d' % raw_value, float(calibrated_value))
        self.update_steps()

    def remove(self, raw_value):
        self._config.remove('t%04d' % int(raw_value))
        self.update_steps()

    def web_page(self):
        html = '<table>\n'
        prev_value = -273
        html += '<tr><th>raw value</th><th>actual temperature [&deg;C]</th><th>delete</th></tr>\n'
        max_raw = list(self._steps)[-1]
        for (key, value) in self._steps.items():
            remove = ''
            if value < prev_value:
                style = ' style="color:red"'
            else:
                prev_value = value
                style = ''
            if key in [0, max_raw]:
                remove = '-'
            else:
                remove = '<b><a href="/calibration?temperature.calibration.remove=%d">x</a></b>' % key
            html += '<tr %s><td>%d</td><td>%s</td><td>%s</td></tr>\n' % (style, key, value, remove)
        html += '\n</table>\n'
        return html


def best_fit_slope_and_intercept(X, Y):
    # https://stackoverflow.com/questions/22239691/code-for-best-fit-straight-line-of-a-scatter-plot-in-python
    xBar = sum(X)/len(X)
    yBar = sum(Y)/len(Y)
    n = len(X)  # or len(Y)
    num = sum([xi*yi for xi, yi in zip(X, Y)]) - n * xBar * yBar
    deNum = sum([xi**2 for xi in X]) - n * xBar**2
    b = num / deNum
    a = yBar - b * xBar
    #print('best fit line:\ny = {:.2f} + {:.2f}x'.format(a, b))
    return b, a


class Temperature():
    def __init__(self, pin=32, period=15.0, interval=0.2):
        """Measure the temperature.
        @param period   The duration to measure. [s](The sensor is very noisy :( )
        @param interval Issue a measurement at every interval. [s]
        """
        self.adc = ADC(Pin(pin))
        self.adc.atten(ADC.ATTN_11DB)  # set 11dB input attenuation (voltage range roughly 0.0v - 3.6v)
        self.calibration = Calibration('/data/temp_cal_%d.json' % pin, 4096, -10, 250)
        self.measurements = list()
        self.period = period
        self.interval = interval
        for _ in range(3):
            # make sure some values are present to calculate averages
            self.measurements.append(self.adc.read())
        loop = asyncio.get_event_loop()
        loop.create_task(self._collect())

    async def _collect(self):
        """Collect the temperature measurements."""
        pending = max(1, self.period / self.interval)

        while True:
            if pending:
                pending -= 1
            else:
                self.measurements.pop(0)  # remove the first measurement
# A new "machine.ADC.read_u16()" method is defined and implemented on stm32, esp8266, esp32 and nrf ports,
# providing a consistent way to read an ADC that returns a value in the range 0-65535.
# This new method should be preferred to the existing "ADC.read()" method.
            self.measurements.append(self.adc.read())
            await asyncio.sleep(self.interval)

    def get(self, estimate=0):
        # TODO: do a linefit through the measurements and extrapolate to estimate the value after 'estimate' seconds
        raw = mean(self.measurements)
        nr = len(self.measurements)
        slope, intercept = best_fit_slope_and_intercept(list(range(nr)), self.measurements)
        #LOGGER.log('slope: %.1f, intercept: %.1f' % (slope, intercept))
        predicted_temp = self.calibration.get(intercept + slope * (nr + (estimate / self.interval)))
        temp = self.calibration.get(raw)
        log_msg = 'Temperature: %.1f (raw temp: %.1f, stdev: %.2f); predicted: %.1f' % (temp, raw,
                                                                                        stdev(self.measurements), predicted_temp)
        LOGGER.log(log_msg, end='\r')
        return predicted_temp

    def get_calibrated_details_page(self):
        raw = mean(self.measurements)
        temperature = self.calibration.get(raw)

        html = '<p>Temperature measurement over past %ds:</p>\n' % self.period
        html += '<table>\n'
        html += '<tr><td>temperature:</td><td>%.1f &deg;C</td></tr>\n' % temperature
        html += '<tr><td>min:</td><td>%.1f &deg;C</td></tr>\n' % self.calibration.get(min(self.measurements))
        html += '<tr><td>max:</td><td>%.1f &deg;C</td></tr>\n' % self.calibration.get(max(self.measurements))
        html += '<tr><td>raw:</td><td>%.1f</td></tr>\n' % raw
        html += '<tr><td>raw stdev:</td><td>%.1f</td></tr>\n' % stdev(self.measurements)
        html += '</table>\n'
        html += '<p><form action="/calibration" method="get">\n'
        html += '<label for="temperature">Current temperature:</label>\n'
        html += '<input type="number" step="0.1" id="temperature" name="temperature" value="%.1f">\n' % temperature
        html += '<input type="submit" formmethod="get" value="Write calibratied temperature">\n'
        html += '</form></p>\n'
        return html

    def set(self, calibrated):
        self.calibration.set(int(mean(self.measurements)), calibrated)


heater = Heater()
TEMPERATURE = Temperature()

TARGET_TEMPERATURE = recipe.stages[0].temperature
LOGGER.log('target: %d' % (TARGET_TEMPERATURE,))


async def temp_control():
    while True:
        temp = TEMPERATURE.get()

        recipe.set_current_temperature(temp)
        # DEBUG: using full automation...
        if MANUAL_CONTROL:
            target_temperature = TARGET_TEMPERATURE
        else:
            target_temperature = recipe.get_target_temperature()

        if target_temperature is not None:
            if temp < (target_temperature - HIST_GOAL):
                heater.on()
            elif temp > (target_temperature + HIST_GOAL):
                heater.off()
        await asyncio.sleep(1)  # Using a solid state relais, it's okay to switch power every sec :)


# Complete project details at https://RandomNerdTutorials.com
def get_html_header(req, _resp, project_name, refresh_content=None):
    now = LOCAL_TIME.now()
    localtime = '%d-%02d-%02d %02d:%02d:%02d' % (now.year, now.mon, now.day, now.hour, now.min, now.sec)
    html = """HTTP/1.0 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html lang="en">
  <head>""" + (('\n<meta http-equiv="refresh" content="%s" />' % refresh_content) if refresh_content else '') + """
    <title>""" + project_name + """ Web Server</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" href="data:,">
    <style>
      html{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}
      h1{color: #0F3376; padding: 2vh;}
      p{font-size: 1.5rem;}
      .button{display: inline-block; background-color: #e7bd3b; border: none; border-radius: 4px; color: white; padding: 16px 40px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
      .button_on{background-color: #f48642;}
      .button_off{background-color: #86f442;}
      table,td,th{border: 1px solid #ddd;}
      table{border-collapse: collapse;margin-left:auto; margin-right:auto;}
      th,td{padding: 5px;}
    </style>
  </head>
  <body>
    <h1><a href="/">""" + project_name + """ Web Server</a></h1>
    <p>Last update: <b>""" + localtime + """</b></p>
    <p>Temperature: <b>%.1f &deg;C</b></p>
    <p>Kettle state: <b>%s</b></p>
    <hr/>
""" % (TEMPERATURE.get(), ('ON' if heater.state else 'OFF'))

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
        html += '<hr/><p style="color:red">' + '<br/>\n'.join(log_msg) + '</p>'
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
        elif key in obj and hasattr(obj[key], value): # call specified method name
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
    yield from resp.awrite(get_html_header(req, resp, PROJECT_NAME, '5; URL=http://%s/' % req.headers[b'Host'].decode()))
    if MANUAL_CONTROL:
        yield from resp.awrite('''\
<h2 style="color:red">Manual mode is enabled</h2>
<p><a href="/?MANUAL_CONTROL=0"><button class="button button_on">Disable manual mode</button></a></p>
''')
    yield from resp.awrite(web_page())
    yield from resp.awrite(get_html_footer('/'))


def calibration(req, resp):
    yield from resp.awrite(get_html_header(req, resp, PROJECT_NAME))
    yield from resp.awrite(TEMPERATURE.calibration.web_page())
    yield from resp.awrite('<hr/>\n')
    yield from resp.awrite(TEMPERATURE.get_calibrated_details_page())
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
<p>Target temperature: %.0f (%.1f..%.1f)</p>
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

    * Controll the heater according to the specified recipe.
    * Run a webserver to show the status of the brewery.
    """
    routes = [
        ("/", index),
        ('/calibration', calibration),
        ('/manual', manual),
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
