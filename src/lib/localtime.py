import ntptime
from machine import RTC, reset
import time
from config import Config

system_config = Config('system_config.json')

class Localtime():
    """Synchronized realtime clock using NTP."""
    def __init__(self, utcOffset=None):
        self.utcOffset = utcOffset or system_config.get('utc_offset')
        self.__synced = None
        self._sync()

    def _sync(self):
        try:
            ntptime.settime()   # Synchronize the system time using NTP
        except Exception as ex:
            print('ERROR: ntp.settime() failed. err:', ex)
            reset()
        # year, month, day, week_of_year, hour, minute, second, millisecond
        # TODO: or is it: year, month, day, day_of_week, hour, minute, second, millisecond
        datetime_ymd_w_hms_m = list(RTC().datetime())
        datetime_ymd_w_hms_m[4] += self.utcOffset
        RTC().init(datetime_ymd_w_hms_m)
        self.__synced = datetime_ymd_w_hms_m[2]
        del datetime_ymd_w_hms_m

    def now(self):
        """Retrieve the current time in milliseconds accurate."""
        class now():
            def __init__(self):
                (self.year, self.mon, self.day, self.dow,
                 self.hour, self.min, self.sec, self.msec) = RTC().datetime()
                self._time = None
            def get_time(self):
                if self._time is None:
                    self._time =  time.mktime([self.year, self.mon, self.day,
                                               self.hour, self.min, self.sec, 0, 0])
                    # self._time += self.msec / 1000    # float overflow when adding msec :(
                return self._time
        dt = now()
        if dt.day != self.__synced and dt.hour == 4:  # sync every day @ 4am
            self._sync()
            dt = now()
        return dt
