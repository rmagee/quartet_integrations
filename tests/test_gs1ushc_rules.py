#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_quartet_output
------------

Tests for `quartet_output` models module.
"""
import os
from django.conf import settings
from django.test import TestCase

from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.events import EventType
from quartet_capture.models import Rule, Step, StepParameter, Task
from quartet_capture.tasks import execute_rule
from quartet_epcis.parsing.business_parser import BusinessEPCISParser
from quartet_output import models
from quartet_output.models import EPCISOutputCriteria
from quartet_output.steps import SimpleOutputParser, ContextKeys
from quartet_masterdata.models import Company, Location

class TestGS1USHC(TestCase):

    def setUp(self) -> None:
        self.create_companies()

    def create_companies(self):
        Company.objects.create(
            name='CMO Corp',
            address1='Testing street',
            city='Testerville',
            state_province='AL',
            postal_code='13777',
            country='US',
            SGLN='urn:epc:id:sgln:07777770000.0.0',
            GLN13='7777777777777',
            gs1_company_prefix='777777'
        )
        Company.objects.create(
            name='Virtual Corp',
            address1='Imaginary street',
            city='Virtuality',
            state_province='NJ',
            postal_code='77700',
            country='US',
            gs1_company_prefix='305555',
            GLN13='3055550000000',
            SGLN='urn:epc:id:sgln:3055555.0.0'
        )
        Location.objects.create(
            name='C3PO',
            address1='Android Lane',
            city='Protocol Droid',
            state_province='TX',
            postal_code='70707',
            country='US',
            GLN13='0842671116709',
            SGLN='urn:epc:id:sgln:0842671116.0.0',
        )


    def test_rule_with_agg_comm(self):
        self._create_good_ouput_criterion()
        db_rule = self._create_rule()
        self._create_step(db_rule)
        self._create_output_steps(db_rule)
        self._create_comm_step(db_rule)
        self._create_epcpyyes_step(db_rule)
        db_task = self._create_task(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        self._parse_test_data('data/commission_one_event.xml')
        self._parse_test_data('data/nested_pack.xml')
        data_path = os.path.join(curpath, 'data/ship_pallet.xml')
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
            self.assertEqual(
                len(context.context[ContextKeys.AGGREGATION_EVENTS_KEY.value]),
                3,
                "There should be three filtered events."
            )
            for event in context.context[
                ContextKeys.AGGREGATION_EVENTS_KEY.value]:
                if event.parent_id in ['urn:epc:id:sgtin:305555.3555555.1',
                                       'urn:epc:id:sgtin:305555.3555555.2']:
                    self.assertEqual(len(event.child_epcs), 5)
                else:
                    self.assertEqual(len(event.child_epcs), 2)
            self.assertIsNotNone(
                context.context.get(
                    ContextKeys.EPCIS_OUTPUT_CRITERIA_KEY.value)
            )

    def _create_good_ouput_criterion(self):
        endpoint = self._create_endpoint()
        auth = self._create_auth()
        eoc = EPCISOutputCriteria()
        eoc.name = "Test Criteria"
        eoc.action = "OBSERVE"
        eoc.event_type = EventType.Object.value
        eoc.disposition = Disposition.in_transit.value
        eoc.biz_step = BusinessSteps.shipping.value
        eoc.authentication_info = auth
        eoc.end_point = endpoint
        eoc.save()
        return eoc

    def _create_good_agg_trigger_ouput_criterion(self):
        endpoint = self._create_endpoint()
        auth = self._create_auth()
        eoc = EPCISOutputCriteria()
        eoc.name = "Test Criteria"
        eoc.action = "ADD"
        eoc.biz_step = BusinessSteps.packing.value
        eoc.biz_location = 'urn:epc:id:sgln:0555555.00002.0'
        eoc.sender_identifier = 'urn:epc:id:sgln:0555555.00001.0'
        eoc.end_point = endpoint
        eoc.save()
        return eoc

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

    def _parse_data(self, output_criteria):
        curpath = os.path.dirname(__file__)
        parser = SimpleOutputParser(
            os.path.join(curpath, 'data/epcis.xml'),
            output_criteria
        )
        parser.parse()
        parser.clear_cache()

    def _create_delay_rule(self):
        rule = Rule()
        rule.name = 'delay-rule'
        rule.description = 'a simple delay rule'
        rule.save()
        self.create_delay_step(rule)
        return rule

    def create_delay_step(self, rule, order=1):
        step = Step()
        step.step_class = 'quartet_output.steps.DelayStep'
        step.order = order
        step.name = 'wait 3 seconds'
        step.rule = rule
        step.save()
        param = StepParameter()
        param.step = step
        param.name = 'Timeout Interval'
        param.value = '3'
        param.save()

    def _create_rule(self):
        rule = Rule()
        rule.name = 'output-test'
        rule.description = 'output test rule'
        rule.save()
        return rule

    def _create_filtered_output_step(self, rule, order=1):
        step = Step()
        step.step_class = 'quartet_integration.gs1ushc.steps.OutputParsingStep'
        step.order = order
        step.name = 'filtered output step'
        step.rule = rule
        step.save()

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

    def _create_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 1
        step.name = 'Output Determination'
        step.step_class = 'quartet_integrations.gs1ushc.steps.OutputParsingStep'
        step.description = 'unit test step'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'EPCIS Output Criteria'
        step_parameter.value = 'Test Criteria'
        step_parameter.save()
        return step

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
        step.step_class = 'quartet_output.steps.AddCommissioningDataStep'
        step.description = 'unit test commissioning step'
        step.save()

    def _create_epcpyyes_step(self, rule, json=False):
        step = Step()
        step.rule = rule
        step.order = 4
        step.name = 'Create EPCIS'
        step.step_class = 'quartet_integrations.gs1ushc.steps.EPCPyYesOutputStep'
        step.description = 'Creates EPCIS XML or JSON and inserts into rule' \
                           'context.'
        step.save()
        if json:
            param = StepParameter.objects.create(
                step=step,
                name='JSON',
                value=True
            )

    def _create_task(self, rule):
        task = Task()
        task.rule = rule
        task.name = 'unit test task'
        task.save()
        return task

    def _add_forward_data_step_parameter(self, step: Step):
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'Forward Data'
        step_parameter.value = 'True'
        step_parameter.description = 'Whether or not to construct new data ' \
                                     'or to just forward the data in the ' \
                                     'rule.'
        step_parameter.save()

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

    def tearDown(self):
        pass


