class Logger():
    def __init__(self, dt):
        self.loggedlineLength = 0
        self.dt = dt
        self.newline = True
        now = self.dt.now()
        print('%d-%02d-%02d %02d:%02d:%02d' % (now.year, now.mon, now.day, now.hour, now.min, now.sec))

    def log(self, msg, end=None):
        if self.newline:
            now = self.dt.now()
            msg = '%02d:%02d:%02d ' % (now.hour, now.min, now.sec) + msg

        if end is None:
            print(msg + ' ' * (self.loggedlineLength - len(msg)))
            self.loggedlineLength = 0
            self.newline = True
        elif end == '':
            print(msg, end=end)
            self.loggedlineLength += len(msg)
            self.newline = False
        elif end == '\r':
            print(msg + ' ' * (self.loggedlineLength - len(msg)), end=end)
            self.loggedlineLength = len(msg)
            self.newline = True
