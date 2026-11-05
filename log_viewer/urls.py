from django.urls import path
from log_viewer import views

urlpatterns = [
    path('', views.LogHome.as_view(), name='log_home'),
    path('api/overview/', views.LogAnalyticsOverviewAPI.as_view(), name='log_analytics_overview'),
    path('api/logs/', views.LogAnalyticsLogsAPI.as_view(), name='log_analytics_logs'),
    path('api/scan/', views.LogAnalyticsScanAPI.as_view(), name='log_analytics_scan'),
    path('api/detail/', views.LogAnalyticsDetailAPI.as_view(), name='log_analytics_detail'),
    path('api/files/', views.LogAnalyticsFilesAPI.as_view(), name='log_analytics_files'),
    path('api/export/', views.LogAnalyticsExportAPI.as_view(), name='log_analytics_export'),
]
