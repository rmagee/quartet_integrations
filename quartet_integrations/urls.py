# -*- coding: utf-8 -*-
from django.conf.urls import url
from quartet_integrations.rocit.views import RetrievePackagingHierarchyView

urlpatterns = [
    url(
        r'PackagingHierarchyServiceAMService', RetrievePackagingHierarchyView.as_view(), name='retrievePackagingHierarchyResponse'
    )
]
