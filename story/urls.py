from django.conf.urls import url

from story import views


urlpatterns = [
    url(r'^user-monitor$', views.user_monitor),
    url(r'^buyer-config$', views.get_buyer_config),
]
