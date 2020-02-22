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
import sys
import os

from django.test import TestCase
from quartet_integrations.management.commands import utils
from quartet_capture.models import Rule, Step, StepParameter
from quartet_capture.tasks import create_and_queue_task
from quartet_masterdata import models


class TestMasterMaterialImport(TestCase):
    """
    The master material import
    """
    def setUp(self) -> None:
        self.create_companies()
        self.create_NR_rule()
        self.create_rule()
        utils.create_random_range()
        utils.create_gtin_response_rule()

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

    def create_NR_rule(self):
        rule = Rule.objects.create(
            name='Unit Test NR Rule',
            description='Unit test rule..'
        )
        step = Step.objects.create(
            name='Import Spreadsheet Data',
            description='Unit test step',
            step_class='quartet_integrations.oracle.steps.TradeItemNumberRangeImportStep',
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
        if sys.version_info[1] > 5:
            curpath = os.path.dirname(__file__)
            file_path = os.path.join(curpath, 'data/oracle_mm_export.csv')
            with open(file_path, "rb") as f:
                create_and_queue_task(
                    data=f.read(),
                    rule_name='Unit Test Rule',
                    run_immediately=True
                )

    def test_execute_task_with_NR(self):
        if sys.version_info[1] > 5:
            curpath = os.path.dirname(__file__)
            file_path = os.path.join(curpath, 'data/oracle_mm_export.csv')

            with open(file_path, "rb") as f:
                create_and_queue_task(
                    data=f.read(),
                    rule_name="Unit Test NR Rule",
                    run_immediately=True
                )
