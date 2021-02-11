from django.conf.urls import url
from quartet_integrations.systech.unitrace.views import UniTraceNumberRangeView

app_name = 'quartet_integrations'

urlpatterns = [
    url(
        r'unitrace/NumberRangeService/?',
        UniTraceNumberRangeView.as_view(), name="unitraceNumberRangeService"
    ),
]
