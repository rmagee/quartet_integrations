# -*- coding: utf-8 -*-
<<<<<<< HEAD
from django.conf.urls import url, include

from .rocit.urls import urlpatterns as rocit_urls
from .opsm.urls import urlpatterns as opsm_urls

urlpatterns = [
    url(r'^', include(rocit_urls)),
    url(r'^', include(opsm_urls))
=======
from django.conf.urls import url
from quartet_integrations.rocit.views import RetrievePackagingHierarchyView

urlpatterns = [
    url(
        r'PackagingHierarchyServiceAMService', RetrievePackagingHierarchyView.as_view(), name='retrievePackagingHierarchyResponse'
    )
>>>>>>> 085fbd778420a62729bfbbe01f3d6d909ed0d86a
]
