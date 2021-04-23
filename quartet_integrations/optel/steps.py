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

from enum import Enum
from gs123.conversion import URNConverter
from quartet_capture import models
from quartet_capture.rules import RuleContext, Step
from quartet_integrations.optel.epcpyyes import get_default_environment
from quartet_integrations.optel.parsing import OptelEPCISLegacyParser, \
    ConsolidationParser, OptelAutoShipParser, OptelCompactV2Parser
from quartet_integrations.sap.steps import SAPParsingStep
from quartet_output import steps
from quartet_templates.models import Template
from quartet_masterdata.models import TradeItem, TradeItemField, \
    OutboundMapping, Company

from EPCPyYes.core.v1_2.events import Action, BusinessTransaction, Source, Destination
from EPCPyYes.core.v1_2.template_events import ObjectEvent
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.CBV.business_transactions import BusinessTransactionType
from EPCPyYes.core.v1_2.CBV.source_destination import SourceDestinationTypes


class ContextKeys(Enum):
    """
    Use this keys to place event and epc inforamtion in context for building
    a shipping event from filtered SSCCs, trade items and batch/lot number.
    """
    FILTERED_SSCCS = 'FILTERED_SSCCS'
    FILTERED_LOT_NUMBER = 'FILTERED_LOT_NUMBER'
    FILTERED_GTIN = 'FILTERED_GTIN'
    OUTBOUND_MAPPING = 'OUTBOUND_MAPPING'
    TRADE_ITEMS_MASTERDATA = 'TRADE_ITEMS_MASTERDATA'


class AddCommissioningDataStep(steps.AddCommissioningDataStep,
                               steps.DynamicTemplateMixin):
    """
    Changes the default template and environment for the EPCPyYes
    object events.  Will first attempt to use a defined QU4RTET template
    to render object events, otherwise it will use the default optel
    object_event.xml template in this package.

    To define a QU4RTET template use the Template step parameter and assign
    it the name of a given QU4RTET template.  This template will then be used
    """

    def process_events(self, events: list):
        env = get_default_environment()
        template = self.get_template(env, 'optel/object_event.xml')
        for event in events:
            for epc in event.epc_list:
                if ':sscc:' in epc:
                    parsed_sscc = URNConverter(epc)
                    event.company_prefix = parsed_sscc._company_prefix
                    event.extension_digit = parsed_sscc._extension_digit
                    break
            event.template = template
            event._env = env

        return events


class AppendCommissioningStep(steps.AppendCommissioningStep,
                              steps.DynamicTemplateMixin,
                              steps.FilterEPCsMixin):
    """
    Overrides the default AppendCommissioningDataStep to provide object
    events that use the optel template for object events.  This template
    uses the optel linemaster format from the 2013/14 time frame.
    """

    def get_object_events(self, epcs):
        """
        Overrides the default function to apply filtering based on the regex
        and append step parameter values.
        :param epcs: The
        :return:
        """
        self.info('Looking for the EPC Filter Search parameter.')
        filter_regex = self.get_parameter('EPC Filter Search', None)
        filter_action = self.get_parameter('Filter Event Action', 'OBSERVE')
        append_all = self.get_parameter('Append All Object Events', True)
        if filter_regex:
            reverse = self.get_boolean_parameter('Reverse Filter', False)
            self.info('Found Search Value %s. Filter event action '
                      'is %s', filter_regex, filter_action)
        env = get_default_environment()
        template = self.get_template(env, 'optel/object_event.xml')
        object_events = super().get_object_events(epcs)
        if not append_all:
            self.info('Filtering out any non commissioning events...')
            object_events = [object_event for object_event in
                             object_events if object_event.action == 'ADD']
        for object_event in object_events:
            object_event.template = template
            object_event._env = env
            if filter_regex and object_event.action == filter_action:
                object_event.epc_list = self.filter(object_event.epc_list,
                                                    filter_regex,
                                                    reverse=reverse)
        return object_events

    def declared_parameters(self):
        return {
            'Template': 'The name of the QU4RTET template to use if you '
                        'want to override the default template.',
            'EPC Filter Search': 'A search value that is used to filter '
                                 'out EPC values during processing.  Typically '
                                 'used to remove redundant EPC data.',
            'Reverse Filter': 'Set to True if you want to use the regex '
                              'parameter to identify EPCs to include rather '
                              'than filter out.',
            'Filter Event Action': 'The action of the events to apply the EPC '
                                   'filter against.  Can '
                                   'be ADD, DELETE, or OBSERVE (case '
                                   ' sensitive). Default is OBSERVE.',
            'Append All Object Events': 'Whether or not to append events'
                                        ' that are not commissioning events. '
                                        'default is True.'
        }


