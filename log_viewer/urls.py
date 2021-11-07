from django.urls import path

from log_viewer import views

urlpatterns = [
    path('', views.LogHome.as_view(), name='log_home'),
]
