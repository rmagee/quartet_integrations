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
# Copyright 2018 SerialLab Corp.  All rights reserved.
from quartet_output.steps import ContextKeys
from quartet_capture import models, rules, errors as capture_errors
from quartet_capture.rules import RuleContext
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.events import BusinessTransaction
from quartet_integrations.extended.events import AppendedShippingObjectEvent
from quartet_integrations.extended.parsers import SSCCParser
"""
    This Step will Append an ObjectEvent with a bizStep of shipping and
    , by default, a disposition of in_transit to the current EPCIS Document.
"""
class AppendShippingStep(rules.Step):

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)

        self.get_or_create_parameter('TemplateName', 'DEFAULT NAME OF TEMPLATE',
                                     'The name of the template that will render the appended Shipping Event.')

    def execute(self, data, rule_context: RuleContext):
        # Parse EPCIS with the SSCCParser
        parser = SSCCParser(data)
        parser.parse()

        # All SSCCs found in the ObjectEvents of the EPCIS Document (data parameter)
        # are now in the SSCCParser's sscc_list
        ssccs = parser.sscc_list

        bt1 = BusinessTransaction("urn:epcglobal:cbv:bt:0345555000050:16", "urn:epcglobal:cbv:btt:po")

        bt2 = BusinessTransaction("urn:epcglobal:cbv:bt:0345555000050:1234568978675748474839",
                                  "urn:epcglobal:cbv:btt:desadv")

        # Will have to get Quantity, LGTIN, UOM, and NDC from the Commissioning Event

        obj_event = AppendedShippingObjectEvent(
            epc_list=ssccs,
            action='OBSERVE',
            biz_step=BusinessSteps.shipping.value,
            disposition=Disposition.in_transit.value,
            business_transaction_list=[bt1, bt2],
            read_point='urn:epc:id:sgln:0355555.00000.0',
            template = self.get_parameter('TemplateName')
        )

        rule_context.context[ContextKeys.FILTERED_EVENTS_KEY.value] = [obj_event,]
        rule_context.context[ContextKeys.OBJECT_EVENTS_KEY.value] =parser._object_events
        rule_context.context[ContextKeys.AGGREGATION_EVENTS_KEY.value] = parser._aggregation_events



    def declared_parameters(self):
        return {
            'TemplateName': 'The name of the template that will render the appended Shipping Event.'
        }

    def on_failure(self):
        pass
