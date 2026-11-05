import json
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView

from .analytics import LogAnalyticsEngine
from .conf import LogViewerConfigHelper as config
from .utils import LogManager


def log_viewer_permission_check(user, request=None):
    return config.check_user_permission(user, request)


class LogViewerBaseAPIView(View):
    """
    Base API view enforcing user permissions and returning JSON responses.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        if not log_viewer_permission_check(request.user, request):
            err_msg = 'Super-admin access required' if config.superuser_only() else 'Permission denied'
            return JsonResponse({'error': err_msg}, status=403)
        return super().dispatch(request, *args, **kwargs)


class LogHome(TemplateView):
    template_name = 'log_viewer/analytics_dashboard.html'

    def get_template_names(self):
        if self.request.GET.get('view') == 'classic':
            return ['log_viewer/log_home.html']
        return ['log_viewer/analytics_dashboard.html']

    @method_decorator(login_required)
    @method_decorator(user_passes_test(lambda user: log_viewer_permission_check(user)))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_manager(self):
        return LogManager()

    def get_engine(self):
        return LogAnalyticsEngine(self.get_manager())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log_manager = self.get_manager()
        engine = self.get_engine()

        # Backward compatibility fields
        context['site_name'] = config.site_name()
        context['logs'] = log_manager.get_logs()
        log_name = self.request.GET.get('name')
        log_child = self.request.GET.get('child')
        columns = []
        rows = []
        files = []

        available_files = engine.get_available_files()
        active_file_name = None

        if log_name:
            log_manager.load_details(log_name)
            columns = log_manager.get_columns()
            files = log_manager.get_log_files()
            file_name = log_child if log_child else log_name
            rows = log_manager.get_log_content(file_name)
            active_file_name = file_name
        elif available_files:
            active_file_name = available_files[0]['name']
            log_manager.load_details(active_file_name)
            columns = log_manager.get_columns()
            files = log_manager.get_log_files()
            rows = log_manager.get_log_content(active_file_name)

        context['log_name'] = log_name or active_file_name
        context['active_file'] = active_file_name
        context['columns'] = columns
        context['child'] = log_child
        context['files'] = files
        context['rows'] = rows

        # Rich Analytics Dashboard Context
        context['available_files'] = available_files
        context['overview'] = engine.get_overview(active_file_name)
        context['default_theme'] = config.default_theme()
        context['auto_refresh_intervals'] = config.auto_refresh_intervals()
        context['default_auto_refresh'] = config.default_auto_refresh()
        context['hourly_chart_enabled'] = config.hourly_chart_enabled()
        context['page_size'] = config.page_size()
        context['view_mode'] = self.request.GET.get('view', 'analytics')
        context['is_super_admin'] = getattr(self.request.user, 'is_superuser', False)
        context['user_display'] = str(self.request.user)

        return context


class LogAnalyticsOverviewAPI(LogViewerBaseAPIView):
    """
    Returns KPIs, severity counts, and 24-hour traffic distribution.
    GET /api/overview/?file=<file_name>&date=<YYYY-MM-DD>
    """

    def get(self, request, *args, **kwargs):
        file_name = request.GET.get('file') or request.GET.get('name')
        date = request.GET.get('date')
        engine = LogAnalyticsEngine()
        data = engine.get_overview(file_name=file_name, date=date)
        return JsonResponse(data)


class LogAnalyticsLogsAPI(LogViewerBaseAPIView):
    """
    Paged query for log entries with real-time payload sanitization and fast filtering.
    GET /api/logs/?file=<name>&level=<ALL|ERROR|WARN|INFO|DEBUG>&keyword=<q>&entity_id=<id>&page=1&limit=50
    """

    def get(self, request, *args, **kwargs):
        file_name = request.GET.get('file') or request.GET.get('name')
        level = request.GET.get('level')
        keyword = request.GET.get('keyword')
        entity_id = request.GET.get('entity_id') or request.GET.get('id') or request.GET.get('trace_id')
        page = request.GET.get('page', 1)
        limit = request.GET.get('limit', config.page_size())
        reverse = request.GET.get('reverse', 'true').lower() in ('true', '1', 'yes')
        all_files = request.GET.get('all', 'false').lower() in ('true', '1', 'yes')

        engine = LogAnalyticsEngine()
        data = engine.get_logs_page(
            file_name=file_name,
            level=level,
            keyword=keyword,
            entity_id=entity_id,
            page=page,
            limit=limit,
            reverse=reverse,
            all_files=all_files,
        )
        return JsonResponse(data)


class LogAnalyticsScanAPI(LogViewerBaseAPIView):
    """
    Targeted entity / correlation scanner (Requests, Traces, Users, Tasks, Transactions, etc.).
    GET /api/scan/?id=<id>&file=<file>&date_scope=<selected|all|range>&start_date=<YYYY-MM-DD>&end_date=<YYYY-MM-DD>&level=<level>
    """

    def get(self, request, *args, **kwargs):
        entity_id = request.GET.get('id') or request.GET.get('entity_id') or request.GET.get('trace_id')
        if not entity_id:
            return JsonResponse({'error': 'Parameter "id" is required'}, status=400)

        file_name = request.GET.get('file') or request.GET.get('name')
        date_scope = request.GET.get('date_scope', 'selected')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        level_filter = request.GET.get('level')

        engine = LogAnalyticsEngine()
        data = engine.scan_entity(
            entity_id=entity_id,
            file_name=file_name,
            date_scope=date_scope,
            start_date=start_date,
            end_date=end_date,
            level_filter=level_filter,
        )
        return JsonResponse(data)


class LogAnalyticsDetailAPI(LogViewerBaseAPIView):
    """
    Retrieves complete raw log payload without truncation or stripping for the detail modal.
    GET /api/detail/?id=<file:index>
    """

    def get(self, request, *args, **kwargs):
        detail_id = request.GET.get('id')
        if not detail_id:
            return JsonResponse({'error': 'Parameter "id" is required'}, status=400)

        engine = LogAnalyticsEngine()
        data = engine.get_log_detail(detail_id)
        if not data:
            return JsonResponse({'error': 'Log entry not found'}, status=404)
        return JsonResponse(data)


class LogAnalyticsFilesAPI(LogViewerBaseAPIView):
    """
    Returns list of all available log files, sizes on disk, and timestamps.
    GET /api/files/
    """

    def get(self, request, *args, **kwargs):
        engine = LogAnalyticsEngine()
        files = engine.get_available_files()
        return JsonResponse({'files': files, 'count': len(files)})


class LogAnalyticsExportAPI(LogViewerBaseAPIView):
    """
    Exports filtered logs as JSON or CSV file download.
    GET /api/export/?file=<file>&format=<json|csv>&level=<level>&keyword=<keyword>
    """

    def get(self, request, *args, **kwargs):
        file_name = request.GET.get('file') or request.GET.get('name')
        export_fmt = request.GET.get('format', 'json').lower()
        level = request.GET.get('level')
        keyword = request.GET.get('keyword')

        engine = LogAnalyticsEngine()
        content, content_type = engine.export_data(
            file_name=file_name,
            export_format=export_fmt,
            level=level,
            keyword=keyword,
        )

        filename = f"logs_{file_name or 'export'}.{export_fmt}"
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
