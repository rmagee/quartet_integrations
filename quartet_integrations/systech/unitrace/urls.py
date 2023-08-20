from django.urls import re_path
from quartet_integrations.systech.unitrace.views import UniTraceNumberRangeView

app_name = "quartet_integrations"

urlpatterns = [
    re_path(
        r"unitrace/NumberRangeService/?",
        UniTraceNumberRangeView.as_view(),
        name="unitraceNumberRangeService",
    ),
]
