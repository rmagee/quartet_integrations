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
from django.contrib.auth import authenticate
from django.conf import settings
from django.db.models import ObjectDoesNotExist
from lxml import etree
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.authentication import BasicAuthentication
from rest_framework_xml import parsers

from logging import getLogger
from quartet_capture import views as capture_views
from quartet_capture.models import TaskParameter
from serialbox.api.views import AllocateView

logger = getLogger(__name__)

from quartet_integrations.rocit.views import DefaultXMLContent


class OPSMNumberRangeView(AllocateView):
    """
    Accepts an inbound request from an external system that thinks it's talking
    to an Oracle OPSM EPCIS 1.0 system.  This is basically part of an OPSM
    emulation layer.
    """
    content_negotiation_class = DefaultXMLContent

    parser_classes = [parsers.XMLParser]

    permission_classes = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.location_name = None

    def auth_user(self, username, password):
        """
        Authenticate user.
        """
        user = authenticate(username=username, password=password)
        if user:
            return user
        else:
            raise AuthenticationFailed('Username/password invalid.')

    def post(self, request):
        count = None
        gtin = None
        xpath_prefix = '//soapenv:Body/typ:createProcessSerialGenerationRequest/typ:serialGenerationRequest/'
        namespaces = {
            'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
            'typ': 'http://xmlns.oracle.com/apps/pas/transactions/transactionsService/applicationModule/common/types/',
            'com': 'http://xmlns.oracle.com/apps/pas/transactions/transactionsService/view/common/',
            'wsse': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd'
        }

        try:
            root = etree.fromstring(request.body)
            username = root.xpath(
                '//soapenv:Header/wsse:Security/wsse:UsernameToken/wsse:Username',
                namespaces=namespaces
            )[0].text
            password = root.xpath(
                '//soapenv:Header/wsse:Security/wsse:UsernameToken/wsse:Password',
                namespaces=namespaces
            )[0].text
            self.auth_user(username, password)
            pool_result = root.xpath('%scom:Location' % xpath_prefix,
                                     namespaces=namespaces)
            if len(pool_result) > 0:
                self.location_name = pool_result[0].text
                pool = pool_result[0].text

            # TODO: Handle exception
            count_result = root.xpath('%scom:SerialQuantity' % xpath_prefix,
                                      namespaces=namespaces)
            if len(count_result) > 0:
                count = count_result[0].text
            gtin_result = root.xpath('%scom:Gtin' % xpath_prefix,
                                     namespaces=namespaces)
            if len(gtin_result) > 0:
                gtin = gtin_result[0].text

            if gtin:
                pool = gtin

            ret = super().get(request, pool, count)
        except ObjectDoesNotExist as e:
            ret = Response(
                'An item that was expected to be '
                'configured could not be found. '
                'This is likely to be a Trade Item or '
                'Company linked to the '
                'SerialBox Pool name or Pool API '
                'Key/machine_name for master data '
                'purposes. Check your master data configurations '
                'or explicity set the Company Prefix Length step '
                'parameter.'
                'Detail: %s' %
                str(e), status.HTTP_400_BAD_REQUEST, exception=True
            )
        except etree.XMLSyntaxError as e:
            ret = Response('The submitted data was either not XML '
                           'or it was malformed and unable to process: %s' %
                           str(e))
        except UnboundLocalError as e:
            ret = Response('One of the values (SerialQuantity, Location, or '
                           'Gtin) were missing from the message and/or '
                           'improper namespaces were supplied.')
        return ret

    def _set_task_parameters(self, pool, region, response_rule, size, request):
        db_task = super()._set_task_parameters(pool, region, response_rule,
                                               size,
                                               request)
        tp = TaskParameter.objects.create(
            task=db_task,
            name='location_name',
            value=self.location_name,
            description='The name of the location passed in the request.'
        )
        return db_task


class CaptureInterface(capture_views.CaptureInterface):
    """
    Adds a reference to the OPSM filter with id "opsm"
    that must be configured on a qu4rtet capture configuration.
    """
    authentication_classes = [BasicAuthentication]
    def post(self, request: Request, format=None, epcis=False):
        if not request.GET._mutable:
            request.GET._mutable = True
        request.GET['filter'] = 'opsm'
        ret = super().post(request, format, epcis)
        if ret.status_code == 201:
            ret = Response(status=status.HTTP_200_OK)
        return ret