class OptelLineParsingStep(SAPParsingStep):
    """
    A QU4RTET parsing step that can parse SAP XML data that contains
    custom event data.
    """

    def execute(self, data, rule_context: RuleContext):
        self.replace_timezone = self.get_boolean_parameter('Replace Timezone',
                                                           False)
        self.loose_enforcement = self.get_boolean_parameter(
            'LooseEnforcement', False)
        self.format = self.get_parameter('Format', 'XML')
        self.recursive_child_update = self.get_or_create_parameter(
            'Recursive Child Update', 'True',
            "Whether or not to update children during observe events."
        ).lower() == "true"
        self.use_top_for_update = self.get_or_create_parameter(
            'Use Top For Child Update', 'True',
            'Whether or not to use top records or true recursion.'
        ).lower() == "true"
        self.rule_context = rule_context
        super().execute(data, rule_context)

    def _parse(self, data):
        return OptelEPCISLegacyParser(
            data, recursive_child_update=True,
            child_update_from_top=self.use_top_for_update,
            rule_context=self.rule_context,
        ).parse(
            replace_timezone=self.replace_timezone,
        )

    @property
    def declared_parameters(self):
        params = super().declared_parameters
        params['Replace Timezone'] = 'Whether or not to replace explicit ' \
                                     'timezone declarations in event times ' \
                                     'with the timezone offset in the event.'
        return params


class OptelAutoShipStep(OptelLineParsingStep):
    """
    A QU4RTET parsing step that can parse SAP XML data that contains
    custom event data.
    """

    def _parse(self, data):
        return OptelAutoShipParser(
            data, recursive_child_update=False,
            child_update_from_top=False,
            rule_context=self.rule_context,
        ).parse(
            replace_timezone=self.replace_timezone,
        )


class ConsolidationParsingStep(OptelLineParsingStep):
    """
    Uses the consolidation parser to handle any bloated optel messages.
    """

    def _parse(self, data):
        return ConsolidationParser(data).parse(self.replace_timezone)


class EPCPyYesOutputStep(steps.EPCPyYesOutputStep):
    """
    Overrides the standard output step in order to supply a different
    output template for the header of the generated EPCIS document.
    """

    def get_epcis_document_class(self, all_events):
        """
        Replaces the default document template with the optel one.
        :param all_events: The events that will be rendered to XML.
        :return: The document class with a new template specified.
        """
        document = super().get_epcis_document_class(all_events)
        env = get_default_environment()
        template = env.get_template('optel/epcis_events_document.xml')
        context_search_value = self.get_parameter('Context Search Value', None)
        context_reverse_search = self.get_boolean_parameter(
            'Context Reverse Search',
            False)
        additional_context = self.get_parameter('Additional Context')
        if additional_context or context_search_value:
            object_ilmd = Template.objects.get(name=additional_context).content
            additional_context = {'object_ilmd': object_ilmd,
                                  'search_value': context_search_value,
                                  'reverse_search': context_reverse_search
                                  }
            self.info('Adding additional context : %s', additional_context)
            document.additional_context = additional_context
        document.template = template
        return document

    def declared_parameters(self):
        return {
            'Additional Context': 'The name of a quartet template containing '
                                  'additional data to insert into the ILMD.',
            'Context Search Value': 'The value to look for in a given serial '
                                    'number to produce the aditional context '
                                    'within a message. Default is None',
            'Context Reverse Search': 'Whether or not to include the '
                                      'Additional Context if the search value'
                                      'is found or whether to include it if'
                                      ' the search value is not found.  Set '
                                      'to True to set additional context '
                                      'when the value is no found. Default '
                                      'is False.'
        }


