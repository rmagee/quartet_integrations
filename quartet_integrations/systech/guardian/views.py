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
from logging import getLogger

from django.conf import settings
from io import BytesIO
from lxml import etree

from quartet_capture.models import TaskParameter
from rest_framework_xml import parsers
from serialbox.api.views import AllocateView

logger = getLogger(__name__)

from rest_framework.negotiation import DefaultContentNegotiation


class DefaultTextXMLContent(DefaultContentNegotiation):

    def select_renderer(self, request, renderers, format_suffix):
        """
        Use the XML renderer as default.
        """
        # Allow URL style format override.  eg. "?format=json
        format_query_param = self.settings.URL_FORMAT_OVERRIDE
        format = format_suffix or request.query_params.get(format_query_param)
        request.query_params.get(format_query_param)
        for renderer in renderers:
            if renderer.media_type == "application/xml":
                renderer.media_type = "text/xml"
                return (renderer, "text/xml")
        return DefaultContentNegotiation.select_renderer(self, request,
                                                         renderers, format)


parser_classes = [parsers.XMLParser]
content_negotiation_class = DefaultTextXMLContent


class GuardianNumberRangeView(AllocateView):
    """
    Will process inbound Guardian Number Range requests and return accordingly.
    This is a SOAP interface and supports only the POST operation.
    """

    content_negotiation_class = DefaultTextXMLContent

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = None
        self.machine_name = None
        self.sending_system = None
        self.id_type = None
        self.encoding_type = None

    def post(self, request):
        request_data = \
            etree.iterparse(BytesIO(request.body),
                            events=('end',),
                            remove_comments=True)
        count = None
        count = self.parse_xml(request_data)
        ret = super().get(request, self.machine_name, count)
        return ret

    def parse_xml(self, request_data) -> int:
        """
        Override to handle different parsing scenarios.  Populates the
        instance fields and returns teh
        :param count:
        :param request_data:
        :return:
        """
        count = 0
        for event, element in request_data:
            print(element.tag)
            if 'ObjectKey' in element.tag:
                logger.debug('object key found')
                self.type, self.machine_name = self.check_object_key(element)
            elif 'Size' in element.tag:
                count = element.text
                logger.debug('size = %s', count)
            elif 'EncodingType' in element.tag:
                self.encoding_type = element.text
            elif 'IDType' in element.tag:
                self.id_type = element.text
            elif 'SendingSystem' in element.tag:
                self.sending_system = element.text
            print(element.tag)
        return count

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
            ):
                logger.debug('Found GTIN, GCP or SSCC object key...getting '
                             'the machine name.')
                name = child.text
            elif name and 'Value' in child.tag:
                logger.debug('Getting the value...')
                value = child.text
        return name, value

    def _set_task_parameters(self, pool, region, response_rule, size, request):
        """
        Override the _set_task_parameters so that we can pass in the
        additional systech parameters for the rule.
        """
        db_task = super()._set_task_parameters(pool, region, response_rule,
                                               size,
                                               request)
        TaskParameter.objects.create(
            task=db_task,
            name='id_type',
            value=self.id_type
        )
        TaskParameter.objects.create(
            task=db_task,
            name='sending_system',
            value=self.sending_system
        )
        TaskParameter.objects.create(
            task=db_task,
            name='encoding_type',
            value=self.encoding_type
        )
        TaskParameter.objects.create(
            task=db_task,
            name='type',
            value=self.type
        )
        TaskParameter.objects.create(
            task=db_task,
            name='machine_name',
            value=self.machine_name
        )
        return db_task
