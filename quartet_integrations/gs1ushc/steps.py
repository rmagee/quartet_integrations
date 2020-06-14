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
from io import BytesIO
from datetime import datetime
from enum import Enum
from typing import List
from EPCPyYes.core.SBDH import sbdh
from EPCPyYes.core.SBDH import template_sbdh
from EPCPyYes.core.v1_2 import template_events
from EPCPyYes.core.v1_2.events import EPCISBusinessEvent
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.CBV import business_steps, source_destination
from quartet_capture import rules, models
from quartet_capture.rules import RuleContext
from quartet_integrations.frequentz.environment import get_default_environment
from quartet_integrations.generic import mixins
from quartet_integrations.gs1ushc.parsing import SimpleOutputParser, \
    BusinessOutputParser
from quartet_masterdata.models import Company, Location
from quartet_output.steps import ContextKeys as OutputKeys, \
    EPCPyYesOutputStep as EPYOS
from quartet_output.steps import OutputParsingStep as QOPS
from EPCPyYes.core.v1_2.events import Source, Destination

EventList = List[EPCISBusinessEvent]

class ContextKeys(Enum):
    """
    RECEIVER_COMPANY
    ----------------
    A masterdata Company (or location)
    record for the receiving company. This is derived
    via company prefix information in filtered events.

    SENDER_COMPANY
    --------------
    This is a masterdate Company (or location) record for the sender.  This
    is pulled from the Sender data in the EPCIS message.
    """
    RECEIVER_COMPANY = 'RECEIVER_COMPANY'
    SENDER_COMPANY = 'SENDER_COMPANY'


class OutputParsingStep(mixins.ObserveChildrenMixin, QOPS):

    def get_parser_type(self, *args):
        """
        Override to provide a different parser type.
        :return: The `type` of parser to use.
        """
        parser_type = SimpleOutputParser if self.loose_enforcement \
            else BusinessOutputParser
        return parser_type

    @property
    def declared_parameters(self):
        params = super().declared_parameters
        params['Create Child Observation'] = ('Whether or not to take any '
                                              'inbound parents and creat an '
                                              'Object event of action '
                                              'OBSERVE with their children.')
        params['Use Sources'] = (
            'Whether or not to pass the source event source list to the '
            'created object/observe event.  Only applicable if the '
            'Create Child Observation step parameter is set to True.'
        )
        params['Use Destinations'] = (
            'Whether or not to pass the source event destination list to the '
            'created object/observe event.  Only applicable if the '
            'Create Child Observation step parameter is set to True.'
        )
        return params

    def execute(self, data, rule_context: rules.RuleContext):
        super().execute(data, rule_context)
        if self.get_boolean_parameter('Create Child Observation', False):
            self.info('Create Child Observation step parameter was set to '
                      'True...checking filtered events to create '
                      'object/observe events.')
            use_sources = self.get_boolean_parameter('Use Sources', True)
            use_destinations = self.get_boolean_parameter('Use Destinations',
                                                          True)
            filtered_events = rule_context.context[
                OutputKeys.FILTERED_EVENTS_KEY.value]
            doc = template_events.EPCISDocument()
            for event in filtered_events:
                objEvent = self.create_observation_event(event, use_sources,
                                                         use_destinations)
                objEvent.biz_step = business_steps.BusinessSteps.other.value
                doc.object_events.append(objEvent)
            if len(doc.object_events) > 0:
                parser = self.get_parser_type()
                parser(BytesIO(doc.render().encode()),
                       self.epc_output_criteria).parse()