class OptelCompactV2ParsingStep(SAPParsingStep):
    """
    A QU4RTET parsing step that can parse Optel Compact XML data that contains
    custom extensions.
    """

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.extenstion_digit = self.get_or_create_parameter(
            'EA Extension Digit', 
            default='0',
            description='Extension digit of the EA item (the smallest unit).')
        self.lot_number = None
        self.ssccs = []
        self.output_criteria = self.get_parameter(
            'EPCIS Output Criteria', raise_exception=True)
        self.skip_parsing = self.get_boolean_parameter('Skip Parsing', False)
        self.trade_items = None

    def _parse(self, data):
        parser = OptelCompactV2Parser(
            data,
            extension_digit=self.extenstion_digit,
            skip_parsing=self.skip_parsing)
        ret = parser.parse()
        # Get selected data from the parser
        self.info('Getting lot number, SSCCs, and trade items from data')
        self.lot_number = parser.lot_number
        self.ssccs = parser.ssccs
        self.gtin = parser.gtin
        self.trade_items = parser.trade_item_list
        return ret
    
    def append_to_rule_context(self, rule_context):
        self.info('Adding pallets and lot number to the rule context.')
        rule_context.context[
            ContextKeys.FILTERED_GTIN.value
        ] = self.gtin
        rule_context.context[
            ContextKeys.FILTERED_SSCCS.value
        ] = self.ssccs
        # Add Lot Number to the rule context
        rule_context.context[
            ContextKeys.FILTERED_LOT_NUMBER.value
        ] = self.lot_number
        # Add Output Criteria to the rule context
        rule_context.context[
            steps.ContextKeys.EPCIS_OUTPUT_CRITERIA_KEY.value
        ] = self.output_criteria
        rule_context.context[
            ContextKeys.TRADE_ITEMS_MASTERDATA.value
        ] = self.trade_items

    def execute(self, data, rule_context: RuleContext):
        super().execute(data, rule_context)
        # Add Filtered SSCCs to the rule context
        self.append_to_rule_context(rule_context)


