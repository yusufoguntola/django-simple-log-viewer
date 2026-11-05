import re
from django.conf import settings
from django.utils.module_loading import import_string

# Default configuration settings
DEFAULT_CONFIG = {
    'PAGE_SIZE': 50,
    'MAX_LINES': 20000,
    'MAX_FILE_SIZE_MB': 250,
    'DEFAULT_THEME': 'dark',
    'AUTO_REFRESH_INTERVALS': [0, 5, 10, 30, 60],
    'DEFAULT_AUTO_REFRESH': 0,
    'SANITIZATION_ENABLED': True,
    'PAYLOAD_MAX_LENGTH': 250,
    'ARRAY_MAX_ITEMS': 5,
    'SUPERUSER_ONLY': True,
    'PERMISSIONS_CHECK': None,
    'EXCLUDE_FILES': [],
    'CACHE_ENABLED': True,
    'CACHE_TIMEOUT': 15,
    'HOURLY_CHART_ENABLED': True,
    'REVERSE_ORDER': True,
    'FILE_SEARCH_DIRECTORIES': [],
    'SITE_NAME': 'LogViewer',
    'ENTITY_PATTERNS': [
        r'(?i)\b(?:request|request_id|requestid|req_id|reqid)[\s:=#]+([a-zA-Z0-9_\-]+)',
        r'(?i)\b(?:trace|trace_id|traceid)[\s:=#]+([a-zA-Z0-9_\-]+)',
        r'(?i)\b(?:correlation|correlation_id|correlationid)[\s:=#]+([a-zA-Z0-9_\-]+)',
        r'(?i)\b(?:user|user_id|userid)[\s:=#]+([a-zA-Z0-9_\-]+)',
        r'(?i)\b(?:task|task_id|taskid)[\s:=#]+([a-zA-Z0-9_\-]+)',
        r'(?i)\b(?:order|order_id|orderid|transaction|tx_id)[\s:=#]+([a-zA-Z0-9_\-]+)',
        r'#([a-zA-Z0-9_\-]+)',
    ],
    'LIFECYCLE_STAGES': [
        {
            'name': 'Drafting / Creation',
            'color': 'blue',
            'keywords': ['draft', 'create', 'created', 'creating', 'init', 'initialize', 'new'],
        },
        {
            'name': 'Scheduling',
            'color': 'indigo',
            'keywords': ['schedule', 'scheduled', 'scheduling', 'cron', 'delayed', 'defer'],
        },
        {
            'name': 'Approval / Validation',
            'color': 'purple',
            'keywords': ['approve', 'approved', 'approval', 'validate', 'validated', 'verify', 'authorized'],
        },
        {
            'name': 'Queue & Processing',
            'color': 'cyan',
            'keywords': ['queue', 'queued', 'process', 'processing', 'running', 'in_progress', 'worker'],
        },
        {
            'name': 'Dispatch / Delivery',
            'color': 'teal',
            'keywords': ['send', 'sending', 'sent', 'dispatch', 'dispatched', 'broadcast', 'delivered', 'notified'],
        },
        {
            'name': 'Completion',
            'color': 'green',
            'keywords': ['complete', 'completed', 'success', 'succeeded', 'finished', 'done', 'ok'],
        },
        {
            'name': 'Failures / Errors',
            'color': 'red',
            'keywords': ['fail', 'failed', 'failure', 'error', 'exception', 'rejected', 'abort', 'fatal', 'crash'],
        },
    ],
}


class LogViewerConfigHelper:
    """
    Helper class to access log viewer configuration settings
    with fallback to defaults.
    """

    @classmethod
    def get(cls, key, default=None):
        setting_key = f'LOG_VIEWER_{key}'
        if hasattr(settings, setting_key):
            return getattr(settings, setting_key)
        if hasattr(settings, key):
            return getattr(settings, key)
        if default is not None:
            return default
        return DEFAULT_CONFIG.get(key)

    @classmethod
    def page_size(cls):
        return cls.get('PAGE_SIZE', 50)

    @classmethod
    def max_lines(cls):
        return cls.get('MAX_LINES', 20000)

    @classmethod
    def max_file_size_mb(cls):
        return cls.get('MAX_FILE_SIZE_MB', 250)

    @classmethod
    def default_theme(cls):
        return cls.get('DEFAULT_THEME', 'dark')

    @classmethod
    def auto_refresh_intervals(cls):
        return cls.get('AUTO_REFRESH_INTERVALS', [0, 5, 10, 30, 60])

    @classmethod
    def default_auto_refresh(cls):
        return cls.get('DEFAULT_AUTO_REFRESH', 0)

    @classmethod
    def sanitization_enabled(cls):
        return cls.get('SANITIZATION_ENABLED', True)

    @classmethod
    def payload_max_length(cls):
        return cls.get('PAYLOAD_MAX_LENGTH', 250)

    @classmethod
    def array_max_items(cls):
        return cls.get('ARRAY_MAX_ITEMS', 5)

    @classmethod
    def entity_patterns(cls):
        return cls.get('ENTITY_PATTERNS', DEFAULT_CONFIG['ENTITY_PATTERNS'])

    @classmethod
    def lifecycle_stages(cls):
        return cls.get('LIFECYCLE_STAGES', DEFAULT_CONFIG['LIFECYCLE_STAGES'])

    @classmethod
    def superuser_only(cls):
        return cls.get('SUPERUSER_ONLY', True)

    @classmethod
    def permissions_check(cls):
        checker = cls.get('PERMISSIONS_CHECK', None)
        if isinstance(checker, str):
            try:
                return import_string(checker)
            except ImportError:
                return None
        return checker

    @classmethod
    def check_user_permission(cls, user, request=None):
        checker = cls.permissions_check()
        if checker and callable(checker):
            return bool(checker(user, request))
        if not user or not user.is_authenticated:
            return False
        if cls.superuser_only():
            return bool(getattr(user, 'is_superuser', False))
        return bool(getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False))

    @classmethod
    def exclude_files(cls):
        return cls.get('EXCLUDE_FILES', [])

    @classmethod
    def cache_enabled(cls):
        return cls.get('CACHE_ENABLED', True)

    @classmethod
    def cache_timeout(cls):
        return cls.get('CACHE_TIMEOUT', 15)

    @classmethod
    def hourly_chart_enabled(cls):
        return cls.get('HOURLY_CHART_ENABLED', True)

    @classmethod
    def reverse_order(cls):
        return cls.get('REVERSE_ORDER', True)

    @classmethod
    def file_search_directories(cls):
        return cls.get('FILE_SEARCH_DIRECTORIES', [])

    @classmethod
    def site_name(cls):
        return cls.get('SITE_NAME', getattr(settings, 'SITE_NAME', 'LogViewer'))
