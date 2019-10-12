# -*- coding: utf-8 -*-
from django.conf.urls import url, include
from .opsm.urls import urlpatterns as opsm_urls
from quartet_integrations.rocit.views import RetrievePackagingHierarchyView

urlpatterns = [
    url(r'^', include(opsm_urls)),
    url(
        r'PackagingHierarchyServiceAMService',
        RetrievePackagingHierarchyView.as_view(),
        name='retrievePackagingHierarchyResponse'
    )
]
