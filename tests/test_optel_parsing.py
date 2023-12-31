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
from django.conf import settings
import os

from django.test import TestCase

from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.events import EventType
from quartet_capture.models import Rule, Step, StepParameter, Task
from quartet_capture.tasks import execute_rule, execute_queued_task
from quartet_epcis.models import entries
from quartet_epcis.db_api.queries import EPCISDBProxy
from quartet_epcis.models import events
from quartet_epcis.models.events import Event
from quartet_epcis.parsing.context_parser import BusinessEPCISParser
from quartet_integrations.optel.parsing import OptelEPCISLegacyParser, \
    ConsolidationParser
from quartet_output import models
from quartet_output import steps
from quartet_output.models import EPCISOutputCriteria
from quartet_output.steps import ContextKeys
from quartet_integrations.optel.steps import ContextKeys as OptelContextKeys
from quartet_masterdata.models import TradeItem, Company, Location, \
    OutboundMapping, TradeItemField


class TestOpelLegacyParser(TestCase):

    def test_epcis_file(self):
        curpath = os.path.dirname(__file__)
        parser = OptelEPCISLegacyParser(
            os.path.join(curpath, 'data/optel-data-obj.xml'))
        parser.parse()

    def test_double_tz_file(self):
        curpath = os.path.dirname(__file__)
        parser = ConsolidationParser(
            os.path.join(curpath, 'data/optel_double_timezone.xml'))
        parser.parse(replace_timezone=True)

    def test_consolidate(self):
        curpath = os.path.dirname(__file__)
        parser = ConsolidationParser(
            os.path.join(curpath, 'data/optel-data.xml'))
        parser.parse()
        event = Event.objects.get(type='ob')
        entry_count = entries.EntryEvent.objects.filter(event=event).count()
        self.assertEqual(353, entry_count)


class TestOptelRule(TestCase):
    def test_optel_step(self):
        rule = self._create_rule()
        self._create_sap_step(rule)
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/optel-data-obj.xml')
        db_task = self._create_task(rule)
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)

    def _create_rule(self):
        rule = Rule()
        rule.name = 'EPCIS'
        rule.description = 'test rule'
        rule.save()
        return rule

    def _create_sap_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 3
        step.name = 'Parse Optel EPCIS'
        step.step_class = 'quartet_integrations.optel.steps.OptelLineParsingStep'
        step.description = 'optel line master unit test parsing step'
        step.save()

    def _create_task(self, rule):
        task = Task()
        task.rule = rule
        task.name = 'unit test task'
        task.save()
        return task


class TestConsolidationRule(TestCase):
    def test_optel_step(self):
        rule = self._create_rule()
        self._create_sap_step(rule)
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/optel-data.xml')
        db_task = self._create_task(rule)
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)

    def test_optel_step_with_dualtz(self):
        rule = self._create_rule()
        self._create_sap_step(rule, tz_param=True)
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/optel_double_timezone.xml')
        db_task = self._create_task(rule)
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)

    def _create_rule(self):
        rule = Rule()
        rule.name = 'EPCIS'
        rule.description = 'test rule'
        rule.save()
        return rule

    def _create_sap_step(self, rule, tz_param=False):
        step = Step()
        step.rule = rule
        step.order = 3
        step.name = 'Parse Optel EPCIS'
        step.step_class = 'quartet_integrations.optel.steps.ConsolidationParsingStep'
        step.description = 'optel line master unit test parsing step'
        step.save()
        if tz_param:
            param = StepParameter.objects.create(step=step,
                                                 name='Replace Timezone',
                                                 value='True')

    def _create_task(self, rule):
        task = Task()
        task.rule = rule
        task.name = 'unit test task'
        task.save()
        return task


