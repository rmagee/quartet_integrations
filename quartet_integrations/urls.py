# -*- coding: utf-8 -*-
from django.conf.urls import url, include

from .rocit.urls import urlpatterns as rocit_urls
from .opsm.urls import urlpatterns as opsm_urls

urlpatterns = [
    url(r'^', include(rocit_urls)),
    url(r'^', include(opsm_urls))
]
