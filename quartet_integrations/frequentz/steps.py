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
import io, os
import datetime
import time
import sqlite3
import requests
from django.core.files.base import File
from django.utils.translation import gettext as _
from xml.etree import ElementTree
from requests.auth import HTTPBasicAuth, HTTPProxyAuth
from list_based_flavorpack.processing_classes.third_party_processing.rules import \
    get_region_table
from EPCPyYes.core.v1_2 import template_events
from quartet_capture import models, rules, errors as capture_errors
from quartet_capture.rules import RuleContext
from quartet_output.transport.http import HttpTransportMixin, user_agent
from quartet_integrations.frequentz.environment import get_default_environment
from quartet_integrations.frequentz.parsers import FrequentzOutputParser
from quartet_masterdata.models import TradeItem
from list_based_flavorpack.models import ListBasedRegion
from serialbox import models as sb_models
from gs123 import conversion
from quartet_templates.steps import TemplateStep
from quartet_output.steps import ContextKeys, EPCPyYesOutputStep


class FrequentzOutputStep(EPCPyYesOutputStep):

    def _get_new_template(self):
        """
        Grabs the jinja environment and creates a jinja template object and
        returns
        :return: A new Jinja template.
        """
        env = get_default_environment()
        template = env.get_template('frequentz/frequentz_object_event.xml')
        return template

    def _get_shipping_template(self):
        """
        Returns a shipping event template for use by the filtered event.
        :return: A jinja template object.
        """
        env = get_default_environment()
        template = env.get_template('frequentz/frequentz_shipping_objectevent.xml')
        return template

    def execute(self, data, rule_context: RuleContext):
        # two events need new templates - object and shipping
        # the overall document needs a new template get that below
        # if filtered events has more than one event then you know
        # the event in filtered events is a shipping event so grab that
        # and give it a new template
        filtered_events = rule_context.context.get(ContextKeys.FILTERED_EVENTS_KEY.value)
        if len(filtered_events) > 0:
            template = self._get_shipping_template()
            filtered_events[0]._template = template
            # get the object events from the context - these are added by
            # the AddCommissioningDataStep step in the rule.
            object_events = rule_context.context.get(
                ContextKeys.OBJECT_EVENTS_KEY.value, [])
            if len(object_events) > 0:
                #here you are changing the object event templates
                template = self._get_new_template()
                for event in object_events:
                    event._template = template
        super().execute(data, rule_context)

    def get_epcis_document_class(self,
                                 all_events) -> template_events.EPCISEventListDocument:
        """
        This function will override the default 1.2 EPCIS doc with a 1.0
        template
        :param all_events: The events to add to the document
        :return: The EPCPyYes event list document to render
        """
        doc_class = super().get_epcis_document_class(all_events)
        env = get_default_environment()
        template = env.get_template('frequentz/frequentz_epcis_document.xml')
        doc_class._template = template
        return doc_class

    @property
    def declared_parameters(self):
        return super().declared_parameters

