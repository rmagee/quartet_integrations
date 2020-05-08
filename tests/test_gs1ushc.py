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
import os
from django.conf import settings
from django.test import TestCase

from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.events import EventType
from quartet_capture.models import Rule, Step, StepParameter, Task
from quartet_capture.tasks import execute_rule
from quartet_epcis.db_api.queries import EPCISDBProxy
from quartet_epcis.parsing.business_parser import BusinessEPCISParser
from quartet_output import models
from quartet_output.models import EPCISOutputCriteria


class TestGS1USHCParsing(TestCase):
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
        eoc.read_point = 'urn:epc:id:sgln:0857777777.02.1'
        eoc.authentication_info = auth
        eoc.end_point = endpoint
        eoc.save()
        return eoc

    def _create_step(self, rule,
                     step_class='quartet_integrations.gs1ushc.steps.OutputParsingStep'
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
        sp2 = StepParameter()
        sp2.step = step
        sp2.name = 'Create Child Observation'
        sp2.value = 'True'
        sp2.save()
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

    def test_gs1ushc_shipping(self):
        self._create_good_ouput_criterion()
        db_rule = self._create_rule()
        self._create_step(
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
            'urn:epc:id:sgtin:0555553.000101.197566650897'
        ])
        for event in events:
            print(event.render())
