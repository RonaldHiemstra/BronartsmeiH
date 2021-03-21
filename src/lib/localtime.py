"""File providing localtime support."""
import time
import network
import ntptime
from machine import RTC, reset
from config import Config

system_config = Config('system_config.json')

class Localtime():
    """Synchronized realtime clock using NTP."""
    def __init__(self, utc_offset=None):
        self.utc_offset = utc_offset or system_config.get('utc_offset')
        self.__synced = None
        self._sync()

    def _sync(self):
        try:
            ntptime.settime()   # Synchronize the system time using NTP
        except Exception as ex:
            print('ERROR: ntp.settime() failed. err:', ex)
            if network.WLAN().isconnected():
                reset()
        # year, month, day, day_of_week, hour, minute, second, millisecond
        datetime_ymd_w_hms_m = list(RTC().datetime())
        datetime_ymd_w_hms_m[4] += self.utc_offset
        RTC().init(datetime_ymd_w_hms_m)
        self.__synced = datetime_ymd_w_hms_m[2]
        del datetime_ymd_w_hms_m

    def now(self):
        """Retrieve a snapshot of the current time in milliseconds accurate."""
        class Now():
            """Class representing a snapshot of the current time."""
            def __init__(self):
                (self.year, self.mon, self.day, self.dow,
                 self.hour, self.min, self.sec, self.msec) = RTC().datetime()
                self._time = None
            def get_time(self) -> float:
                """Convert this time snapshot to a time float value."""
                if self._time is None:
                    self._time =  time.mktime([self.year, self.mon, self.day,
                                               self.hour, self.min, self.sec, 0, 0])
                    # self._time += self.msec / 1000    # float overflow when adding msec :(
                return self._time
        snapshot = Now()
        if snapshot.day != self.__synced and snapshot.hour == 4:  # sync every day @ 4am
            self._sync()
            snapshot = Now()
        return snapshot
