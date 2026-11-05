import os
import re
from pathlib import Path
from django.conf import settings

ASCTIME_REGEX = (
    r'(?:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,\.]\d+)?|'
    r'\d{2}/[A-Za-z]+/\d{4}(?::|\s+)\d{2}:\d{2}:\d{2}(?:\s+[+-]\d+)?|'
    r'\S+?(?:\s+\d{2}:\d{2}:\d{2}(?:[,\.]\d+)?)?)'
)

COMMON_FALLBACK_FORMATS = [
    ('%(asctime)s [%(levelname)s] %(name)s: %(message)s', '%', None),
    ('%(asctime)s - %(name)s - %(levelname)s - %(message)s', '%', None),
    ('[%(asctime)s] %(levelname)s: %(message)s', '%', None),
    ('{levelname} {asctime} {module} {process:d} {thread:d} {message}', '{', None),
    ('{levelname} {message}', '{', None),
    ('%(asctime)s [%(levelname)-8s] %(message)s', '%', None),
    ('%(levelname)s:%(name)s:%(message)s', '%', None),
    ('[{server_time}] {message}', '{', None),
]


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
        self.logging_setting = getattr(settings, 'LOGGING', {}) or {}
        self.formatters = self.logging_setting.get('formatters') or {}
        self.handlers = self.logging_setting.get('handlers') or {}
        self.logs = []
        self.log_names = []
        self.columns = []
        self.log_files = []
        self.path = ""
        self.name = ""
        self.compiled_regex = None
        self.has_split_asctime = False
        self.msg_idx = -1

        for value in self.handlers.values():
            if isinstance(value, dict) and value.get('filename'):
                raw_filename = value.get('filename')
                filename = os.fspath(raw_filename)
                basename = os.path.basename(filename)
                self.logs.append({
                    'name': filename,
                    'formatter': value.get('formatter'),
                    'basename': basename,
                })
                if basename not in self.log_names:
                    self.log_names.append(basename)

    def get_logs(self):
        return self.log_names

    def _build_parser(self, format_str, style=None, datefmt=None):
        if not style:
            if '{' in format_str and '%' not in format_str:
                style = '{'
            elif '$' in format_str and '%' not in format_str:
                style = '$'
            else:
                style = '%'

        if style == '{':
            token_pattern = re.compile(r'\{([a-zA-Z0-9_]+)(?::[^{}]*)?\}')
        elif style == '$':
            token_pattern = re.compile(r'\$(?:\{([a-zA-Z0-9_]+)\}|([a-zA-Z0-9_]+))')
        else:
            token_pattern = re.compile(r'%\(([a-zA-Z0-9_]+)\)(?:[-+0-9# *.]*)?[a-zA-Z]')

        matches = list(token_pattern.finditer(format_str))
        if not matches:
            return ['Log'], re.compile(r'^(?P<message>.*)$'), False, 0

        columns = []
        has_split_asctime = False
        date_has_space = (' ' in (datefmt or 'Date Time'))

        regex_parts = ['^']
        last_end = 0

        for i, m in enumerate(matches):
            literal = format_str[last_end:m.start()]
            if literal:
                esc = re.escape(literal)
                esc = re.sub(r'\\\s+', lambda _: r'\s+', esc)
                regex_parts.append(esc)

            token_name = m.group(1) or (m.group(2) if len(m.groups()) > 1 else None)
            if not token_name:
                continue

            if token_name in ('asctime', 'server_time'):
                if date_has_space:
                    has_split_asctime = True
                    columns.extend(['Date', 'Time'])
                else:
                    columns.append('Date' if token_name == 'asctime' else 'Server Time')
            else:
                columns.append(token_name.title())

            is_last = (i == len(matches) - 1)
            if token_name == 'message' or is_last:
                field_pattern = f'(?P<{token_name}>.*)'
            elif token_name in ('asctime', 'server_time'):
                if literal.endswith('[') or literal.endswith('('):
                    field_pattern = f'(?P<{token_name}>[^]\)]+)'
                else:
                    field_pattern = f'(?P<{token_name}>{ASCTIME_REGEX})'
            elif token_name in ('process', 'thread', 'lineno'):
                field_pattern = f'(?P<{token_name}>\\d+)'
            elif token_name == 'levelname':
                field_pattern = f'(?P<{token_name}>[A-Za-z]+)\\s*'
            else:
                field_pattern = f'(?P<{token_name}>\\S+)'

            regex_parts.append(field_pattern)
            last_end = m.end()

        literal = format_str[last_end:]
        if literal:
            esc = re.escape(literal)
            esc = re.sub(r'\\\s+', lambda _: r'\s+', esc)
            regex_parts.append(esc)

        regex_parts.append('$')
        compiled = re.compile(''.join(regex_parts))

        msg_idx = -1
        for idx, col in enumerate(columns):
            if col.lower() == 'message':
                msg_idx = idx
                break
        if msg_idx == -1 and columns:
            msg_idx = len(columns) - 1

        return columns, compiled, has_split_asctime, msg_idx

    def load_details(self, name):
        """
        Get possible columns for this log file (using format setting) and load all
        old log files for the selected log file.
        """
        self.name = name
        self.columns = []
        self.log_files = []
        self.path = ""
        self.compiled_regex = None
        self.has_split_asctime = False
        self.msg_idx = -1

        ext = getattr(settings, 'LOG_FILE_EXTENSION', '.log')
        base_name = name[:-len(ext)] if name.endswith(ext) else name
        expected_default_name = f"{base_name}{ext}"

        matched_log = None
        for log in self.logs:
            filename = log.get('name', '')
            log_basename = log.get('basename', '')
            if (
                log_basename == name
                or log_basename == expected_default_name
                or filename.endswith(expected_default_name)
                or log_basename.startswith(base_name)
                or name.startswith(log_basename)
                or (base_name and name.startswith(base_name))
            ):
                matched_log = log
                break

        if not matched_log:
            self.columns = ['Log']
            self.compiled_regex = re.compile(r'^(?P<message>.*)$')
            self.msg_idx = 0
            return

        filename = matched_log.get('name')
        formatter_name = matched_log.get('formatter')
        formatter_setting = self.formatters.get(formatter_name) if formatter_name else None

        format_str = None
        style = None
        datefmt = None

        if formatter_setting and isinstance(formatter_setting, dict):
            format_str = formatter_setting.get('format')
            style = formatter_setting.get('style')
            datefmt = formatter_setting.get('datefmt')

        if format_str:
            cols, rgx, split_asc, m_idx = self._build_parser(format_str, style, datefmt)
            self.columns = cols
            self.compiled_regex = rgx
            self.has_split_asctime = split_asc
            self.msg_idx = m_idx
        else:
            default_fmt = '%(levelname)s:%(name)s:%(message)s'
            cols, rgx, split_asc, m_idx = self._build_parser(default_fmt)
            self.columns = cols
            self.compiled_regex = rgx
            self.has_split_asctime = split_asc
            self.msg_idx = m_idx

        self.path = os.path.dirname(os.path.abspath(filename))
        if os.path.isdir(self.path):
            discovered = [
                f for f in os.listdir(self.path)
                if os.path.isfile(os.path.join(self.path, f)) and (
                    expected_default_name in f
                    or f == matched_log.get('basename')
                    or f.startswith(base_name)
                )
            ]
            self.log_files = sorted(discovered)
        if not self.log_files:
            self.log_files = [matched_log.get('basename', expected_default_name)]

    def get_columns(self):
        return self.columns

    def get_log_files(self):
        return self.log_files

    def _parse_line(self, line):
        if not self.compiled_regex:
            return [line]
        m = self.compiled_regex.match(line)
        if not m:
            return None
        data = m.groupdict()
        row = []
        for col in self.columns:
            if col == 'Date' and self.has_split_asctime:
                ts = data.get('asctime') or data.get('server_time') or ''
                row.append(ts.split(' ', 1)[0].strip() if ' ' in ts else ts.strip())
            elif col == 'Time' and self.has_split_asctime:
                ts = data.get('asctime') or data.get('server_time') or ''
                row.append(ts.split(' ', 1)[1].strip() if ' ' in ts else '')
            else:
                key = col.lower().replace(' ', '')
                val = data.get(key, '')
                row.append(val.strip() if isinstance(val, str) else str(val))
        return row

    def get_log_content(self, file):
        file_path = os.path.join(self.path, file)
        if not os.path.isfile(file_path):
            return []

        rows = []
        with open(file_path, "r", encoding="utf-8", errors="replace") as log_file:
            lines = log_file.readlines()

        if not lines:
            return []

        # Check if first non-empty line matches current parser; if not, try fallback auto-detection
        first_non_empty = next((l.rstrip('\r\n') for l in lines if l.strip()), None)
        if first_non_empty and self.compiled_regex and not self.compiled_regex.match(first_non_empty):
            for fallback_fmt, f_style, f_datefmt in COMMON_FALLBACK_FORMATS:
                cols, rgx, split_asc, m_idx = self._build_parser(fallback_fmt, f_style, f_datefmt)
                if rgx.match(first_non_empty):
                    self.columns = cols
                    self.compiled_regex = rgx
                    self.has_split_asctime = split_asc
                    self.msg_idx = m_idx
                    break

        for line in lines:
            line_clean = line.rstrip('\r\n')
            if not line_clean and not rows:
                continue
            parsed = self._parse_line(line_clean)
            if parsed is not None:
                rows.append(parsed)
            else:
                target_idx = self.msg_idx if self.msg_idx != -1 else (len(self.columns) - 1)
                if rows:
                    rows[-1][target_idx] += '\n' + line_clean
                else:
                    row = [''] * len(self.columns)
                    row[target_idx] = line_clean
                    rows.append(row)

        return rows