class CreateShippingEventStep(Step, steps.DynamicTemplateMixin):
    """
    This step was designed to work along with the OptelCompactV2ParsingStep.
    It creates shipping event based on the filtered sscc's and trade items.
    To work properly it needs Outbound Mapping to be defined and linked to
    the filtered trade item's field as:
        - name = GTIN14
        - value = Company Name from OutboundMapping's main company
    """

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.template = self.get_parameter(
            'Template Name', ''
        )
        self.use_location = self.get_boolean_parameter(
            'Use Location', True
        )

    def execute(self, data, rule_context: RuleContext):
        self.rule_context = rule_context
        # Get mapping for the shipping event
        mapping = self.get_mapping()
        # Build a new shipping event
        shipping_event = self.build_shipping_event(mapping)
        rule_context.context['masterdata'] = {
            mapping.company.SGLN: mapping.company.__dict__,
            mapping.from_business.SGLN: mapping.from_business.__dict__,
            mapping.to_business.SGLN: mapping.to_business.__dict__
        }

    def get_mapping(self):
        """
        Looks for a GTIN14 value in the rule context. Then it looks for a
        TradeItem instance based on the GTIN14. Checks the TradeItems's field
        by the name of GTIN14 value. This fields holds company name as a value
        which is used to get a OutboundMapping.
        """
        # get trade item gtin from rule context
        self.info('Looking for a GTIN14 value in the rule context '
                  'using FILTERED_GTIN context key')
        gtin = self.rule_context.context.get(
            ContextKeys.FILTERED_GTIN.value)
        try:
            # Get trade item information
            item = TradeItem.objects.get(GTIN14=gtin)
            # Get TradeItemField for company name
            field = item.tradeitemfield_set.get(name=gtin)
            # Get OutboundMapping using company name
            mapping = OutboundMapping.objects.get(company__name=field.value)
        except TradeItem.DoesNotExist:
            raise self.TradeItemDoesNotExist(
                'Trade Item with %s GTIN14 was not added to masterdata.' % gtin)
        except TradeItemField.DoesNotExist:
            raise self.TradeItemFieldDoesNotExist(
                'Trade Item Field for the %s GTIN14 was not created for TradeItem. '
                'You need to create TradeItemField for this trade item with '
                'name equal to GTIN14 and value equal to target company name.' % gtin)
        except OutboundMapping.DoesNotExist:
            raise self.OutBoundMappingDoesNotExist(
                'Outbound Mapping was not created for the company "%s". '
                'You need to create OutboundMapping for the shipping '
                'event target company.' % field.value)
        # Add it to the rule context as Filtered Events ContextKey
        self.rule_context.context[
            ContextKeys.OUTBOUND_MAPPING.value
        ] = mapping
        return mapping

    def build_shipping_event(self, mapping):
        """
        Creates a Shipping event using values in the rule context.
        It requires a Lot Number, SSCCs.
        """
        lot_number = self.rule_context.context.get(
            ContextKeys.FILTERED_LOT_NUMBER.value)
        self.info('Lot number found: %s' % lot_number)
        ssccs = self.rule_context.context.get(
            ContextKeys.FILTERED_SSCCS.value)
        self.info('SSCC\'s list found: %s' % ssccs)
        # Create EPCIS Shipping Event
        self.info('Creating new shipping event.')
        shipping_event = ObjectEvent()
        shipping_event.action = Action.observe.value
        shipping_event.biz_step = BusinessSteps.shipping.value
        shipping_event.disposition = Disposition.in_transit.value
        shipping_event.epc_list = ssccs
        # Set up BusinessTransactionList
        gln = mapping.ship_from.GLN13
        shipping_event.business_transaction_list.append(
            BusinessTransaction(
                'urn:epcglobal:cbv:bt:%s:%s' % (gln, lot_number),
                BusinessTransactionType.Despatch_Advice.value
            )
        )
        # Set Source and Destination
        # Check if this sould be either possessing party or location
        if self.use_location:
            source_dest_type = SourceDestinationTypes.location.value
        else:
            source_dest_type = SourceDestinationTypes.possessing_party.value
        self.info('Using "%s" in source and destination tags.' % source_dest_type)
        shipping_event.source_list.append(
            Source(
                SourceDestinationTypes.owning_party.value,
                mapping.from_business.SGLN
            )
        )
        shipping_event.source_list.append(
            Source(
                source_dest_type,
                mapping.ship_from.SGLN
            )
        )
        shipping_event.destination_list.append(
            Destination(
                SourceDestinationTypes.owning_party.value,
                mapping.to_business.SGLN
            )
        )
        shipping_event.destination_list.append(
            Destination(
                source_dest_type,
                mapping.ship_to.SGLN
            )
        )
        # Set template if path was provided
        if self.template:
            env = get_default_environment()
            template = self.get_template(
                env,
                'quartet_tracelink/disposition_assigned.xml'
            )
            shipping_event.template = template
        # Add event to rule context
        self.info('Adding shipping event to the rule context. This '
                  'action will replace previously added events with '
                  'the FILTERED_EVENTS_KEY key.')
        self.rule_context.context[
            steps.ContextKeys.FILTERED_EVENTS_KEY.value
        ] = [shipping_event,]
        # return shipping event
        self.rule_context.context['SENDER_GLN'] = mapping.ship_from.company.GLN13
        self.rule_context.context['RECEIVER_GLN'] = mapping.to_business.GLN13
        self.info('Setting sender and receiver GLN\'s. Sender: %s '
                  'Receiver: %s' % (
                      mapping.ship_from.company.GLN13,
                      mapping.to_business.GLN13))
        return shipping_event


    def declared_parameters(self):
        return {
            'Template Name': 'Template used for rendering shiping object event.',
        }

    def on_failure(self):
        pass

    class TradeItemDoesNotExist(Exception):
        pass

    class TradeItemFieldDoesNotExist(Exception):
        pass
    
    class OutBoundMappingDoesNotExist(Exception):
        pass
