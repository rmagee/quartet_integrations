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
from list_based_flavorpack.models import ListBasedRegion
from serialbox import models as sb_models

from quartet_output.steps import ContextKeys

"""
 Creates output EPCIS for Frequentz which is EPCIS 1.0
"""

class FrequentzOutputStep(rules.Step):

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)


    def execute(self, data, rule_context: RuleContext):

        # Parse EPCIS
        if isinstance(data, File):
            parser = FrequentzOutputParser(data)
        elif isinstance(data, str):
            parser = FrequentzOutputParser(io.BytesIO(str.encode(data)))
        else:
            parser = FrequentzOutputParser(io.BytesIO(data))

        # parse
        parser.parse()

        rule_context.context[
            ContextKeys.OBJECT_EVENTS_KEY.value] = parser.object_events
        rule_context.context[
            ContextKeys.AGGREGATION_EVENTS_KEY.value] = parser.aggregation_events

        # put the parser in the context so the data isn't parsed again in the next step
        rule_context.context['PARSER'] = parser

        env = get_default_environment()

        created_date = str(datetime.datetime.utcnow().isoformat())
        additional_context = {'created_date': created_date}

        all_events = parser.object_events + parser.aggregation_events
        epcis_document = template_events.EPCISEventListDocument(
            all_events,
            None,
            template=env.get_template(
                'frequentz/frequentz_epcis_document.xml'
            ),
            additional_context=additional_context
        )
        if self.get_boolean_parameter('JSON', False):
            data = epcis_document.render_json()
        else:
            data = epcis_document.render()
        rule_context.context[
            ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value
        ] = data
        # For testing so the comm/agg doc can be viewed/evaluated in unit test
        rule_context.context['COMM_AGG_DOCUMENT'] = data

    def declared_parameters(self):
        return {}

    def on_failure(self):
        pass

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
        content_type = 'txt/xml'
        quantity = self.get_parameter('quantity', None)
        resource_name = self.get_parameter('resource_name', None)
        format = self.get_parameter('format', None)

        # check parameters
        if quantity is None:
            msg = "Step Parameter 'quantity' was not set"
            self.error(msg)
            raise Exception(msg)

        if resource_name is None:
            msg = "Step Parameter 'resource_name' was not set"
            self.error(msg)
            raise Exception(msg)

        if format is None:
            msg = "Step Parameter 'format' was not set"
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
        request_id = root.find('soapenv:Body/ns2:createTagResponse/ns2:requestId', ns).text

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
    Takes response data from tracelink systems and writes to the sqlite db
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
        format = rule_context.context['format']
        region = self.get_list_based_region(region_name)

        # Load XML
        root = ElementTree.fromstring(xml)
        # Get quantity
        quantity_returned = root.find('soapenv:Body/ns2:getTagsResponse/ns2:tagResponse/ns2:quantity', ns).text
        # Get Serial Numbers
        tags = root.findall('soapenv:Body/ns2:getTagsResponse/ns2:tagResponse/ns2:tagList/ns2:tag', ns)
        serial_numbers = []
        # add tags to serial_numbers array
        for tag in tags:
            sn = tag.text.replace('urn:epc:tag:{0}:'.format(format).lower(), "")
            serial_numbers.append(sn)

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
        self.info('storing the numbers.')
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
        return {}
