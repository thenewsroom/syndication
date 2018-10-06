from django.conf.urls.defaults import *

urlpatterns = patterns('',
    url('^(?P<model>[\w]+)/(?P<object_id>[\d]+)/$', 'penseive.views.details'),
    url('^entity/$', 'penseive.views.entity'),
    url('^entity/(?P<type>[\w\s]+)/$', 'penseive.views.entities'),
    url('^entity/(?P<type>[\w\s]+)/(?P<name>.+)/$', 'penseive.views.entity_list'),
)
