from django.urls import re_path
from quartet_integrations.tracelink.views import TraceLinkNumberRangeView

app_name = "quartet_integrations"

urlpatterns = [
    re_path(
        r"soap/snx/snrequest/?", TraceLinkNumberRangeView.as_view(), name="tracelinkSNX"
    ),
]