class TestOutputParsing(TestCase):
    def _create_endpoint(self):
        ep = models.EndPoint()
        ep.urn = getattr(settings, 'TEST_SERVER', 'http://testhost')
        ep.name = 'Test EndPoint'
        ep.save()
        return ep

    def _create_auth(self):
        auth = models.AuthenticationInfo()
        auth.description = 'Unit test auth.'
        auth.username = 'UnitTestUser'
        auth.password = 'UnitTestPassword'
        auth.save()
        return auth

    def _create_good_ouput_criterion(self):
        endpoint = self._create_endpoint()
        auth = self._create_auth()
        eoc = EPCISOutputCriteria()
        eoc.name = "Test Criteria"
        eoc.action = "OBSERVE"
        eoc.event_type = EventType.Object.value
        eoc.disposition = Disposition.in_transit.value
        eoc.biz_step = BusinessSteps.shipping.value
        eoc.read_point = 'urn:epc:id:sgln:0555555.00002.0'
        eoc.authentication_info = auth
        eoc.end_point = endpoint
        eoc.save()
        return eoc

    def _create_step(self, rule,
                     step_class='quartet_output.steps.OutputParsingStep'
                     ):
        step = Step()
        step.rule = rule
        step.order = 1
        step.name = 'Output Determination'
        step.step_class = step_class
        step.description = 'unit test step'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'EPCIS Output Criteria'
        step_parameter.value = 'Test Criteria'
        step_parameter.save()
        return step

    def _create_parsing_step(
        self, rule,
        step_class='quartet_integrations.optel.steps.ConsolidationParsingStep'
    ):
        step = Step()
        step.rule = rule
        step.order = 1
        step.name = 'Parsing Step'
        step.step_class = step_class
        step.description = 'unit test step'
        step.save()

    def _create_output_steps(self, rule):
        step = Step()
        step.rule = rule
        step.order = 2
        step.name = 'UnpackHierarchies'
        step.step_class = 'quartet_output.steps.UnpackHierarchyStep'
        step.description = 'unit test unpacking step'
        step.save()

    def _create_comm_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 3
        step.name = 'CreateCommissioning'
        step.step_class = 'quartet_integrations.optel.steps.AddCommissioningDataStep'
        step.description = 'unit test commissioning step'
        step.save()

    def _create_epcpyyes_step(self, rule, json=False):
        step = Step()
        step.rule = rule
        step.order = 4
        step.name = 'Create EPCIS'
        step.step_class = 'quartet_integrations.optel.steps.EPCPyYesOutputStep'
        step.description = 'Creates EPCIS XML or JSON and inserts into rule' \
                           'context.'
        step.save()
        if json:
            param = StepParameter.objects.create(
                step=step,
                name='JSON',
                value=True
            )

    def _create_task_step(self, rule, order=5):
        step = Step()
        step.rule = rule
        step.order = order
        step.name = 'Create Output Task'
        step.step_class = 'quartet_output.steps.CreateOutputTaskStep'
        step.description = 'Looks for any EPCIS data on the context and ' \
                           'then, if found, creates a new output task using ' \
                           'the configured Output Rule step parameter.'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'Output Rule'
        step_parameter.value = 'Transport Rule'
        step_parameter.description = 'The name of the rule to create a new ' \
                                     'task with.'
        step_parameter.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'run-immediately'
        step_parameter.value = 'True'
        step_parameter.description = 'The name of the rule to create a new ' \
                                     'task with.'
        step_parameter.save()
        return step

    def _create_rule(self):
        rule = Rule()
        rule.name = 'output-test'
        rule.description = 'output test rule'
        rule.save()
        return rule

    def _create_transport_rule(self):
        rule = Rule()
        rule.name = 'Transport Rule'
        rule.description = 'Attempts to send data using transport step(s).'
        rule.save()
        return rule

    def _create_transport_step(self, rule, put_data='False'):
        step = Step()
        step.rule = rule
        step.order = 1
        step.name = 'Transport'
        step.step_class = 'quartet_output.steps.TransportStep'
        step.description = 'Sends test data.'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'run-immediately'
        step_parameter.value = 'True'
        step_parameter.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'put-data'
        step_parameter.value = put_data
        step_parameter.save()

    def _create_rule(self):
        rule = Rule()
        rule.name = 'output-test'
        rule.description = 'output test rule'
        rule.save()
        return rule

    def _create_task(self, rule):
        task = Task()
        task.rule = rule
        task.name = 'unit test task'
        task.save()
        return task

    def _parse_test_data(self, test_file='data/epcis.xml',
                         parser_type=BusinessEPCISParser,
                         recursive_decommission=False):
        curpath = os.path.dirname(__file__)
        if isinstance(parser_type, BusinessEPCISParser):
            parser = parser_type(
                os.path.join(curpath, test_file),
                recursive_decommission=recursive_decommission
            )
        else:
            parser = parser_type(
                os.path.join(curpath, test_file),
            )
        message_id = parser.parse()
        print(parser.event_cache)
        parser.clear_cache()
        return message_id, parser

    def test_rule_with_agg_comm_output(self):
        self._create_good_ouput_criterion()
        db_rule = self._create_rule()
        self._create_step(db_rule)
        self._create_output_steps(db_rule)
        self._create_comm_step(db_rule)
        self._create_epcpyyes_step(db_rule)
        self._create_task_step(db_rule)
        db_rule2 = self._create_transport_rule()
        self._create_transport_step(db_rule2)
        db_task = self._create_task(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        self._parse_test_data('data/commissioning.xml')
        self._parse_test_data('data/aggregation.xml')
        data_path = os.path.join(curpath, 'data/shipping.xml')
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
            self.assertEqual(
                len(context.context[ContextKeys.AGGREGATION_EVENTS_KEY.value]),
                12,
                "There should be twelve filtered events."
            )
            for event in context.context[
                ContextKeys.AGGREGATION_EVENTS_KEY.value]:
                if event.parent_id in [
                    'urn:epc:id:sgtin:0555553.300106.259812595316',
                    'urn:epc:id:sgtin:0555553.300106.127892027084']:
                    self.assertEqual(len(event.child_epcs), 4)
            task_name = context.context[ContextKeys.CREATED_TASK_NAME_KEY.value]
            execute_queued_task(task_name=task_name)
            task = Task.objects.get(name=task_name)
            self.assertEqual(task.status, 'FINISHED')
            print(
                context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value])

    def test_gs1ushc_shipping(self):
        self._create_good_ouput_criterion()
        db_rule = self._create_rule()
        self._create_parsing_step(
            db_rule
        )
        db_task = self._create_task(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        self._parse_test_data('data/commissioning.xml')
        self._parse_test_data('data/aggregation.xml')
        data_path = os.path.join(curpath, 'data/gs1ushc_ship.xml')
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
        events = EPCISDBProxy().get_object_events_by_epcs([
            'urn:epc:id:sgtin:0555553.000101.241082086825'
        ])
        for event in events:
            if event.biz_step == 'urn:epcglobal:cbv:bizstep:shipping':
                print(event.render())


class TestOptelCompactV2Rule(TestCase):

    def setUp(self):
        super().setUp()
        self._create_masterdata()

    def _create_rule(self):
        return Rule.objects.create(
            name='Parse Optel EPCIS',
            description='unittest'
        )

    def _create_parsing_step(self, rule):
        return Step.objects.create(
            name='Parse CompactV2 EPCIS',
            description='Parse Optel CompactV2 EPCIS',
            step_class='quartet_integrations.optel.steps.OptelCompactV2ParsingStep',
            rule=rule,
            order=1,
        )

    def _create_parsing_step_params(self, step):
        StepParameter.objects.create(
            name='EPCIS Output Criteria',
            value='Unit Test Criteria',
            step=step
        )
        StepParameter.objects.create(
            name='Collect Trade Items Data',
            value=True,
            step=step
        )
        StepParameter.objects.create(
            name='EA Extension Digit',
            value='0',
            step=step
        )

    def _create_output_criteria(self):
        return EPCISOutputCriteria.objects.create(
            name='Unit Test Criteria'
        )

    def _create_task(self, rule):
        return Task.objects.create(
            rule=rule,
            name='unittest task'
        )

    def _create_masterdata(self):
        company = Company.objects.create(
            GLN13='0359883000000',
            SGLN='urn:epc:id:sgln:0359883.00000.0',
            name='Unit Test Company',
            gs1_company_prefix='0359883'
        )
        TradeItem.objects.create(
            GTIN14='00359883100063',
            regulated_product_name='Unit Test Item 1',
            company=company
        )
        TradeItem.objects.create(
            GTIN14='30359883100064',
            regulated_product_name='Unit Test Item 2',
            company=company
        )

    def test_optel_compactv2_step(self):
        # Set up the rule, step and a task
        rule = self._create_rule()
        step = self._create_parsing_step(rule)
        self._create_parsing_step_params(step)
        db_task = self._create_task(rule)
        # Get EPCIS xml path
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/optel-compactv2-epcis.xml')
        # Run the task with the test data
        context = []
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
        event = Event.objects.filter(type='ob').first()
        ilmds = event.instancelotmasterdata_set.all()
        self.assertEquals(len(ilmds), 2)
        self.assertEquals(str(ilmds[0]), 'lotNumber: 19AR095')
        self.assertEquals(str(ilmds[1]), 'itemExpirationDate: 2021-09-30')
        # 2x GTINS + 1x SSCC
        self.assertEquals(len(context.context['TRADE_ITEMS_MASTERDATA']), 3)


class TestCreateShippingEventStep(TestCase):

    def setUp(self):
        super().setUp()
        # Create Essential Masterdata
        self._create_companies_masterdata()
        self._create_trade_items_masterdata()
        self._create_location_masterdata()
        # Create Outbound Mapping
        self._create_outbound_mapping()

    def _create_companies_masterdata(self):
        self.company = Company.objects.create(
            GLN13='0359883000000',
            SGLN='urn:epc:id:sgln:0359883.00000.0',
            name='Unit Test Company',
            gs1_company_prefix='0359883'
        )
        self.company_2 = Company.objects.create(
            GLN13='0311111000000',
            SGLN='urn:epc:id:sgln:0311111.00000.0',
            name='Unit Test Company 2',
            gs1_company_prefix='0311111'
        )

    def _create_location_masterdata(self):
        self.location = Location.objects.create(
            GLN13='0359883000000',
            SGLN='urn:epc:id:sgln:0359883.00000.0',
            name='Unit Test Company',
            company=self.company
        )
        self.location_2 = Location.objects.create(
            GLN13='0311111000000',
            SGLN='urn:epc:id:sgln:0311111.00000.0',
            name='Unit Test Company 2',
            company=self.company_2
        )

    def _create_trade_items_masterdata(self):
        item = TradeItem.objects.create(
            GTIN14='00359883100063',
            regulated_product_name='Unit Test Item 1',
            company=self.company
        )
        TradeItemField.objects.create(
            name=item.GTIN14,
            value=self.company.name,
            trade_item=item
        )
        TradeItem.objects.create(
            GTIN14='30359883100064',
            regulated_product_name='Unit Test Item 2',
            company=self.company
        )

    def _create_outbound_mapping(self):
        self.mapping = OutboundMapping.objects.create(
            company=self.company,
            from_business=self.company,
            to_business=self.company_2,
            ship_from=self.location,
            ship_to=self.location_2
        )

    def _create_rule(self):
        return Rule.objects.create(
            name='Parse Optel EPCIS',
            description='unittest'
        )

    def _create_parsing_step(self, rule):
        return Step.objects.create(
            name='Parse CompactV2 EPCIS',
            description='Parse Optel CompactV2 EPCIS',
            step_class='quartet_integrations.optel.steps.OptelCompactV2ParsingStep',
            rule=rule,
            order=1,
        )

    def _create_parsing_step_params(self, step):
        StepParameter.objects.create(
            name='EPCIS Output Criteria',
            value='Unit Test Criteria',
            step=step
        )
        StepParameter.objects.create(
            name='Collect Trade Items Data',
            value=True,
            step=step
        )
        StepParameter.objects.create(
            name='EA Extension Digit',
            value='0',
            step=step
        )

    def _create_output_criteria(self):
        return EPCISOutputCriteria.objects.create(
            name='Unit Test Criteria'
        )

    def _create_task(self, rule):
        return Task.objects.create(
            rule=rule,
            name='unittest task'
        )

    def _create_shipping_step(self, rule):
        step = Step.objects.create(
            name='Create Shipping Event',
            rule=rule,
            description='unittest',
            step_class='quartet_integrations.optel.steps.CreateShippingEventStep',
            order=2
        )
        StepParameter.objects.create(
            step=step,
            name='Template Name',
            value='quartet_tracelink/disposition_assigned.xml'
        )

    def test_create_shipping_event(self):
        # Set up the rule, step and a task
        rule = self._create_rule()
        step = self._create_parsing_step(rule)
        self._create_parsing_step_params(step)
        self._create_shipping_step(rule)
        db_task = self._create_task(rule)
        # Get EPCIS xml path
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/optel-compactv2-epcis.xml')
        # Run the task with the test data
        context = []
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
        # Get values from context
        shipping_events = context.context[ContextKeys.FILTERED_EVENTS_KEY.value]
        mapping = context.context.get(OptelContextKeys.OUTBOUND_MAPPING.value, None)
        ssccs = context.context.get(OptelContextKeys.FILTERED_SSCCS.value)
        # Check if they are the same as in mapping
        self.assertEquals(len(shipping_events), 1)
        self.assertIsNotNone(mapping)
        self.assertEquals(
            shipping_events[0].source_list[0].source,
            self.mapping.from_business.SGLN)
        self.assertEquals(
            shipping_events[0].source_list[1].source,
            self.mapping.ship_from.SGLN)
        self.assertEquals(
            shipping_events[0].destination_list[0].destination,
            self.mapping.to_business.SGLN)
        self.assertEquals(
            shipping_events[0].destination_list[1].destination,
            self.mapping.ship_to.SGLN)
        self.assertEquals(len(shipping_events[0].epc_list), 1)
        self.assertEquals(shipping_events[0].epc_list, ssccs)
    
    def _create_filtered_event_parsing_step(self, rule, order=3):
        step = Step.objects.create(
            name='Parse Filtered Events',
            rule=rule,
            description='unittest',
            step_class='quartet_integrations.generic.steps.FilteredEventsParsingStep',
            order=order
        )
        return step

    def test_saving_created_shipping_event(self):
        # Set up the rule, step and a task
        rule = self._create_rule()
        step = self._create_parsing_step(rule)
        self._create_parsing_step_params(step)
        self._create_shipping_step(rule)
        self._create_filtered_event_parsing_step(rule)
        db_task = self._create_task(rule)
        # Get EPCIS xml path
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/optel-compactv2-epcis.xml')
        # Run the task with the test data
        context = []
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
        # Get values from context
        ssccs = context.context.get(OptelContextKeys.FILTERED_SSCCS.value)
        # Check if they are the same as in mapping
        # get shipping event from db
        
        proxy = EPCISDBProxy()
        db_events = proxy.get_events_by_epc(ssccs[0])
        shipment = db_events[-1]
        self.assertEquals(len(db_events), 3)
        self.assertEquals(shipment.biz_step, BusinessSteps.shipping.value)
