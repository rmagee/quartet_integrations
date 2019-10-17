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
# Copyright 2019 SerialLab Corp.  All rights reserved.
from django.conf.urls import url
from quartet_integrations.opsm.views import OPSMNumberRangeView, \
    CaptureInterface

app_name = 'quartet_integrations'
# /opsmservices-transactions/SerialGenRequestServiceAMService?wsdl
# SerialGenRequestServiceAMServiceSoapHttpPort
urlpatterns = [
    url(
        r'opsmservices-transactions/SerialGenRequestServiceAMService',
        OPSMNumberRangeView.as_view(), name="numberRangeService"
    ),
    url(
        r'opsmservices-epcis/Capture',
        CaptureInterface.as_view(), name='opsmCapture'
    )
]
