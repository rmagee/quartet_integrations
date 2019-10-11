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
import requests
from rest_framework.request import HttpRequest
from rest_framework.renderers import JSONRenderer
from lxml import etree
from rest_framework.views import APIView
from rest_framework_xml import parsers
from serialbox.api.views import AllocateView

from quartet_integrations.opsm import opsm_settings

from logging import getLogger
from serialbox.models import Pool

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

    def post(self, request):
        pool_name = None
        count = None
        gtin = None
        xpath_prefix = '//soapenv:Body/typ:createProcessSerialGenerationRequest/typ:serialGenerationRequest/'
        namespaces = {
            'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
            'typ': 'http://xmlns.oracle.com/apps/pas/transactions/transactionsService/applicationModule/common/types/',
            'com': 'http://xmlns.oracle.com/apps/pas/transactions/transactionsService/view/common/'
        }

        root = etree.fromstring(request.body)
        pool_result = root.xpath('%scom:Location' % xpath_prefix,
                                 namespaces=namespaces)
        if len(pool_result) > 0:
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

        if gtin_result:
            pool = gtin

        return super().get(request, pool, count)

        # # get the url - default is http://127.0.0.1/serialbox/allocate/pool/count/
        # url = self.build_url(count, pool)
        #
        # # execute the call
        # response = requests.get(
        #     url,
        #     auth=request.auth
        # )



    def buil_request(self, current_request: HttpRequest):
        new_request = HttpRequest()
        new_request.accepted_renderer = JSONRenderer()
        new_request.GET = current_request.GET


    def build_url(self, count, pool):
        """
        Builds the default URL based on settings.  To change any of the
        defualt connectivity settings, use the following:

        OPSM_SERIALBOX_SCHEME - set http or https. Default is http.
        OPSM_SERIALBOX_HOST - set the host to connect to (defaults to the
        local loopback IP address)
        OPSM_SERIALBOX_PORT - set the port for the server/host to connect to
        default is none.
        :param count: The number of serial numbers to request.
        :param pool: The pool to request numbers from.
        :return: A properly formatted serialbox Allocate API URL.
        """
        scheme = opsm_settings.OPSM_SERIALBOX_SCHEME
        host = opsm_settings.OPSM_SERIALBOX_HOST
        port = opsm_settings.OPSM_SERIALBOX_PORT
        if not port:
            url = "%s://%s/serialbox/allocate/%s/%d/?format=json" % (
                scheme, host, pool.machine_name, int(count))
        else:
            url = "%s://%s:%s/serialbox/allocate/%s/%d/?format=json" % (
                scheme, host, port, pool.machine_name, int(count))
        return url
