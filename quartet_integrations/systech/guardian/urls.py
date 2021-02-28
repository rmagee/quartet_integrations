# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2020 SerialLab Corp.  All rights reserved.
from django.conf.urls import url
from quartet_integrations.systech.guardian.views import GuardianNumberRangeView
from quartet_integrations.systech.guardian.views import GuardianCapture

app_name = 'quartet_integrations'

urlpatterns = [
    url(
        r'guardian/NumberRangeService/?',
        GuardianNumberRangeView.as_view(), name="guardianNumberRangeService"
    ),
    url(
        r'guardian/guardian-capture/?',
        GuardianCapture.as_view(), name="guardianCapture"
    )
]
