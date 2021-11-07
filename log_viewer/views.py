from django.conf import settings
from django.views.generic import TemplateView

from .utils import LogManager

manager = LogManager()


class LogHome(TemplateView):
    template_name = 'log_viewer/log_home.html'

    def get_context_data(self, **kwargs):
        context = super(LogHome, self).get_context_data(**kwargs)
        context['site_name'] = getattr(settings, 'SITE_NAME', 'LogViewer')
        context['logs'] = manager.get_logs()
        log_name = self.request.GET.get('name')
        log_child = self.request.GET.get('child')
        columns = []
        if log_name:
            manager.load_details(log_name[:log_name.rindex('.')])
            columns = manager.get_columns()
            context['log_name'] = log_name
            context['files'] = manager.get_log_files()
            file_name = log_child if log_child else log_name
            context['rows'] = manager.get_log_content(file_name)
        context['columns'] = columns
        context['child'] = log_child
        return context
