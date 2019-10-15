# -*- coding: utf-8 -*-
from django.conf.urls import url, include
from .opsm.urls import urlpatterns as opsm_urls
from .rocit.urls import urlpatterns as rocit_urls

urlpatterns = [
    url(r'^', include(opsm_urls)),
    url(r'^', include(rocit_urls))
]
