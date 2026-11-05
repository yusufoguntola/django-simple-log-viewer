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

    def test_zero_configuration_upgrade_default_dashboard(self):
        """
        Ensures existing projects upgrading from PyPI without any new settings
        automatically receive the new analytics dashboard by default.
        """
        logging_config = {
            'version': 1,
            'handlers': {
                'file': {
                    'filename': self.log_file,
                },
            },
        }
        with override_settings(LOGGING=logging_config):
            request = self.factory.get('/log-viewer/')
            request.user = self.superuser
            response = LogHome.as_view()(request)
            self.assertEqual(response.status_code, 200)

            # Template used by default is the new analytics dashboard
            self.assertEqual(response.template_name, ['log_viewer/analytics_dashboard.html'])

            # Dashboard context populated automatically without any query param
            context = response.context_data
            self.assertEqual(context['active_file'], 'django_test.log')
            self.assertIn('overview', context)
            self.assertEqual(context['overview']['total_entries'], 1)
            self.assertIn('available_files', context)
            self.assertEqual(len(context['available_files']), 1)


class LogAnalyticsEngineTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, 'app.log')
        self.rotated_log = os.path.join(self.test_dir, 'app.log.2023-11-22')
        self.secret_log = os.path.join(self.test_dir, 'secret.log')

        # Create primary log
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("2023-11-22 08:15:00,100 [INFO] app.auth: User 42 logged in successfully\n")
            f.write("2023-11-22 10:30:00,200 [INFO] app.orders: Order ORD-89 created by admin\n")
            f.write('2023-11-22 10:31:04,300 [INFO] app.dispatch: Order ORD-89 approved and batch payload sent: ["item_001", "item_002", "item_003", "item_004", "item_005", "item_006"]\n')
            f.write("2023-11-22 10:32:00,400 [WARN] app.network: Latency high for task req-9988\n")
            f.write("2023-11-22 10:33:00,500 [ERROR] app.sms: Dispatch failed for order ORD-89 connection timeout\n")

        # Create rotated historical log
        with open(self.rotated_log, 'w', encoding='utf-8') as f:
            f.write("2023-11-20 14:00:00,000 [INFO] app.orders: Order ORD-89 scheduled\n")
            f.write("2023-11-20 14:05:00,000 [INFO] app.orders: Order ORD-77 completed\n")

        with open(self.secret_log, 'w', encoding='utf-8') as f:
            f.write("2023-11-22 12:00:00,000 [INFO] app.secret: Hidden secret log\n")

        self.logging_config = {
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

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_available_files_discovery_and_exclusion(self):
        with override_settings(LOGGING=self.logging_config, LOG_VIEWER_EXCLUDE_FILES=['secret']):
            from log_viewer.analytics import LogAnalyticsEngine
            engine = LogAnalyticsEngine()
            files = engine.get_available_files()
            file_names = [f['name'] for f in files]

            self.assertIn('app.log', file_names)
            self.assertIn('app.log.2023-11-22', file_names)
            self.assertNotIn('secret.log', file_names)

            # Check metadata fields
            app_info = next(f for f in files if f['name'] == 'app.log')
            self.assertTrue(app_info['is_primary'])
            self.assertGreater(app_info['size_bytes'], 0)
            self.assertIn('B', app_info['size_formatted'])

    def test_overview_kpis_and_histogram(self):
        with override_settings(LOGGING=self.logging_config):
            from log_viewer.analytics import LogAnalyticsEngine
            engine = LogAnalyticsEngine()
            overview = engine.get_overview('app.log')

            self.assertEqual(overview['file_name'], 'app.log')
            self.assertEqual(overview['total_entries'], 5)
            self.assertEqual(overview['error_count'], 1)
            self.assertEqual(overview['warning_count'], 1)
            self.assertEqual(overview['info_count'], 3)
            self.assertEqual(overview['error_rate'], '20.00%')

            # 24-hr histogram distribution check
            hourly = overview['hourly_traffic']
            self.assertEqual(len(hourly), 24)
            # Hour 10 has 4 entries (10:30, 10:31, 10:32, 10:33)
            self.assertEqual(hourly[10]['count'], 4)
            self.assertEqual(hourly[10]['error_count'], 1)
            # Hour 08 has 1 entry (08:15)
            self.assertEqual(hourly[8]['count'], 1)

            self.assertEqual(overview['peak_hour'], '10:00')
            self.assertTrue(overview['has_traffic_surge'])

    def test_payload_sanitization_dom_protection(self):
        from log_viewer.analytics import LogAnalyticsEngine
        engine = LogAnalyticsEngine()

        # Large array list sanitization
        sample_batch = 'Sent to: ["item_001", "item_002", "item_003", "item_004", "item_005", "item_006"]'
        res = engine.sanitize_payload(sample_batch)
        self.assertTrue(res['was_sanitized'])
        self.assertIn('📦 Array (6 items) stripped', res['sanitized'])

        # Giant array sanitization
        big_array = "Data: [" + ", ".join(str(i) for i in range(100)) + "]"
        res_arr = engine.sanitize_payload(big_array)
        self.assertTrue(res_arr['was_sanitized'])
        self.assertIn('📦 Array (100 items) stripped', res_arr['sanitized'])

        # Bearer token and password masking
        auth_msg = 'Headers: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz and password: "mysecretpassword123"'
        res_auth = engine.sanitize_payload(auth_msg)
        self.assertIn('Bearer [REDACTED_TOKEN]', res_auth['sanitized'])
        self.assertIn('password: "********"', res_auth['sanitized'])

    def test_paged_logs_and_filtering(self):
        with override_settings(LOGGING=self.logging_config):
            from log_viewer.analytics import LogAnalyticsEngine
            engine = LogAnalyticsEngine()

            # Test level filter: ERROR
            res_err = engine.get_logs_page(file_name='app.log', level='ERROR')
            self.assertEqual(res_err['total_matched'], 1)
            self.assertEqual(res_err['entries'][0]['level'], 'ERROR')

            # Test keyword search
            res_kw = engine.get_logs_page(file_name='app.log', keyword='timeout')
            self.assertEqual(res_kw['total_matched'], 1)
            self.assertIn('timeout', res_kw['entries'][0]['message'].lower())

            # Test pagination
            res_paged = engine.get_logs_page(file_name='app.log', page=1, limit=2)
            self.assertEqual(len(res_paged['entries']), 2)
            self.assertEqual(res_paged['total_pages'], 3)
            self.assertTrue(res_paged['has_next'])

    def test_entity_trace_scanner(self):
        with override_settings(LOGGING=self.logging_config):
            from log_viewer.analytics import LogAnalyticsEngine
            engine = LogAnalyticsEngine()

            # Scan single file
            res_single = engine.scan_entity('ORD-89', file_name='app.log', date_scope='selected')
            self.assertEqual(res_single['total_found'], 3)
            self.assertEqual(res_single['levels_count']['error'], 1)
            self.assertEqual(res_single['levels_count']['info'], 2)

            # Check lifecycle stages mapping
            timeline = res_single['timeline']
            self.assertEqual(timeline[0]['stage'], 'Drafting / Creation')
            self.assertEqual(timeline[1]['stage'], 'Approval / Validation')
            self.assertEqual(timeline[2]['stage'], 'Failures / Errors')

            # Fast mode: Scan with level filter ERROR
            res_fast = engine.scan_entity('ORD-89', file_name='app.log', level_filter='ERROR')
            self.assertEqual(res_fast['total_found'], 1)
            self.assertEqual(res_fast['timeline'][0]['level'], 'ERROR')

            # Scan across all files (including rotated app.log.2023-11-22)
            res_all = engine.scan_entity('ORD-89', date_scope='all')
            self.assertEqual(res_all['total_found'], 4)

    def test_detail_payload_and_json_parsing(self):
        json_log = os.path.join(self.test_dir, 'json_app.log')
        with open(json_log, 'w', encoding='utf-8') as f:
            f.write('2023-11-22 12:00:00,000 [INFO] app.api: {"event": "order_placed", "order_id": "ORD-123", "amount": 99.5}\n')

        cfg = {
            'version': 1,
            'handlers': {'json_file': {'filename': json_log}},
        }
        with override_settings(LOGGING=cfg):
            from log_viewer.analytics import LogAnalyticsEngine
            engine = LogAnalyticsEngine()
            detail = engine.get_log_detail('json_app.log:0')
            self.assertIsNotNone(detail)
            self.assertTrue(detail['is_json'])
            self.assertEqual(detail['json_data']['order_id'], 'ORD-123')
            self.assertEqual(detail['json_data']['amount'], 99.5)

    def test_export_data_json_and_csv(self):
        with override_settings(LOGGING=self.logging_config):
            from log_viewer.analytics import LogAnalyticsEngine
            import json
            engine = LogAnalyticsEngine()

            # JSON export
            json_str, ctype = engine.export_data('app.log', export_format='json')
            self.assertEqual(ctype, 'application/json')
            parsed = json.loads(json_str)
            self.assertEqual(len(parsed), 5)

            # CSV export
            csv_str, ctype = engine.export_data('app.log', export_format='csv')
            self.assertEqual(ctype, 'text/csv')
            self.assertIn('ID,File,Timestamp,Level,Logger,Entities,Message', csv_str)
            self.assertIn('Order ORD-89', csv_str)


class LogAnalyticsAPITest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, 'api_app.log')

        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("2023-11-22 10:00:00,000 [INFO] app.test: System init\n")
            f.write("2023-11-22 10:05:00,000 [ERROR] app.test: Database error for req-55\n")

        self.logging_config = {
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

        self.superuser = User.objects.create_superuser(
            username='api_admin',
            email='admin@example.com',
            password='password123',
        )
        self.regular_user = User.objects.create_user(
            username='api_regular',
            email='regular@example.com',
            password='password123',
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_api_authentication_and_rbac(self):
        from log_viewer.views import LogAnalyticsOverviewAPI
        from django.contrib.auth.models import AnonymousUser

        # 1. Unauthenticated gets 401
        req = self.factory.get('/api/overview/')
        req.user = AnonymousUser()
        resp = LogAnalyticsOverviewAPI.as_view()(req)
        self.assertEqual(resp.status_code, 401)

        # 2. Regular non-superuser gets 403
        req = self.factory.get('/api/overview/')
        req.user = self.regular_user
        resp = LogAnalyticsOverviewAPI.as_view()(req)
        self.assertEqual(resp.status_code, 403)

        # 3. Superuser gets 200
        with override_settings(LOGGING=self.logging_config):
            req = self.factory.get('/api/overview/?file=api_app.log')
            req.user = self.superuser
            resp = LogAnalyticsOverviewAPI.as_view()(req)
            self.assertEqual(resp.status_code, 200)

    def test_api_logs_endpoint(self):
        from log_viewer.views import LogAnalyticsLogsAPI
        import json

        with override_settings(LOGGING=self.logging_config):
            req = self.factory.get('/api/logs/?file=api_app.log&level=ERROR')
            req.user = self.superuser
            resp = LogAnalyticsLogsAPI.as_view()(req)
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.content)
            self.assertEqual(data['total_matched'], 1)
            self.assertEqual(data['entries'][0]['level'], 'ERROR')

    def test_api_scan_endpoint(self):
        from log_viewer.views import LogAnalyticsScanAPI
        import json

        with override_settings(LOGGING=self.logging_config):
            req = self.factory.get('/api/scan/?id=55&file=api_app.log')
            req.user = self.superuser
            resp = LogAnalyticsScanAPI.as_view()(req)
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.content)
            self.assertEqual(data['total_found'], 1)
            self.assertEqual(data['timeline'][0]['level'], 'ERROR')

    def test_api_detail_endpoint(self):
        from log_viewer.views import LogAnalyticsDetailAPI
        import json

        with override_settings(LOGGING=self.logging_config):
            req = self.factory.get('/api/detail/?id=api_app.log:1')
            req.user = self.superuser
            resp = LogAnalyticsDetailAPI.as_view()(req)
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.content)
            self.assertIn('Database error', data['raw_message'])

    def test_api_export_endpoint(self):
        from log_viewer.views import LogAnalyticsExportAPI

        with override_settings(LOGGING=self.logging_config):
            req = self.factory.get('/api/export/?file=api_app.log&format=csv')
            req.user = self.superuser
            resp = LogAnalyticsExportAPI.as_view()(req)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp['Content-Type'], 'text/csv')
            self.assertIn('attachment; filename="logs_api_app.log.csv"', resp['Content-Disposition'])


class LogAnalyticsSettingsTest(TestCase):
    def test_custom_settings_overrides(self):
        with override_settings(
            LOG_VIEWER_PAGE_SIZE=120,
            LOG_VIEWER_DEFAULT_THEME='light',
            LOG_VIEWER_AUTO_REFRESH_INTERVALS=[5, 15, 60],
            LOG_VIEWER_SUPERUSER_ONLY=False,
            LOG_VIEWER_PAYLOAD_MAX_LENGTH=180,
        ):
            from log_viewer.conf import LogViewerConfigHelper as config
            self.assertEqual(config.page_size(), 120)
            self.assertEqual(config.default_theme(), 'light')
            self.assertEqual(config.auto_refresh_intervals(), [5, 15, 60])
            self.assertFalse(config.superuser_only())
            self.assertEqual(config.payload_max_length(), 180)

