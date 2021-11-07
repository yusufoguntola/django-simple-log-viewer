import re

from os import listdir
from os.path import isfile, join

from django.conf import settings


class LogManager:
    name = ""
    log_names = []
    columns = []
    log_files = []
    path = ""

    def __init__(self):
        """
        Get all log file names as contained in log setting with the formatter for each.
        """
        self.logging_setting = getattr(settings, 'LOGGING', {})
        if self.logging_setting:
            self.formatters = self.logging_setting.get('formatters')
            self.handlers = self.logging_setting.get('handlers', {})
            self.logs = []
            for value in self.handlers.values():
                if value.get('filename'):
                    filename = value.get('filename')
                    self.logs.append({'name': filename, 'formatter': value.get('formatter')})
                    self.log_names.append(filename[filename.rindex("/") + 1:])

    def get_logs(self):
        return self.log_names

    def load_details(self, name):
        """
        We have a log to deal with now. Get possible columns for this log file (using format setting) and load all
        old log files for the selected log file
        :param name:
        :return:
        """
        self.name = name
        self.columns = []
        for log in self.logs:
            filename = log.get('name')
            expected_default_name = '{}{}'.format(name, getattr(settings, 'LOG_FILE_EXTENSION', '.log'))
            if filename.endswith(expected_default_name):
                formatter_name = log.get('formatter')
                formatter_setting = self.formatters.get(formatter_name)
                _format = formatter_setting.get('format')
                _format = re.sub(r'[^A-Za-z0-9 ]+[1s]*', '', _format)
                for item in re.split('\s+', _format.strip()):
                    if item.lower() == 'asctime':
                        date_format = formatter_setting.get('datefmt', 'Date Time')
                        self.columns.extend(['Date', 'Time']) if date_format.__contains__(
                            ' ') else self.columns.append('Date')
                    else:
                        self.columns.append(item.title())
                self.path = filename[:filename.rindex('/') + 1]
                self.log_files = sorted([file for file in listdir(self.path) if
                                         isfile(join(self.path, file)) and file.__contains__(expected_default_name)])
                break

    def get_columns(self):
        return self.columns

    def get_log_files(self):
        return self.log_files

    def get_log_content(self, file):
        file_path = join(self.path, file)
        rows = []
        with open(file_path, "r") as log_file:
            lines = log_file.readlines()
            for line in lines:
                _columns = []
                splitted = re.split('\s+', line, len(self.columns) - 1)
                for column in splitted:
                    _columns.append(column)
                rows.append(_columns)
        return rows
