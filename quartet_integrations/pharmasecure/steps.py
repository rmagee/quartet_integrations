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
import copy
import datetime
import random
import time
import sqlite3
import requests
from django.utils.translation import gettext as _
from xml.etree import ElementTree
from requests.auth import HTTPBasicAuth, HTTPProxyAuth
from list_based_flavorpack.processing_classes.third_party_processing.rules import \
    get_region_table
from EPCPyYes.core.v1_2 import template_events
from quartet_capture import models, rules, errors as capture_errors
from quartet_capture.rules import RuleContext
from quartet_output.transport.http import HttpTransportMixin
from quartet_integrations.frequentz.environment import get_default_environment
from quartet_masterdata.models import TradeItem
from list_based_flavorpack.models import ListBasedRegion
from serialbox import models as sb_models
from gs123 import conversion
from quartet_templates.steps import TemplateStep
from quartet_output.steps import ContextKeys, EPCPyYesOutputStep


class PharmaSecureOutputStep(EPCPyYesOutputStep):

    def _get_commissioning_template(self):
        """
        Grabs the jinja environment and creates a jinja template object and
        returns
        :return: A new Jinja template.
        """
        env = get_default_environment()
        template = env.get_template('pharmasecure/pharmasecure_object_event.xml')
        return template

    def _get_aggregation_template(self):
        """
        Returns a Aggregation event template for use by the filtered event.
        :return: A jinja template object.
        """
        env = get_default_environment()
        template = env.get_template('pharmasecure/pharamsecure_aggregation.xml')
        return template


    def execute(self, data, rule_context: RuleContext):
        # two events need new templates - object and shipping
        # the overall document needs a new template get that below
        # if filtered events has more than one event then you know
        # the event in filtered events is a shipping event so grab that
        # and give it a new template

        rule_context.context[ContextKeys.FILTERED_EVENTS_KEY.value] = []


        object_events = rule_context.context.get(
            ContextKeys.OBJECT_EVENTS_KEY.value, [])

        if len(object_events) > 0:
            #here you are changing the object event templates
            template = self._get_commissioning_template()
            for event in object_events:
                event._template = template

        aggregation_events = rule_context.context.get(
            ContextKeys.AGGREGATION_EVENTS_KEY.value, [])

        if len(aggregation_events) > 0:
            # here you are changing the object event templates
            template = self._get_aggregation_template()
            for event in aggregation_events:
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
        template = env.get_template('pharmasecure/pharmasecure_epcis_document.xml')
        doc_class._template = template
        return doc_class


class PharmaSecureShipStep(EPCPyYesOutputStep):

    def _get_shipping_template(self):
        """
        Returns a shipping event template for use by the filtered event.
        :return: A jinja template object.
        """
        env = get_default_environment()
        template = env.get_template('pharmasecure/pharmasecure_shipping_objectevent.xml')
        return template

    def execute(self, data, rule_context: RuleContext):

        filtered_events = rule_context.context.get(ContextKeys.FILTERED_EVENTS_KEY.value)
        rule_context.context[ContextKeys.OBJECT_EVENTS_KEY.value] = []
        rule_context.context[ContextKeys.AGGREGATION_EVENTS_KEY.value] = []

        if len(filtered_events) > 0:
            template = self._get_shipping_template()
            for event in filtered_events:
                event._template = template

        super().execute(data, rule_context)

    def get_epcis_document_class(self,
                                 all_events) -> template_events.EPCISEventListDocument:
        """
        This function will override the default 1.2 EPCIS doc PharmaSecure EPCIS Document
        template
        :param all_events: The events to add to the document
        :return: The EPCPyYes event list document to render
        """
        doc_class = super().get_epcis_document_class(all_events)
        env = get_default_environment()
        template = env.get_template('pharmasecure/pharmasecure_epcis_document.xml')
        doc_class._template = template
        return doc_class