class IRISNumberRequestTransportStep(rules.Step, HttpTransportMixin):
    '''
    Uses the transport information within the `region`.
    '''

    def execute(self, data, rule_context: RuleContext):
        # get the task parameters that we rely on
        try:
            self.info(
                _('Looking for the task parameter with the target Region. '
                  'Output Name.'))
            param = models.TaskParameter.objects.get(
                task__name=rule_context.task_name,
                name='List-based Region'
            )
            # now see if we can get the output critieria based on the param
            # value
            self.info(_('Found the region param, now looking up the '
                        'Region instance with name %s.'),
                      param.value
                      )

        except models.TaskParameter.DoesNotExist:
            raise capture_errors.ExpectedTaskParameterError(
                _('The task parameter with name List-based Region '
                  'could not be found.  This task parameter is required by '
                  'the NumberRequestTransportStep to function correctly.')
            )
        try:
            region = ListBasedRegion.objects.get(machine_name=param.value)

            # Send the Create Request

            response = self._send_message(data, rule_context, region)
            # Pass response for downstream processing.
            rule_context.context['NUMBER_RESPONSE'] = response.content
            rule_context.context['region_name'] = region.machine_name
            rule_context.context['format'] = self.get_parameter('format', None)
        except Exception as e:
            self.error(_(
                "An error occurred while sending request to third party: %s"),
                str(e))
            raise

    def get_auth(self, region):
        """
        Get's the authentication method and credentials from the
        region record.
        :param region: A ListBasedModel model instance.
        :return: A `requests.auth.HTTPBasicAuth` or `HTTPProxyAuth`
        """
        auth_info = region.authentication_info
        auth = None
        if auth_info:
            auth_type = auth_info.type or ''
            if 'digest' in auth_type.lower():
                auth = HTTPBasicAuth
            elif 'proxy' in auth_type.lower():
                auth = HTTPProxyAuth
            else:
                auth = HTTPBasicAuth
            auth = auth(auth_info.username, auth_info.password)
        return auth

    def post_data(self, data: str, rule_context: RuleContext,
                  region: ListBasedRegion,
                  content_type='application/xml'
                  ):
        '''
        :param data_context_key: The key within the rule_context that contains
         the data to post.  If being invoked from the internals of this
         module this is usually the OUTBOUND_EPCIS_MESSSAGE_KEY value of the
         `quartet_output.steps.ContextKeys` Enum.
        :param output_criteria: The output criteria containing the connection
        info.
        :return: The response.
        '''

        response = requests.post(
            region.end_point.urn,
            data,
            auth=self.get_auth(region),
            headers={'content-type': content_type, 'user-agent': user_agent}
        )
        return response

    def _send_message(
        self,
        data: str,
        rule_context: RuleContext,
        region: ListBasedRegion
    ):
        '''
        Sends a message using the protocol specified.
        :param rule_context: The RuleContext contains the data in the
        OUTBOUND_EPCIS_MESSAGE_KEY value from the `ContextKey` class.
        :param region: The originating region.
        :return: None.
        '''

        ret_val = None
        # Set up namespaces for returned xml from IRIS
        ns = {
            "soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
            "ns2": "http://www.ibm.com/epcis/serialid/TagManagerTypes"
        }

        # Set parameter values from the Step
        content_type = 'text/xml'
        quantity = region.number_replenishment_size
        try:
            resource_name = region.processing_parameters.get(key='gtin').value
        except:
            resource_name = None
        try:
            format = region.processing_parameters.get(key='format').value
        except:
            format = None

        # check parameters
        if quantity is None:
            msg = "replenishment_size was not set"
            self.error(msg)
            raise Exception(msg)

        if resource_name is None:
            msg = "Region Processing Parameter 'gtin' was not set. (This can be an sscc value too.)"
            self.error(msg)
            raise Exception(msg)

        if format is None:
            msg = "Region Processing Parameter 'format' was not set"
            self.error(msg)
            raise Exception(msg)

        # Build request to create a request for serial numbers
        context = {
            'quantity': quantity,
            'resource': resource_name,
            'format': format,
            'username': region.authentication_info.username,
            'password': region.authentication_info.password,
            'created': str(datetime.datetime.utcnow().isoformat())
        }

        # build/generate template for create request
        template_doc = 'frequentz/create_request.xml'
        env = get_default_environment()
        template = env.get_template(template_doc)
        data = template.render(**context)
        self.info("create request sent %s", data)
        # Post the request
        response = self.post_data(
            data,
            rule_context,
            region,
            content_type
        )
        try:
            response.raise_for_status()
        except:
            if response.content:
                self.info("Error occurred with following response %s",
                          response.content)
            raise
        self.info("Response Received %s", response.content[0:5000])
        # Get the request id
        root = ElementTree.fromstring(response.text)
        request_id = root.find(
            'soapenv:Body/ns2:createTagResponse/ns2:requestId', ns).text

        # build request to get serial numbers
        context = {
            'request_id': request_id,
            'username': region.authentication_info.username,
            'password': region.authentication_info.password,
            'created': str(datetime.datetime.utcnow().isoformat())
        }
        # generate template to get the serial numbers
        template_doc = 'frequentz/get_serial_number.xml'
        template = env.get_template(template_doc)
        data = template.render(**context)

        # post data to retrieve serial numbers
        result_response = self.post_data(
            data,
            rule_context,
            region,
            content_type
        )
        try:
            result_response.raise_for_status()
        except:
            if result_response.content:
                self.info("Error occurred with following response %s",
                          result_response.content)
            raise
        self.info("Response Received %s", response.content[0:5000])
        self.info("get serial number request sent %s", data)

        # build request to confrim serial numbers retrieved
        context = {
            'request_id': request_id,
            'username': region.authentication_info.username,
            'password': region.authentication_info.password,
            'created': str(datetime.datetime.utcnow().isoformat())
        }
        # Generate template for confirm request
        template_doc = 'frequentz/confirm_request.xml'
        template = env.get_template(template_doc)
        data = template.render(**context)
        # Post Confirm request
        response = self.post_data(
            data,
            rule_context,
            region,
            content_type
        )
        self.info("confirmation for serial numbers sent %s", data)
        try:
            response.raise_for_status()
        except:
            if response.content:
                self.info("Error occurred with following response %s",
                          response.content)
            raise
        self.info("Response Received %s", response.content[0:5000])

        return result_response

    def on_failure(self):
        super().on_failure()

    @property
    def declared_parameters(self):
        return {

            'resource_name': 'The GTIN-14 or Company Prefix for SSCCs',
            'quantity': 'Number of serial numbers to return',
            'format': 'The format to return from IRIS. SGTIN-198 or SSCC'
        }


