# -*- coding: utf-8 -*-
from django.urls import re_path, include
from .opsm.urls import urlpatterns as opsm_urls
from .rocit.urls import urlpatterns as rocit_urls
from .systech.guardian.urls import urlpatterns as guardian_urls
from .systech.unitrace.urls import urlpatterns as unitrace_urls
from .tracelink.urls import urlpatterns as tracelink_urls
from .generic.urls import urlpatterns as debugging_urls

urlpatterns = [
    re_path(r"^", include(opsm_urls)),
    re_path(r"^", include(rocit_urls)),
    re_path(r"^", include(guardian_urls)),
    re_path(r"^", include(unitrace_urls)),
    re_path(r"^", include(tracelink_urls)),
    re_path(r"^", include(debugging_urls)),
]