class PharmaSecureNumberRequestTransportStep(rules.Step, HttpTransportMixin):
    '''
    Requests Serial Numbers from PharmaSecure
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
            # Get the region
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
                  content_type='text/xml'
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
            headers={'content-type': 'text/xml',
                     'charset':'utf-8',
                     'SOAPAction':'http://tempuri.org/IPSService/Generate'}
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

        # Set up namespaces for returned xml from IRIS
        ns = {
            "a":"http://schemas.datacontract.org/2004/07/psIDCodeMaker",
            "s":"http://schemas.xmlsoap.org/soap/envelope/",
            "i":"http://www.w3.org/2001/XMLSchema-instance"
        }

        # Set parameter values from the Step
        content_type = 'text/xml'
        quantity = None
        object_value = None
        object_name = None
        encoding_type = None
        try:
            object_value = region.processing_parameters.get(key='object_value').value
        except:
            pass
        try:
            object_name = region.processing_parameters.get(key='object_name').value
        except:
            pass
        try:
            quantity = region.processing_parameters.get(key='quantity').value
        except:
            pass
        try:
            encoding_type = region.processing_parameters.get(key='encoding_type').value
        except:
            pass

        # check parameters
        if quantity is None:
            msg = "Parameter Quantity was not set"
            self.error(msg)
            raise Exception(msg)

        if encoding_type is None:
            msg = "Parameter 'encoding_type' was not set. Acceptable Values are SSCC or SGTIN."
            self.error(msg)
            raise Exception(msg)

        if object_name is None:
            msg = "Parameter 'object_name' was not set. Acceptable Values are COMPANY_PREFIX or GTIN."
            self.error(msg)
            raise Exception(msg)

        if object_value is None:
            msg = "Parameter 'object_value' was not set. Acceptable Values are a Company Prefix or a GTIN14."
            self.error(msg)
            raise Exception(msg)


        # Build request to for serial numbers
        context = {
            'request_id': random.randint(100000000001,999999999999),
            'encoding_type': encoding_type,
            'quantity': quantity,
            'object_name': object_name,
            'object_value': object_value

        }

        # build/generate template for create request
        template_doc = 'pharmasecure/pharmasecure_number_request.xml'
        env = get_default_environment()
        template = env.get_template(template_doc)
        data = template.render(**context)
        self.info("Sending request %s", data)
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
        self.info("Response Received %s", response.content[0:50000])

        return response

    def on_failure(self):
        super().on_failure()

    @property
    def declared_parameters(self):
        return {

            'object_value': 'The GTIN-14 or Company Prefix for SSCCs',
            'quantity': 'Number of serial numbers to return',
            'object_name':'The name of the Object value e.g. COMPANY_PREFIX or GTIN',
            'encoding_type': 'SGTIN or SSCC'
        }


class PharmaSecureNumberRequestProcessStep(rules.Step):
    """
    Takes response data from PharmaSecure and writes to the sqlite db
    database file if the region supports that.
    """

    def write_range(self, end, region, sb_start, start):
        raise NotImplementedError('This number response step does not handle '
                                  'range based information.')

    def execute(self, data, rule_context: RuleContext):

        # Set up namespaces for returned xml from PharmaSecure
        ns = {
            "a":"http://schemas.datacontract.org/2004/07/psIDCodeMaker",
            "i":"http://www.w3.org/2001/XMLSchema-instance",
            "s":"http://schemas.xmlsoap.org/soap/envelope/",
            "":"http://tempuri.org/"
        }

        # Get xml response from context
        xml = rule_context.context['NUMBER_RESPONSE']
        region_name = rule_context.context['region_name']
        region = self.get_list_based_region(region_name)
        # Load XML
        root = ElementTree.fromstring(xml)
        # Get Serial Numbers
        tags = root.findall(
            '*/*/*/*/a:SerialNo',
            ns)
        if len(tags) == 0:
            # Error from PharmaSecure
            msg = ""
            try:
                er = root.find('*/*/*/a:ErrorCode', ns).text
                msg = "Error from PharmaSecure {0}".format(er)
            except:
                msg = 'PharmaSecure returned no Serial Numbers for {0}'.format(region_name)
                self.error(msg)

            raise Exception(msg)


        serial_numbers = []
        # add tags to serial_numbers array
        for tag in tags:
            sn = conversion.BarcodeConverter(tag.find('a:SerialNumber', ns).text, company_prefix_length=len("0370010"))
            num = sn.serial_number
            serial_numbers.append(num)

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
        s = ","
        self.info('Saved Serial Numbers. {0}'.format(s.join(serial_numbers)))
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
        return {}


