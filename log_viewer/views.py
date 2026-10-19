from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from .utils import LogManager

manager = LogManager()


class LogHome(TemplateView):
    template_name = 'log_viewer/log_home.html'

    @method_decorator(login_required)
    @method_decorator(user_passes_test(lambda user: user.is_superuser))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_manager(self):
        return LogManager()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log_manager = self.get_manager()
        context['site_name'] = getattr(settings, 'SITE_NAME', 'LogViewer')
        context['logs'] = log_manager.get_logs()
        log_name = self.request.GET.get('name')
        log_child = self.request.GET.get('child')
        columns = []
        if log_name:
            log_manager.load_details(log_name)
            columns = log_manager.get_columns()
            context['log_name'] = log_name
            context['files'] = log_manager.get_log_files()
            file_name = log_child if log_child else log_name
            context['rows'] = log_manager.get_log_content(file_name)
        context['columns'] = columns
        context['child'] = log_child
        return context
