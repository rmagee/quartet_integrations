# -*- coding: utf-8 -*-
from django.conf.urls import url, include
from .opsm.urls import urlpatterns as opsm_urls
from .rocit.urls import urlpatterns as rocit_urls
from .systech.guardian.urls import urlpatterns as guardian_urls
from .systech.unitrace.urls import urlpatterns as unitrace_urls
from .tracelink.urls import urlpatterns as tracelink_urls
from .generic.urls import urlpatterns as debugging_urls

urlpatterns = [
    url(r'^', include(opsm_urls)),
    url(r'^', include(rocit_urls)),
    url(r'^', include(guardian_urls)),
    url(r'^', include(unitrace_urls)),
    url(r'^', include(tracelink_urls)),
    url(r'^', include(debugging_urls))
]
