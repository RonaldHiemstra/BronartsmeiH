"""Support file to handle configuration files."""
import json
import os


class Config():
    """Class for serializing configuration items."""

    def __init__(self, filename):
        self.filename = filename
        try:
            with open(self.filename) as file:
                self.__config = json.load(file)
        except OSError:
            path = ''
            for part in filename.split('/')[:-1]:
                try:
                    os.mkdir(path + part)
                except OSError:
                    pass
                path += part + '/'
            self.__config = dict()

    def get(self, key=None, default=None):
        """Get a config item."""
        if key is None:
            # return all public config items (filter out the hidden items)
            return {key: self.__config[key] for key in self.__config if not key.startswith('__')}
        return self.__config.get(key, default)

    def set(self, key, value):
        """Set a config item."""
        self.__config[key] = value
        with open(self.filename, 'w') as file:
            file.write(json.dumps(self.__config))

    def remove(self, key):
        """Set a config item."""
        del self.__config[key]
        with open(self.filename, 'w') as file:
            file.write(json.dumps(self.__config))
