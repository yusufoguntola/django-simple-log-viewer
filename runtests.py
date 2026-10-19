#!/usr/bin/env python
import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

def run_tests():
    if not settings.configured:
        settings.configure(
            SECRET_KEY='test-secret-key-for-django-simple-log-viewer',
            INSTALLED_APPS=[
                'django.contrib.auth',
                'django.contrib.contenttypes',
                'django.contrib.sessions',
                'log_viewer',
            ],
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            TEMPLATES=[
                {
                    'BACKEND': 'django.template.backends.django.DjangoTemplates',
                    'APP_DIRS': True,
                    'OPTIONS': {
                        'context_processors': [
                            'django.template.context_processors.request',
                            'django.contrib.auth.context_processors.auth',
                        ],
                    },
                },
            ],
            ROOT_URLCONF='log_viewer.urls',
            LOG_FILE_EXTENSION='.log',
        )
    django.setup()
    TestRunner = get_runner(settings)
    runner = TestRunner(verbosity=2)
    failures = runner.run_tests(['log_viewer'])
    sys.exit(bool(failures))

if __name__ == '__main__':
    run_tests()
