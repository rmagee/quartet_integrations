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

import sys
from django.conf import settings
from django.test import TransactionTestCase

from serialbox.models import Pool
from quartet_capture.models import Rule, Step, StepParameter
from quartet_capture.tasks import create_and_queue_task
from quartet_integrations.management.commands import utils
from quartet_integrations.management.commands.utils import \
    create_external_GTIN_response_rule
from quartet_masterdata import models
from quartet_output.models import EndPoint, AuthenticationInfo
from quartet_tracelink.utils import TraceLinkHelper


class TestMasterMaterialImport(TransactionTestCase):
    """
    The master material import
    """

    def setUp(self) -> None:
        self.create_companies()
        self.create_NR_rule()
        self.create_company_rule()
        self.create_rule()
        utils.create_random_range()
        utils.create_gtin_response_rule()
        TraceLinkHelper().create_rule()

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
        ai_id = self.create_authentication()
        rule = Rule.objects.create(
            name='Unit Test NR Rule',
            description='Unit test rule..'
        )
        step = Step.objects.create(
            name='Import Spreadsheet Data',
            description='Unit test step',
            step_class='quartet_integrations.tracelink.steps.ExternalTradeItemNumberRangeImportStep',
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

        StepParameter.objects.create(
            name='Endpoint',
            value='Tracelink',
            step=step
        )

        StepParameter.objects.create(
            name='Authentication Info ID',
            value=str(ai_id),
            step=step
        )
        StepParameter.objects.create(
            name='Sending System GLN',
            value='0123456789012',
            step=step
        )
        response_rule_name = self.create_response_rule()
        TraceLinkHelper().create_template()
        StepParameter.objects.create(
            name='Response Rule Name',
            value=response_rule_name,
            step=step
        )
        return rule

    def create_endpoint(self):
        EndPoint.objects.create(
            name='Tracelink',
            urn=getattr(settings, 'TEST_SERVER', 'http://testhost')
        )

    def create_authentication(self):
        ai = AuthenticationInfo.objects.create(
            username='Tracelink',
            password='Password',
            type='unit test example',
            description='unit test example'
        )
        return ai.id

    def create_company_rule(self):
        rule = Rule.objects.create(
            name='Tracelink Partner Import',
            description='Unit test rule.'
        )
        step1 = Step.objects.create(
            name='Parse Partner Data',
            description='parse the tracelink data',
            step_class='quartet_integrations.tracelink.steps.TraceLinkPartnerParsingStep',
            rule=rule,
            order=1
        )

    def create_response_rule(self):
        rule, created = create_external_GTIN_response_rule()
        return rule.name

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

    def test_load_partners(self):
        if sys.version_info[1] > 5:
            curpath = os.path.dirname(__file__)
            file_path = os.path.join(curpath, 'data/tracelink-partners.csv')
            with open(file_path, "rb") as f:
                create_and_queue_task(
                    data=f.read(),
                    rule_name='Tracelink Partner Import',
                    run_immediately=True
                )
            self.assertEqual(models.Company.objects.all().count(), 15)

    def test_execute_task_with_NR(self):
        if sys.version_info[1] > 5:
            self.create_endpoint()
            curpath = os.path.dirname(__file__)
            file_path = os.path.join(curpath, 'data/master_out.csv')

            with open(file_path, "rb") as f:
                create_and_queue_task(
                    data=f.read(),
                    rule_name="Unit Test NR Rule",
                    run_immediately=True
                )

            self.assertEqual(Pool.objects.all().count(),163)

