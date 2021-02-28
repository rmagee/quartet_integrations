from django.conf.urls import url
from quartet_integrations.tracelink.views import TraceLinkNumberRangeView

app_name = 'quartet_integrations'

urlpatterns = [
    url(
        r'soap/snx/snrequest/?',
        TraceLinkNumberRangeView.as_view(), name="tracelinkSNX"
    ),
]