class EPCPyYesOutputStep(EPYOS, mixins.CompanyFromURNMixin,
                         mixins.CompanyLocationMixin):
    """
    Provides a new template for object events that includes gs1ushc
    ILMD data instead of CBV ILMD.
    """

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.template = self._get_new_template()
        self.add_sbdh = self.get_or_create_parameter(
            'Add SBDH',
            'True',
            self.declared_parameters.get('Add SBDH')
        ) in ['True', 'true']
        self.header = template_sbdh.StandardBusinessDocumentHeader()
        self.header.partners = []

    def _get_new_template(self):
        """
        Grabs the jinja environment and creates a jinja template object and
        returns
        :return: A new Jinja template.
        """
        env = get_default_environment()
        template = env.get_template('gs1ushc/object_event.xml')
        return template

    def execute(self, data, rule_context: RuleContext):
        # two events need new templates - object and shipping
        # the overall document needs a new template get that below
        # if filtered events has more than one event then you know
        # the event in filtered events is a shipping event so grab that
        # and give it a new template
        append_data = self.get_or_create_parameter(
            'Append Data', 'True',
            'Whether or not to call the append data function of the step for '
            'events prior to rendering.') in ['True', 'true']
        modify_date = self.get_or_create_parameter(
            'Modify Date', 'True',
            'Whether or not to call the modify date function on teh step'
            ' for events prior to rendering.'
        ) in ['True', 'true']
        ilmd = None
        schema_version = self.get_or_create_parameter('Schema Version', '1',
                                                      self.declared_parameters.get(
                                                          'Schema Version'))
        self.info('Setting the schema version to %s', schema_version)
        rule_context.context['schema_version'] = schema_version
        filtered_events = rule_context.context.get(
            OutputKeys.FILTERED_EVENTS_KEY.value)
        if len(filtered_events) > 0:
            # get the object events from the context - these are added by
            # the AddCommissioningDataStep step in the rule.
            if modify_date: self.modify_date(filtered_events)
            object_events = rule_context.context.get(
                OutputKeys.OBJECT_EVENTS_KEY.value, [])
            if len(object_events) > 0:
                if modify_date: self.modify_date(object_events)
                for object_event in object_events:
                    if len(object_event.ilmd) > 0:
                        ilmd = object_event.ilmd
                        break
                self.info(
                    'Found some filtered object events.'
                    ' Looking up the receiver company by urn value/'
                    'company prefix.')
                if self.add_sbdh:
                    self.add_header(filtered_events[0], rule_context)
                # self.sbdh.partners.append(receiver)
                for event in object_events:
                    event._template = self.template
                    if len(event.ilmd) == 0:
                        event.ilmd = ilmd
            agg_events = rule_context.context.get(
                OutputKeys.AGGREGATION_EVENTS_KEY.value, []
            )
            if append_data: self.append_event_data(agg_events)
            if modify_date: self.modify_date(agg_events)

        super().execute(data, rule_context)

    def modify_date(self, epcis_events: EventList):
        """
        Some systems don't like timezone info so remove it.  Override to
        provide different behavior.
        """
        for epcis_event in epcis_events:
            epcis_event.event_time = epcis_event.event_time.replace('+00:00', 'Z')
            epcis_event.record_time = epcis_event.record_time.replace('+00:00', 'Z')

    def append_event_data(self, epcis_events: EventList):
        """
        If set, will append data to the event, in this case will
        append disposition information if it is missing.  Override to provide
        different behavior.
        """
        disposition = self.get_or_create_parameter(
            'Added Disposition',Disposition.in_progress.value,
            'The disposition to add to events that do not have one.'
        )
        for epcis_event in epcis_events:
            if not epcis_event.disposition:
                epcis_event.disposition = disposition

    def add_header(self, filtered_event: EPCISBusinessEvent, rule_context):
        """
        Adds the SBDH data.
        :param object_events:
        :param rule_context:
        :return:
        """
        # first get the receiver by the company prefix
        # noinspection PyTypeChecker
        try:
            sender_location = self.get_company_by_identifier(
                filtered_event,
                source_destination.SourceDestinationTypes.possessing_party.value
            )
        except Company.DoesNotExist:
            sender_location = self.get_location_by_identifier(
                filtered_event,
                source_destination.SourceDestinationTypes.possessing_party.value
            )
        self.add_sender_partner(sender_location, rule_context)
        receiver_company = self.get_company_by_urn(filtered_event,
                                                   rule_context)
        self.add_receiver_partner(receiver_company, rule_context)
        # next get the receiving location by the receiving party in the event
        try:
            receiver_location = self.get_company_by_identifier(
                epcis_event=filtered_event, source_list=False
            )
        except Company.DoesNotExist:
            receiver_location = self.get_location_by_identifier(
                filtered_event, source_list=False
            )
        owner_source = Source(
            source_destination.SourceDestinationTypes.owning_party.value,
            receiver_company.SGLN)
        owner_destination = Destination(
            source_destination.SourceDestinationTypes.owning_party.value,
            receiver_company.SGLN)
        source_location = Source(
            source_destination.SourceDestinationTypes.location.value,
            sender_location.SGLN)
        destination_location = Destination(
            source_destination.SourceDestinationTypes.location.value,
            receiver_location.SGLN)
        filtered_event.source_list = [owner_source, source_location]
        filtered_event.destination_list = [owner_destination,
                                           destination_location]
        rule_context.context['masterdata'] = {
            receiver_company.SGLN: receiver_company,
            receiver_location.SGLN: receiver_location,
            sender_location.SGLN: sender_location
        }

    def add_receiver_location(self, receiver):
        pass

    def add_receiver_partner(self, receiver_company, rule_context):
        """
        Adds the receiver partner to the header and the receiver company
        to the context.
        :param receiver_company: The masterdata Company model instance.
        :param rule_context: The RuleContext passed to execute.
        :return: None
        """
        receiver = sbdh.Partner(
            sbdh.PartnerType.RECEIVER,
            partner_id=sbdh.PartnerIdentification('GLN',
                                                  receiver_company.GLN13)
        )
        self.header.partners.append(receiver)
        self.header.document_identification.creation_date_and_time = \
            datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        rule_context.context[
            ContextKeys.RECEIVER_COMPANY.value] = receiver

    def add_sender_partner(self, sender_company, rule_context):
        """
        Adds the receiver partner to the header and the sender company
        to the context.
        :param sender_company: The masterdata Company model instance.
        :param rule_context: The RuleContext passed to execute.
        :return: None
        """
        sender = sbdh.Partner(
            sbdh.PartnerType.SENDER,
            partner_id=sbdh.PartnerIdentification('GLN',
                                                  sender_company.GLN13)
        )
        self.header.partners.append(sender)
        rule_context.context[
            ContextKeys.SENDER_COMPANY.value] = sender

    def get_epcis_document_class(self,
                                 all_events
                                 ) -> template_events.EPCISEventListDocument:
        """
        This function will override the default 1.2 EPCIS doc with a 1.0
        template
        :param all_events: The events to add to the document
        :return: The EPCPyYes event list document to render
        """
        doc_class = template_events.EPCISEventListDocument(all_events,
                                                           self.header)
        env = get_default_environment()
        template = env.get_template('gs1ushc/epcis_document.xml')
        doc_class.additional_context = {
            'masterdata': self.rule_context.context['masterdata']}
        doc_class._template = template
        return doc_class

    @property
    def declared_parameters(self):
        ret = super().declared_parameters()
        ret['Schema Version'] = 'The schema version to include in the header. ' \
                                'default is 1'
        ret['Add SBDH'] = 'Whether or not to add a Standard Business Document' \
                          ' Header to the EPCIS message.  Default is true.'
        return ret
