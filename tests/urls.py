# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

from django.urls import re_path, include

from quartet_integrations.urls import urlpatterns as quartet_integrations_urls
from serialbox.api.urls import urlpatterns as serialbox_urls

app_name = "quartet_integrations"

urlpatterns = [
    re_path(r"^", include(quartet_integrations_urls)),
    re_path(r"^", include(serialbox_urls)),
]
