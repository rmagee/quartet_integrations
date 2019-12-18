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
from io import StringIO, BytesIO
from EPCPyYes.core.v1_2 import template_events
from EPCPyYes.core.v1_2.CBV import business_steps
from quartet_capture import rules
from quartet_output.steps import OutputParsingStep as QOPS, ContextKeys
from quartet_integrations.gs1ushc.parsing import SimpleOutputParser, \
    BusinessOutputParser
from quartet_integrations.generic import mixins


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
        if self.get_boolean_parameter('Create Child Observation', 'False'):
            self.info('Create Child Observation step parameter was set to '
                      'True...checking filtered events to create '
                      'object/observe events.')
            use_sources = self.get_boolean_parameter('Use Sources', True)
            use_destinations = self.get_boolean_parameter('Use Destinations',
                                                          True)
            filtered_events = rule_context.context[
                ContextKeys.FILTERED_EVENTS_KEY.value]
            doc = template_events.EPCISDocument()
            for event in filtered_events:
                objEvent = self.create_observation_event(event, use_sources,
                                                         use_destinations)
                objEvent.biz_step = business_steps.BusinessSteps.other.value
                doc.object_events.append(objEvent)
            if len(doc.object_events) > 0:
                parser = self.get_parser_type()
                parser(BytesIO(doc.render().encode()), self.epc_output_criteria).parse()
