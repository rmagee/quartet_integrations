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

from gs123.conversion import URNConverter
from quartet_capture import models
from quartet_integrations.optel.epcpyyes import get_default_environment
from quartet_integrations.optel.parsing import OptelEPCISLegacyParser, \
    ConsolidationParser
from quartet_integrations.sap.steps import SAPParsingStep
from quartet_output import steps
from quartet_templates.models import Template

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

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.replace_timezone = self.get_boolean_parameter('Replace Timezone',
                                                           False)

    def _parse(self, data):
        return OptelEPCISLegacyParser(data).parse(
            replace_timezone=self.replace_timezone
        )

    @property
    def declared_parameters(self):
        params = super().declared_parameters
        params['Replace Timezone'] = 'Whether or not to replace explicit ' \
                                     'timezone declarations in event times ' \
                                     'with the timezone offset in the event.'
        return params


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
