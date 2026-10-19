import os
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from log_viewer.utils import LogManager
from log_viewer.views import LogHome

User = get_user_model()


class LogViewerUtilsTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, 'test_app.log')

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_empty_logging_setting(self):
        with override_settings(LOGGING={}):
            manager = LogManager()
            self.assertEqual(manager.get_logs(), [])
            manager.load_details('nonexistent')
            self.assertEqual(manager.get_columns(), ['Log'])
            self.assertEqual(manager.get_log_content('nonexistent.log'), [])

    def test_pathlib_and_str_filename_support(self):
        pathlib_file = Path(self.test_dir) / 'pathlib_app.log'
        logging_config = {
            'version': 1,
            'handlers': {
                'file1': {'filename': self.log_file},
                'file2': {'filename': pathlib_file},
            },
        }
        with override_settings(LOGGING=logging_config):
            manager1 = LogManager()
            logs = manager1.get_logs()
            self.assertIn('test_app.log', logs)
            self.assertIn('pathlib_app.log', logs)
            self.assertEqual(len(logs), 2)

            # Test instance isolation - new manager should not accumulate duplicates
            manager2 = LogManager()
            self.assertEqual(len(manager2.get_logs()), 2)

    def test_bracketed_format(self):
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("2026-10-19 12:00:00,123 [INFO] test_app: Operation completed successfully\n")
            f.write("2026-10-19 12:00:01,456 [ERROR] test_app: An error occurred\n")

        logging_config = {
            'version': 1,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                },
            },
            'handlers': {
                'file': {
                    'filename': self.log_file,
                    'formatter': 'standard',
                },
            },
        }
        with override_settings(LOGGING=logging_config):
            manager = LogManager()
            manager.load_details('test_app.log')
            cols = manager.get_columns()
            self.assertEqual(cols, ['Date', 'Time', 'Levelname', 'Name', 'Message'])

            rows = manager.get_log_content('test_app.log')
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0], ['2026-10-19', '12:00:00,123', 'INFO', 'test_app', 'Operation completed successfully'])
            self.assertEqual(rows[1], ['2026-10-19', '12:00:01,456', 'ERROR', 'test_app', 'An error occurred'])

    def test_hyphen_separated_format(self):
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("2026-10-19 12:00:00,123 - my_logger - WARNING - High memory usage\n")

        logging_config = {
            'version': 1,
            'formatters': {
                'hyphen': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                },
            },
            'handlers': {
                'file': {
                    'filename': self.log_file,
                    'formatter': 'hyphen',
                },
            },
        }
        with override_settings(LOGGING=logging_config):
            manager = LogManager()
            manager.load_details('test_app')
            cols = manager.get_columns()
            self.assertEqual(cols, ['Date', 'Time', 'Name', 'Levelname', 'Message'])

            rows = manager.get_log_content('test_app.log')
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0], ['2026-10-19', '12:00:00,123', 'my_logger', 'WARNING', 'High memory usage'])

    def test_django_docs_verbose_brace_format(self):
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("INFO 2026-10-19 12:00:00,123 my_module 1234 5678 User logged in\n")

        logging_config = {
            'version': 1,
            'formatters': {
                'verbose': {
                    'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                    'style': '{',
                },
            },
            'handlers': {
                'file': {
                    'filename': self.log_file,
                    'formatter': 'verbose',
                },
            },
        }
        with override_settings(LOGGING=logging_config):
            manager = LogManager()
            manager.load_details('test_app.log')
            cols = manager.get_columns()
            self.assertEqual(cols, ['Levelname', 'Date', 'Time', 'Module', 'Process', 'Thread', 'Message'])

            rows = manager.get_log_content('test_app.log')
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0], ['INFO', '2026-10-19', '12:00:00,123', 'my_module', '1234', '5678', 'User logged in'])

    def test_django_docs_simple_brace_format(self):
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("ERROR Database connection lost\n")

        logging_config = {
            'version': 1,
            'formatters': {
                'simple': {
                    'format': '{levelname} {message}',
                    'style': '{',
                },
            },
            'handlers': {
                'file': {
                    'filename': self.log_file,
                    'formatter': 'simple',
                },
            },
        }
        with override_settings(LOGGING=logging_config):
            manager = LogManager()
            manager.load_details('test_app.log')
            cols = manager.get_columns()
            self.assertEqual(cols, ['Levelname', 'Message'])

            rows = manager.get_log_content('test_app.log')
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0], ['ERROR', 'Database connection lost'])

    def test_padded_levelname_and_bracketed_asctime(self):
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("[2026-10-19 12:00:00,123] [INFO    ] Task finished\n")

        logging_config = {
            'version': 1,
            'formatters': {
                'custom': {
                    'format': '[%(asctime)s] [%(levelname)-8s] %(message)s',
                },
            },
            'handlers': {
                'file': {
                    'filename': self.log_file,
                    'formatter': 'custom',
                },
            },
        }
        with override_settings(LOGGING=logging_config):
            manager = LogManager()
            manager.load_details('test_app.log')
            cols = manager.get_columns()
            self.assertEqual(cols, ['Date', 'Time', 'Levelname', 'Message'])

            rows = manager.get_log_content('test_app.log')
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0], ['2026-10-19', '12:00:00,123', 'INFO', 'Task finished'])

    def test_multiline_tracebacks_merged_into_message(self):
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("2026-10-19 12:00:00,100 [INFO] app: Starting job\n")
            f.write("2026-10-19 12:00:01,200 [ERROR] app: Job failed\n")
            f.write("Traceback (most recent call last):\n")
            f.write('  File "/app/job.py", line 10, in run\n')
            f.write('    raise RuntimeError("Worker crashed")\n')
            f.write("RuntimeError: Worker crashed\n")
            f.write("2026-10-19 12:00:02,300 [INFO] app: Clean shutdown\n")

        logging_config = {
            'version': 1,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                },
            },
            'handlers': {
                'file': {
                    'filename': self.log_file,
                    'formatter': 'standard',
                },
            },
        }
        with override_settings(LOGGING=logging_config):
            manager = LogManager()
            manager.load_details('test_app.log')
            rows = manager.get_log_content('test_app.log')
            self.assertEqual(len(rows), 3)

            # Row 0
            self.assertEqual(rows[0][2], 'INFO')
            self.assertEqual(rows[0][4], 'Starting job')

            # Row 1 has the full traceback attached to Message
            self.assertEqual(rows[1][2], 'ERROR')
            expected_msg = (
                "Job failed\n"
                "Traceback (most recent call last):\n"
                '  File "/app/job.py", line 10, in run\n'
                '    raise RuntimeError("Worker crashed")\n'
                "RuntimeError: Worker crashed"
            )
            self.assertEqual(rows[1][4], expected_msg)

            # Row 2
            self.assertEqual(rows[2][2], 'INFO')
            self.assertEqual(rows[2][4], 'Clean shutdown')

    def test_rotated_log_files_discovery(self):
        # Create rotated log files
        rotated_1 = os.path.join(self.test_dir, 'test_app.log.1')
        rotated_2 = os.path.join(self.test_dir, 'test_app.log.2')
        with open(self.log_file, 'w') as f:
            f.write("INFO:app:main log\n")
        with open(rotated_1, 'w') as f:
            f.write("INFO:app:rotated 1\n")
        with open(rotated_2, 'w') as f:
            f.write("INFO:app:rotated 2\n")

        logging_config = {
            'version': 1,
            'handlers': {
                'file': {'filename': self.log_file},
            },
        }
        with override_settings(LOGGING=logging_config):
            manager = LogManager()
            manager.load_details('test_app.log')
            files = manager.get_log_files()
            self.assertIn('test_app.log', files)
            self.assertIn('test_app.log.1', files)
            self.assertIn('test_app.log.2', files)

    def test_fallback_auto_detection(self):
        # Handler does not specify formatter, but log file has standard timestamp format
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("2026-10-19 12:00:00,123 - app - INFO - Auto detected!\n")

        logging_config = {
            'version': 1,
            'handlers': {
                'file': {'filename': self.log_file},
            },
        }
        with override_settings(LOGGING=logging_config):
            manager = LogManager()
            manager.load_details('test_app.log')
            rows = manager.get_log_content('test_app.log')
            self.assertEqual(len(rows), 1)
            self.assertEqual(manager.get_columns(), ['Date', 'Time', 'Name', 'Levelname', 'Message'])
            self.assertEqual(rows[0][-1], 'Auto detected!')


class LogHomeViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, 'django_test.log')
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("2026-10-19 12:00:00,123 [INFO] django.request: Page loaded\n")

        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password123',
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='user@example.com',
            password='password123',
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_anonymous_user_redirected(self):
        request = self.factory.get('/log-viewer/')
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        response = LogHome.as_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_non_superuser_redirected(self):
        request = self.factory.get('/log-viewer/')
        request.user = self.regular_user
        response = LogHome.as_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_superuser_access_and_context(self):
        logging_config = {
            'version': 1,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                },
            },
            'handlers': {
                'file': {
                    'filename': self.log_file,
                    'formatter': 'standard',
                },
            },
        }
        with override_settings(LOGGING=logging_config, SITE_NAME='CustomApp'):
            request = self.factory.get('/log-viewer/?name=django_test.log')
            request.user = self.superuser
            response = LogHome.as_view()(request)
            self.assertEqual(response.status_code, 200)

            context = response.context_data
            self.assertEqual(context['site_name'], 'CustomApp')
            self.assertIn('django_test.log', context['logs'])
            self.assertEqual(context['log_name'], 'django_test.log')
            self.assertEqual(context['columns'], ['Date', 'Time', 'Levelname', 'Name', 'Message'])
            self.assertEqual(len(context['rows']), 1)
            self.assertEqual(context['rows'][0][4], 'Page loaded')
