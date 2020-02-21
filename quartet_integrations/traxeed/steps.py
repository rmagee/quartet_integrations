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
from datetime import timedelta
import io
import uuid
from django.core.files.base import File
from EPCPyYes.core.v1_2 import template_events
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.events import BusinessTransaction, Source, Destination
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from quartet_capture import models, rules
from quartet_capture.rules import RuleContext
from quartet_integrations.extended.environment import get_default_environment
from quartet_integrations.extended.events import AppendedShippingObjectEvent
from quartet_integrations.traxeed.parsers import (
    TraxeedParser,
    TraxeedRfxcelParser,
    TraxeedIRISParser
)
from quartet_output.steps import ContextKeys
from quartet_templates.models import Template

"""
 Processes EPCIS coming from Traxeed
"""

class ProcessTraxeedStep(rules.Step):

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
            parser = TraxeedParser(data,
                                   reg_ex=self._regEx)

        elif isinstance(data, str):
            parser = TraxeedParser(io.BytesIO(str.encode(data)),
                                   reg_ex=self._regEx)

        else:
            parser = TraxeedParser(io.BytesIO(data),
                                   reg_ex=self._regEx)
        # parse
        parser.parse()

        rule_context.context[
            ContextKeys.OBJECT_EVENTS_KEY.value] = parser._object_events
        rule_context.context[
            ContextKeys.AGGREGATION_EVENTS_KEY.value] = parser._aggregation_events

        # put the parser in the context so the data isn't parsed again in the subsequent step
        rule_context.context['PARSER'] = parser

        env = get_default_environment()

        identifier = str(uuid.uuid4())
        additional_context = {'identifier': identifier}

        all_events = parser._object_events + parser._aggregation_events
        epcis_document = template_events.EPCISEventListDocument(
            all_events,
            None,
            template=env.get_template(
                'traxeed/tx_hk_epcis_document.xml'
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
        return {
            'Template Name': 'The name of the template that will render the appended Shipping Event.',
            'Quantity RegEx': '^urn:epc:id:sgtin:[0-9]{6,12}\.0',
        }

    def on_failure(self):
        pass


class ShipTraxeedStep(rules.Step):

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)

    def execute(self, data, rule_context: RuleContext):

        parser = rule_context.context['PARSER']
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
        shipping_event._context['product_code'] = parser.ndc
        shipping_event._context['lot'] = parser.lot_number
        shipping_event._context['exp_date'] = parser.exp_date
        shipping_event._context['biz_location'] = parser.biz_location
        shipping_event._context['read_point'] = parser.read_point
        shipping_event._context['PO'] = parser.PO
        trans_date = "{0}-{1}-{2}".format(datetime.datetime.now().year, datetime.datetime.now().month,
                                          datetime.datetime.now().day)
        shipping_event._context['trans_date'] = trans_date

        all_events = [shipping_event, ]

        env = get_default_environment()

        identifier = str(uuid.uuid4())
        additional_context = {'identifier': identifier}
        epcis_document = template_events.EPCISEventListDocument(
            all_events,
            None,
            template=env.get_template(
                'traxeed/tx_hk_epcis_document.xml'
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

    def declared_parameters(self):
        return {
            'Template Name': 'The name of the template that will render the appended Shipping Event.',
        }

    def on_failure(self):
        pass

    def get_template(self):
        """
        Looks up the template based on the step parameter.
        :return: The content of the template.
        """
        template_name = self.get_parameter('Template Name',
                                           raise_exception=True)

        ret_val = Template.objects.get(name=template_name).content
        return ret_val


class TraxeedRfxcel(rules.Step):

    def __init__(self, db_task: models.Task, **kwargs):

        self._regEx = '^urn:epc:id:sgtin:[0-9]{6,12}\.[0-9]{1,7}'


        self._source_op = self.get_or_create_parameter('Source Owning Party','',
                                                       'The SGLN URN of the Source Owning Party')
        self._source_location = self.get_or_create_parameter('Source Location', '',
                                                       'The SGLN URN of the Source Location')
        self._destination_op = self.get_or_create_parameter('Destination Owning Party', '',
                                                                  'The SGLN URN of the Destination Owning Party')
        self._destination_location = self.get_or_create_parameter('Destination Location', '',
                                                             'The SGLN URN of the Destination Location')

        env = get_default_environment()
        temp = env.get_template('traxeed/tx_rfxcel_epcis_document.xml')
        self._doc_template = temp
        temp = env.get_template('traxeed/tx_rf_object_events.xml')
        self._obj_template = temp

        super().__init__(db_task, **kwargs)

    def execute(self, data, rule_context: RuleContext):

        # Parse EPCIS with the ExtendedParser
        if isinstance(data, File):
            parser = TraxeedRfxcelParser(data,
                                    reg_ex=self._regEx)

        elif isinstance(data, str):
            parser = TraxeedRfxcelParser(io.BytesIO(str.encode(data)),
                                    reg_ex=self._regEx)

        else:
            parser = TraxeedRfxcelParser(io.BytesIO(data),
                                    reg_ex=self._regEx)
        # parse
        parser.parse()
        # get the first aggregation event for the record/event times
        agg_event = parser._aggregation_events[0]
        # adjust the record/event time into the future
        t = datetime.datetime.strptime(agg_event.record_time, '%Y-%m-%dT%H:%M:%SZ')
        dt = t + timedelta(seconds=10)

        # All SSCCs found in the ObjectEvents of the EPCIS Document (data parameter)
        # are now in the ExtendedParser's sscc_list
        ssccs = parser.sscc_list

        biz_trans = BusinessTransaction(biz_transaction=parser.PO, type="urn:epcglobal:cbv:btt:po")


        source_op = Source(source = self._source_op, source_type = 'urn:epcglobal:cbv:sdt:owning_party')
        source_location = Source(source=self._source_location, source_type='urn:epcglobal:cbv:sdt:location' )
        destination_op = Destination(destination_type='urn:epcglobal:cbv:sdt:owning_party', destination=self._destination_op)
        destination_location = Destination(destination_type='urn:epcglobal:cbv:sdt:location', destination=self._destination_location)

        source_list = [source_op, source_location]
        destination_list = [destination_op, destination_location]

        shipping_event = template_events.ObjectEvent(
            epc_list=ssccs,
            record_time=dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
            event_time=dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
            event_timezone_offset=agg_event.event_timezone_offset,
            action="OBSERVE",
            biz_step=BusinessSteps.shipping.value,
            disposition=Disposition.in_transit.value,
            read_point=agg_event.read_point,
            biz_location=agg_event.biz_location,
            business_transaction_list = [biz_trans],
            source_list=source_list,
            destination_list=destination_list,
            template=self._obj_template
        )



        rule_context.context[ContextKeys.FILTERED_EVENTS_KEY.value] = [
            shipping_event, ]
        rule_context.context[
            ContextKeys.OBJECT_EVENTS_KEY.value] = parser._object_events
        rule_context.context[
            ContextKeys.AGGREGATION_EVENTS_KEY.value] = parser._aggregation_events

        all_events = parser._object_events + parser._aggregation_events + [shipping_event, ]

        env = get_default_environment()

        identifier = str(uuid.uuid4())
        additional_context = {'identifier': identifier}
        epcis_document = template_events.EPCISEventListDocument(
            all_events,
            None,
            template=env.get_template(
                'traxeed/tx_rfxcel_epcis_document.xml'
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

    def declared_parameters(self):
        return {
            'Source Owning Party': 'The SGLN URN of the Source Owning Party',
            'Source Location': 'The SGLN URN of the Source Location',
            'Destination Owning Party': 'The SGLN URN of the Destination Owning Party',
            'Destination Location': 'The SGLN URN of the Destination Location',
        }

    def on_failure(self):
        pass

    def get_template(self):
        """
        Looks up the template based on the step parameter.
        :return: The content of the template.
        """
        template_name = self.get_parameter('Template Name',
                                           raise_exception=True)


        ret_val = Template.objects.get(name=template_name).content
        return ret_val


class TraxeedIRIS(rules.Step):

    def __init__(self, db_task: models.Task, **kwargs):

        self._regEx = '^urn:epc:id:sgtin:[0-9]{6,12}\.[0-9]{1,7}'


        self._source_op = self.get_or_create_parameter('Source Owning Party','',
                                                       'The SGLN URN of the Source Owning Party')
        self._source_location = self.get_or_create_parameter('Source Location', '',
                                                       'The SGLN URN of the Source Location')
        self._destination_op = self.get_or_create_parameter('Destination Owning Party', '',
                                                                  'The SGLN URN of the Destination Owning Party')
        self._destination_location = self.get_or_create_parameter('Destination Location', '',
                                                             'The SGLN URN of the Destination Location')

        env = get_default_environment()
        temp = env.get_template('traxeed/tx_rfxcel_epcis_document.xml')
        self._doc_template = temp
        temp = env.get_template('traxeed/tx_rf_object_events.xml')
        self._obj_template = temp

        super().__init__(db_task, **kwargs)

    def execute(self, data, rule_context: RuleContext):

        # Parse EPCIS with the ExtendedParser
        if isinstance(data, File):
            parser = TraxeedIRISParser(data,
                                    reg_ex=self._regEx)

        elif isinstance(data, str):
            parser = TraxeedIRISParser(io.BytesIO(str.encode(data)),
                                    reg_ex=self._regEx)

        else:
            parser = TraxeedIRISParser(io.BytesIO(data),
                                    reg_ex=self._regEx)
        # parse
        parser.parse()
        # get the first aggregation event for the record/event times
        agg_event = parser._aggregation_events[0]
        # adjust the record/event time into the future
        t = datetime.datetime.strptime(agg_event.record_time, '%Y-%m-%dT%H:%M:%SZ')
        dt = t + timedelta(seconds=10)

        # All SSCCs found in the ObjectEvents of the EPCIS Document (data parameter)
        # are now in the ExtendedParser's sscc_list
        ssccs = parser.sscc_list

        biz_trans = BusinessTransaction(biz_transaction=parser.PO, type="urn:epcglobal:cbv:btt:po")


        source_op = Source(source = self._source_op, source_type = 'urn:epcglobal:cbv:sdt:owning_party')
        source_location = Source(source=self._source_location, source_type='urn:epcglobal:cbv:sdt:location' )
        destination_op = Destination(destination_type='urn:epcglobal:cbv:sdt:owning_party', destination=self._destination_op)
        destination_location = Destination(destination_type='urn:epcglobal:cbv:sdt:location', destination=self._destination_location)

        source_list = [source_op, source_location]
        destination_list = [destination_op, destination_location]

        shipping_event = template_events.ObjectEvent(
            epc_list=ssccs,
            record_time=dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
            event_time=dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
            event_timezone_offset=agg_event.event_timezone_offset,
            action="OBSERVE",
            biz_step=BusinessSteps.shipping.value,
            disposition=Disposition.in_transit.value,
            read_point=agg_event.read_point,
            biz_location=agg_event.biz_location,
            business_transaction_list = [biz_trans],
            source_list=source_list,
            destination_list=destination_list,
            template=self._obj_template
        )



        rule_context.context[ContextKeys.FILTERED_EVENTS_KEY.value] = [
            shipping_event, ]
        rule_context.context[
            ContextKeys.OBJECT_EVENTS_KEY.value] = parser._object_events
        rule_context.context[
            ContextKeys.AGGREGATION_EVENTS_KEY.value] = parser._aggregation_events

        all_events = parser._object_events + parser._aggregation_events + [shipping_event, ]

        env = get_default_environment()

        identifier = str(uuid.uuid4())
        additional_context = {'identifier': identifier}
        epcis_document = template_events.EPCISEventListDocument(
            all_events,
            None,
            template=env.get_template(
                'traxeed/tx_rfxcel_epcis_document.xml'
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

    def declared_parameters(self):
        return {
            'Source Owning Party': 'The SGLN URN of the Source Owning Party',
            'Source Location': 'The SGLN URN of the Source Location',
            'Destination Owning Party': 'The SGLN URN of the Destination Owning Party',
            'Destination Location': 'The SGLN URN of the Destination Location',
        }

    def on_failure(self):
        pass

    def get_template(self):
        """
        Looks up the template based on the step parameter.
        :return: The content of the template.
        """
        template_name = self.get_parameter('Template Name',
                                           raise_exception=True)


        ret_val = Template.objects.get(name=template_name).content
        return ret_val