class IRISNumberRequestProcessStep(rules.Step):
    """
    Takes response data from IRIS systems and writes to the sqlite db
    database file if the region supports that.
    """

    def write_range(self, end, region, sb_start, start):
        raise NotImplementedError('This number response step does not handle '
                                  'range based information.')

    def execute(self, data, rule_context: RuleContext):

        # Set up namespaces for returned xml from IRIS
        ns = {
            "soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
            "ns2": "http://www.ibm.com/epcis/serialid/TagManagerTypes"
        }

        # Get xml response from context
        xml = rule_context.context['NUMBER_RESPONSE']
        region_name = rule_context.context['region_name']
        region = self.get_list_based_region(region_name)
        format = region.processing_parameters.get(key='format').value
        # Load XML
        root = ElementTree.fromstring(xml)
        # Get quantity
        quantity_returned = root.find(
            'soapenv:Body/ns2:getTagsResponse/ns2:tagResponse/ns2:quantity',
            ns).text
        # Get Serial Numbers
        tags = root.findall(
            'soapenv:Body/ns2:getTagsResponse/ns2:tagResponse/ns2:tagList/ns2:tag',
            ns)
        serial_numbers = []
        # add tags to serial_numbers array
        for tag in tags:
            if format.lower() == 'sgtin-198' or format.lower() == 'sgtin-96':
                sn = tag.text.split('.')[3]
                serial_numbers.append(sn)
            elif format.lower() == 'sscc-96':
                urn = tag.text.replace('urn:epc:tag:sscc-96:',
                                       'urn:epc:id:sscc:')
                # sn = conversion.URNConverter(urn)
                parts = urn.split('.')
                ext = parts[2][0]
                cp = parts[1]
                sn = parts[2][1:]
                sscc18 = '{0}{1}{2}'.format(ext, cp, sn)
                sscc18 = conversion.calculate_check_digit(sscc18)
                serial_numbers.append(sscc18)

        self.write_list(serial_numbers, region)

    def write_list(self, serial_numbers, region: ListBasedRegion):

        start = time.time()
        if not os.path.exists(region.db_file_path):
            connection = sqlite3.connect(region.db_file_path)
            connection.execute(
                "create table if not exists %s "
                "(serial_number text not null unique, used integer not null)"
                % get_region_table(region)
            )
        else:
            connection = sqlite3.connect(region.db_file_path)

        cursor = connection.cursor()
        cursor.execute('begin transaction')
        self.info('storing the numbers. {0}'.format(region.db_file_path))
        for id in serial_numbers:
            cursor.execute('insert into %s (serial_number, used) values '
                           '(?, ?)' % get_region_table(region), (id, 0))
        connection.commit()
        self.info("Execution time: %.3f seconds." % (time.time() - start))

    def get_list_based_region(self, machine_name):
        """
        Gets the list based region based on the machine name of the region
        first and, if not available, will look for a pool with the machine
        name and pull the list based region from the pool.
        :param machine_name: The machine name of the region or pool
        :return: A ListBasedRegion instance
        """
        try:
            ret = ListBasedRegion.objects.get(machine_name=machine_name)
        except ListBasedRegion.DoesNotExist:
            pool = sb_models.Pool.objects.get(machine_name=machine_name)
            ret = ListBasedRegion.objects.filter(pool=pool)[0]
            if not isinstance(ret, ListBasedRegion):
                raise ListBasedRegion.DoesNotExist(
                    'A list based region '
                    'is not available within'
                    'pool %s' % pool.machine_name
                )
        return ret

    def on_failure(self):
        super().on_failure()

    @property
    def declared_parameters(self):
        return super().declared_parameters


class IRISTemplateStep(TemplateStep):

    def execute(self, data, rule_context: RuleContext):
        # convert
        if len(data[0]) > 18:
            num = data[0][2:]
            urn = 'urn:epc:id:sgtin:{0}'.format(num)
            sn = conversion.URNConverter(urn)
            # Populate
            rule_context.context['trade_item'] = TradeItem.objects.get(
                GTIN14=sn.gtin14
            )
        # call super
        return super().execute(data, rule_context)

    def on_failure(self):
        super().on_failure()

    @property
    def declared_parameters(self):
        return super().declared_parameters
