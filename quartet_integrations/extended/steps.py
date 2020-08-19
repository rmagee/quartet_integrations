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
import datetime
import io
import uuid
from django.core.files.base import File
from EPCPyYes.core.v1_2 import template_events
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from quartet_capture import models, rules
from quartet_capture.rules import RuleContext
from quartet_integrations.extended.environment import get_default_environment
from quartet_integrations.extended.events import AppendedShippingObjectEvent
from quartet_integrations.extended.parsers import ExtendedParser
from quartet_output.steps import ContextKeys, DynamicTemplateMixin, \
    EPCPyYesOutputStep
from quartet_templates.models import Template
from uuid import uuid4


class TemplateOutputStep(DynamicTemplateMixin, EPCPyYesOutputStep):
    """
    Will use a configured template to format a message
    """

    def declared_parameters(self):
        params = super().declared_parameters()
        params['Template'] = "The name of the template to use to render the " \
                             "output."

    def get_epcis_document_class(self,
                                 all_events) -> template_events.EPCISEventListDocument:
        epcis_document = super().get_epcis_document_class(all_events)
        template = self.get_or_create_parameter('Template',
                                                'Please configure...',
                                                'The template to render.')
        env = get_default_environment()
        epcis_document.template = self.get_template(env, template)
        epcis_document.additional_context = {'uuid':str(uuid4())}
        return epcis_document


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
                                                   '^urn:epc:id:sgtin:[0-9]{6,12}\.[0-9]{1,7}',
                                                   'RegEx that is used to count items in EPCIS')

    def execute(self, data, rule_context: RuleContext):

        # Parse EPCIS with the ExtendedParser
        if isinstance(data, File):
            parser = ExtendedParser(data,
                                    reg_ex=self._regEx)

        elif isinstance(data, str):
            parser = ExtendedParser(io.BytesIO(str.encode(data)),
                                    reg_ex=self._regEx)

        else:
            parser = ExtendedParser(io.BytesIO(data),
                                    reg_ex=self._regEx)
        # parse
        parser.parse()
        # Set qty, ndc, exp_date, and lot
        qty = parser.quantity
        # All SSCCs found in the ObjectEvents of the EPCIS Document (data parameter)
        # are now in the ExtendedParser's sscc_list
        ssccs = parser.sscc_list

        shipping_event = AppendedShippingObjectEvent(
            epc_list=ssccs,
            record_time=datetime.datetime.utcnow(),
            action='OBSERVE',
            biz_step=BusinessSteps.shipping.value,
            disposition=Disposition.in_transit.value,
            read_point=parser.read_point,
            biz_location=parser.biz_location,
            template=self.get_template(),

        )

        shipping_event._context['count'] = parser.quantity
        shipping_event._context['product_code'] = parser.product_code
        shipping_event._context['lot'] = parser.lot_number
        shipping_event._context['exp_date'] = parser.exp_date
        shipping_event._context['biz_location'] = parser.biz_location
        shipping_event._context['read_point'] = parser.read_point
        shipping_event._context['PO'] = parser.PO
        trans_date = "{0}-{1}-{2}".format(datetime.datetime.now().year,
                                          datetime.datetime.now().month,
                                          datetime.datetime.now().day)
        shipping_event._context['trans_date'] = trans_date

        rule_context.context[ContextKeys.FILTERED_EVENTS_KEY.value] = [
            shipping_event, ]
        rule_context.context[
            ContextKeys.OBJECT_EVENTS_KEY.value] = parser._object_events
        rule_context.context[
            ContextKeys.AGGREGATION_EVENTS_KEY.value] = parser._aggregation_events

        all_events = parser._object_events + parser._aggregation_events + [
            shipping_event, ]

        env = get_default_environment()

        identifier = str(uuid.uuid4())
        additional_context = {'identifier': identifier}
        epcis_document = template_events.EPCISEventListDocument(
            all_events,
            None,
            template=env.get_template(
                'extended/ext_epcis_document.xml'
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
