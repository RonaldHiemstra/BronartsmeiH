"""A recipe contains several stages."""
import logging
import time

from status import state


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
    """The recipe for a nice beer.
    The client of this class should call `set_current_temperature` on a regular interval, so the recipe can check the progress.
    #TODO: the recipe should get the temperature when needed (using asyncio)...
    """

    def __init__(self, stages):
        self.stages = stages
        self.index = 0
        self.edge = None  # -1 for raising edge; 1 for falling edge

    def _set_current_temperature(self, cur_temperature):
        target_temperature = self._get_target_temperature()
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

    def get_target_temperature(self, cur_temperature=None, default=-273):
        """Get the required temperature."""
        if cur_temperature is not None:
            self._set_current_temperature(cur_temperature)
        return self._get_target_temperature(default)

    def _get_target_temperature(self, default=-273):
        stage = self.stages[self.index]
        if (stage.start is not None) and (time.time() - stage.start) > stage.duration:
            if stage.wait_for_action and stage.end is None:
                state.alert('Recipe', stage.end_message)
            else:
                if stage.end is None:
                    stage.end = time.time()
                if self.index == (len(self.stages) - 1):
                    return default
                self.index += 1

        return self.stages[self.index].temperature

    def ack_action(self, action):
        """Acknowledge the pending action."""
        stage = self.stages[self.index]
        if stage.end_message == action:
            stage.end = time.time()
            state.alert('Recipe', None)
        else:
            logging.error('Action "%s" not allowed!, wrong stage[%d] expecting "%s"', action, self.index, stage.end_message)

    def web_page(self, recipe_variable_name):
        """Get HTML with the recipe and its progress."""
        html = '''\
<h2>Recipe</h2>
<p><table>
  <tr><th>duration<br/>[min]</th><th>temperature<br/>[&deg;C]</th><th>start</th><th>end</th><th>progress<br/>[%%]</th>\
<th style="text-align:left">action</th></tr>
'''
        message = None
        for stage in self.stages:
            action = stage.end_message if stage.end_message else ''
            if stage.start is None:
                row_style = ''
                t_start = '-'
                t_end = '-'
                percentage = 0
            elif stage.end is None:
                row_style = ' style="background-color:yellow"'
                t_start = '%02d:%02d' % time.localtime(stage.start)[3:5]
                t_end = '%02d:%02d' % time.localtime(stage.start + stage.duration)[3:5]
                progress = time.time() - stage.start
                if progress >= stage.duration:
                    percentage = 100
                else:
                    print(time.time(), stage.start, progress, stage.duration)
                    percentage = 100 * progress / stage.duration
                if percentage == 100:
                    message = stage.end_message
                    t_end = '<b>%s</b>' % t_end
                    if action:
                        action = '<a href="/?%s.ack_action=%s">%s</a>' % (recipe_variable_name, action, action)
            else:
                row_style = ' style="background-color:gray"'
                t_start = '%02d:%02d' % time.localtime(stage.start)[3:5]
                t_end = '%02d:%02d' % time.localtime(stage.end)[3:5]
                percentage = 100
            html += '''<tr%s><td>%d</td><td>%d</td><td>%s</td><td>%s</td><td>%.1f</td><td style="text-align:left">%s</td></tr>
    ''' % (row_style, stage.duration // 60, stage.temperature, t_start, t_end, percentage, action)
        html += '</table></p>\n'
        if message is not None:
            html += '<p style="color:red"><b>%s</b></p>\n' % message
            html += '<p><a href="/?%s.ack_action=%s"><button class="button button_on">action performed</button></a></p>\n' % (
                recipe_variable_name, message)
        return html
