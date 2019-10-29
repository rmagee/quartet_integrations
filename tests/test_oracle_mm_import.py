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

from EPCPyYes.core.v1_2 import template_events as yes_events
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from quartet_capture.models import Rule, Step, Task, StepParameter
from quartet_capture.tasks import execute_rule, create_and_queue_task
from quartet_capture.rules import RuleContext
from quartet_epcis.models import events
from quartet_epcis.parsing.business_parser import BusinessEPCISParser
from quartet_integrations.sap.parsing import SAPParser
from quartet_masterdata import models
from quartet_output.models import EPCISOutputCriteria, EndPoint
from quartet_output.steps import ContextKeys
from quartet_masterdata.models import Company, Location
from quartet_integrations.oracle.parsing import MasterMaterialParser



class TestMasterMaterialImport(TestCase):
    """
    The master material import
    """
    def setUp(self) -> None:
        self.create_companies()

    def create_rule(self):
        rule = Rule.objects.create(
            name='Unit Test Rule',
            description='Unit test rule..'
        )
        step = Step.objects.create(
            name='Import Spreadsheet Data',
            description='Unit test step',
            step_class='quartet_integrations.oracle.steps.TradeItemImportStep',
            rule=rule,
            order=1
        )
        StepParameter.objects.create(
            name='Company Prefix 1',
            value='0377777',
            step=step
        )
        StepParameter.objects.create(
            name='Company Prefix 2',
            value='0347771',
            step=step
        )
        return rule

    def create_companies(self):
        """
        creates the example company records
        :return: None
        """
        models.Company.objects.create(
            gs1_company_prefix='0347771'
        )
        models.Company.objects.create(
            gs1_company_prefix='0377777'
        )

    def test_execute_task(self):
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(curpath, 'data/oracle_mm_export.csv')
        with open(file_path, "rb") as f:
            rule = self.create_rule()
            create_and_queue_task(
                data=f.read(),
                rule_name='Unit Test Rule',
                run_immediately=True
            )

