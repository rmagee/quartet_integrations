# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

from django.conf.urls import url, include

from quartet_integrations.urls import urlpatterns as quartet_integrations_urls

app_name = 'quartet_integrations'

urlpatterns = [
    url(r'^', include(quartet_integrations_urls)),

]
