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
# Copyright 2021 SerialLab Corp.  All rights reserved.

from logging import getLogger

import os
from django.template import loader

from lxml import etree

from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request

from quartet_capture.models import TaskParameter
from quartet_integrations.systech.guardian.views import GuardianNumberRangeView, GuardianNumberRangeRenderer
from rest_framework.renderers import BrowsableAPIRenderer

logger = getLogger(__name__)


class TraceLinkNumberRangeView(GuardianNumberRangeView):
    """
    This number range view handles data very similar to the "SAP" format
    handled by Systech Guardian.
    """
    renderer_classes = [GuardianNumberRangeRenderer, BrowsableAPIRenderer]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.receiving_system = None
        self.company_prefix = None
        self.extension_digit = None

    def get(self, request: Request, pool=None, size=None, region=None):
        """
        Just serves up the tracelink WSDL file for optel connectors and
        applications that require the WSDL to function.
        """
        host = request._request.get_host()
        scheme = request._request.scheme
        if 'wsdl' in request.query_params.keys():
            template = loader.get_template(
                "tracelink/snrequest.xml")
            xml = template.render({"host": host,
                                   "scheme": scheme
                                   })
            return Response(xml, status.HTTP_200_OK,
                            content_type='application/xml')
        elif request.query_params.get('xsd') == '1':
            template = loader.get_template(
                "tracelink/xsd1.xml")
            xml = template.render({"host": host,
                                   "scheme": scheme
                                   })
            return Response(xml, status.HTTP_200_OK,
                            content_type='application/xml')
        elif request.query_params.get('xsd') == '2':
            template = loader.get_template(
                "tracelink/xsd2.xml")
            xml = template.render({"host": host,
                                   "scheme": scheme
                                   })
            return Response(xml, status.HTTP_200_OK,
                            content_type='application/xml')
        else:
            return Response(status=status.HTTP_200_OK)

    def parse_xml(self, request_data) -> int:
        """
        Override to handle different parsing scenarios.  Populates the
        instance fields and returns the count.
        :param count:
        :param request_data:
        :return:
        """
        count = 0
        for event, element in request_data:
            if 'ObjectKey' in element.tag:
                logger.debug('object key found')
                self.type, self.machine_name = self.check_object_key(
                    element)
                if "|" in self.machine_name:
                    # here we are taking the pipe out of the "company prefix"
                    # value and then putting the last digit in the front
                    # this is how serialbox steps expect it: indicator digit
                    # then the company prefix as the machine name of the pool.
                    logger.debug('Found an SSCC')
                    vals = self.machine_name.split("|")
                    self.machine_name = vals[1] + vals[0]
                    self.extension_digit = vals[1]
                    self.company_prefix = vals[0]
                    logger.debug('Set machine name to %s', self.machine_name)
            elif 'Size' in element.tag:
                count = element.text
                logger.debug('size = %s', count)
            elif 'EncodingType' in element.tag:
                self.encoding_type = element.text
            elif 'idtype' in element.tag.lower():
                self.id_type = element.text
            elif 'SendingSystem' in element.tag:
                self.sending_system = element.text
            elif 'ReceivingSystem' in element.tag:
                self.receiving_system = element.text
        return count

    def _set_task_parameters(self, pool, region, response_rule, size, request):
        """
        Add the ReceivingSystem task parameter to the existing ones created
        by the base class and return the Task.
        """
        db_task = super()._set_task_parameters(pool, region, response_rule,
                                               size,
                                               request)

        TaskParameter.objects.create(
            task=db_task,
            name='receiving_system',
            value=self.receiving_system
        )
        if self.extension_digit:
            TaskParameter.objects.create(
                task=db_task,
                name='extension_digit',
                value=self.extension_digit
            )
            TaskParameter.objects.create(
                task=db_task,
                name='company_prefix',
                value=self.company_prefix
            )
        return db_task

    def check_object_key(self, object_key: etree.Element) -> tuple:
        """
        Iterates through the children of an ObjectKey element to ascertain
        whether or not there is a GTIN or SSCC identifier present.
        :param element: The element to check
        :return: Will return the GTIN or SSCC if found, otherwise none.
        """
        name = None
        value = None
        for child in object_key:
            if child.text and (
                'GTIN' in child.text
                or 'SSCC' in child.text
                or 'GCP' in child.text
                or 'COMPANY_PREFIX' in child.text
            ):
                logger.debug('Found GTIN, GCP, COMPANY_PREFIX or SSCC '
                             'object key...getting '
                             'the machine name.')
                name = child.text
            elif name and 'Value' in child.tag:
                logger.debug('Getting the value...')
                value = child.text
        return name, value
