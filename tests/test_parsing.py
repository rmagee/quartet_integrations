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
from django.test import TestCase
from quartet_output.steps import ContextKeys
from quartet_capture.models import Rule, Step, Task
from quartet_capture.tasks import execute_rule
from EPCPyYes.core.v1_2 import template_events as yes_events
from quartet_integrations.sap.parsing import SAPParser

class TestParser(SAPParser):

    def handle_object_event(self, epcis_event: yes_events.ObjectEvent):
        print(epcis_event.render())
        return super().handle_object_event(epcis_event)


class TestEparsecis(TestCase):
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        #logging.basicConfig(level=logging.DEBUG)

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_epcis_file(self):
        curpath = os.path.dirname(__file__)
        parser = TestParser(
            os.path.join(curpath, 'data/sap-epcis.xml'))
        parser.parse()


class TestRule(TestCase):
    def test_sap_step(self):
        rule = self._create_rule()
        self._create_sap_step(rule)
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/sap-epcis.xml')
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
        step.name = 'Parse SAP EPCIS'
        step.step_class = 'quartet_integrations.sap.steps.SAPParsingStep'
        step.description = 'sap unit test parsing step'
        step.save()


    def _create_task(self, rule):
        task = Task()
        task.rule = rule
        task.name = 'unit test task'
        task.save()
        return task
