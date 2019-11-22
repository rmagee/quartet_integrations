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
import io
from django.core.files.base import File
from quartet_output.steps import ContextKeys
from quartet_capture import models, rules, errors as capture_errors
from quartet_capture.rules import RuleContext
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.events import BusinessTransaction
from quartet_integrations.extended.events import AppendedShippingObjectEvent
from quartet_integrations.extended.parsers import SSCCParser
from quartet_templates.models import Template

"""
    This Step will Append an ObjectEvent with a bizStep of shipping and
    , by default, a disposition of in_transit to the current EPCIS Document.
"""


class AppendShippingStep(rules.Step):

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)

        self.get_or_create_parameter('Template Name',
                                     'Shipping Event Template',
                                     'The name of the template that will '
                                     'render the appended Shipping Event.',
                                     )
        self._regEx = self.get_or_create_parameter('Quantity RegEx',
                                                   '^urn:epc:id:sgtin:[0-9]{6,12}\.0',
                                                   'RegEx that is used to count items in EPCIS')

    def execute(self, data, rule_context: RuleContext):

        # Parse EPCIS with the SSCCParser
        if isinstance(data, File):
            parser = SSCCParser(data, reg_ex=self._regEx)

        elif isinstance(data, str):
            parser = SSCCParser(io.BytesIO(str.encode(data)),
                                reg_ex=self._regEx)

        else:
            parser = SSCCParser(io.BytesIO(data), reg_ex=self._regEx)

        # parse
        parser.parse()
        # Set qty, ndc, exp_date, and lot
        qty = parser.quantity
        ndc = parser.NDC
        lot = parser.lot_number

        # All SSCCs found in the ObjectEvents of the EPCIS Document (data parameter)
        # are now in the SSCCParser's sscc_list
        ssccs = parser.sscc_list


        bt1 = BusinessTransaction("urn:epcglobal:cbv:bt:0345555000050:16",
                                  "urn:epcglobal:cbv:btt:po")

        bt2 = BusinessTransaction(
            "urn:epcglobal:cbv:bt:0345555000050:1234568978675748474839",
            "urn:epcglobal:cbv:btt:desadv")

        # Will have to get Quantity, LGTIN, UOM, and NDC from the Commissioning Event

        obj_event = AppendedShippingObjectEvent(
            epc_list=ssccs,
            action='OBSERVE',
            biz_step=BusinessSteps.shipping.value,
            disposition=Disposition.in_transit.value,
            business_transaction_list=[bt1, bt2],
            read_point='urn:epc:id:sgln:0355555.00000.0',
            template=self.get_template(),
            qty=qty
        )

        obj_event._context['count'] = qty
        obj_event._context['ndc'] = ndc
        obj_event._context['lot'] = lot

        rule_context.context[ContextKeys.FILTERED_EVENTS_KEY.value] = [
            obj_event, ]
        rule_context.context[
            ContextKeys.OBJECT_EVENTS_KEY.value] = parser._object_events
        rule_context.context[
            ContextKeys.AGGREGATION_EVENTS_KEY.value] = parser._aggregation_events

    def get_template(self):
        """
        Looks up the template based on the step parameter.
        :return: The content of the template.
        """
        template_name = self.get_parameter('Template Name',
                                           raise_exception=True)
        return Template.objects.get(name=template_name).content

    def declared_parameters(self):
        return {
            'Template Name': 'The name of the template that will render the appended Shipping Event.',
            'Quantity RegEx': '^urn:epc:id:sgtin:[0-9]{6,12}\.0'
        }

    def on_failure(self):
        pass
