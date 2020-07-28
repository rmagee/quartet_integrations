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
import csv
import sys
from django.conf import settings
from django.test import TransactionTestCase

from serialbox.models import Pool
from quartet_capture.models import Rule, Step, StepParameter
from quartet_capture.tasks import create_and_queue_task
from quartet_integrations.management.commands import utils
from quartet_integrations.management.commands.utils import \
    create_external_GTIN_response_rule
from quartet_masterdata import models as masterdata
from quartet_templates import models as templates
from quartet_output import models as output
from quartet_output.models import EndPoint, AuthenticationInfo
from quartet_tracelink.utils import TraceLinkHelper


class TestMasterMaterialImport(TransactionTestCase):
    """
    The master material import
    """

    def setUp(self) -> None:
        self.create_companies()
        self.iris_rule = self.create_iris_import_rule()
        utils.create_gtin_response_rule()

    def create_iris_import_rule(self):

        rule = Rule.objects.create(
            name='Trade Item Import IRIS',
            description='Unit test rule. Creates Number Range for Random Numbers'
        )
        step = Step.objects.create(
            name='Import CSV',
            description='Unit test step',
            step_class='quartet_integrations.mmd.steps.TradeItemImportStep',
            rule=rule,
            order=1
        )

        response_rule_name = self.create_response_rule()

        StepParameter.objects.create(
            name='Response Rule Name',
            value=response_rule_name,
            step=step
        )

        snm_output_criteria = self.create_snm_output_criteria('IRIS')

        StepParameter.objects.create(
            name='SNM Output Criteria',
            value=snm_output_criteria,
            step=step
        )

        StepParameter.objects.create(
            name='Sending System SGLN',
            value='urn:epc:id:sgln:0351991.00000.0',
            step=step
        )

        StepParameter.objects.create(
            name='List Based',
            value=True,
            step=step
        )

        StepParameter.objects.create(
            name='Replenishment Size',
            value=5000,
            step=step
        )

        template_name = self.create_iris_template()

        StepParameter.objects.create(
            name='Request Template Name',
            value=template_name,
            step=step
        )

        StepParameter.objects.create(
            name='Processing Parameters',
            value='[ \
                    {"gtin":"%API_KEY%"}, \
                    {"format":"SGTIN-198"} \
                  ]',
            step=step
        )

        StepParameter.objects.create(
            name='Mock',
            value=True,
            step=step
        )
        return rule


    def create_iris_template(self):
        template, _ = templates.Template.objects.get_or_create(
            name = 'IRIS Template',
            content = "{{gtin}},{{format}}"

        )
        return template.name


    def create_response_rule(self):
        rule, _ = create_external_GTIN_response_rule()
        return rule.name


    def create_snm_output_criteria(self, name):
    # Create a Mockable output criteria
       auth, _ = output.AuthenticationInfo.objects.get_or_create(
            description="{0} Auth".format(name),
            username='test',
            password='password'
       )

       endpoint, _ = output.EndPoint.objects.get_or_create(
            name='{0} Endpoint'.format(name),
            urn='http://localhost'
       )

       output_criteria, _ = output.EPCISOutputCriteria.objects.get_or_create(
           name='{0}  SNM Output'.format(name),
           end_point=endpoint,
           authentication_info=auth
       )

       return output_criteria.name

    def create_companies(self):

        # For IRIS
        masterdata.Company.objects.create(
            name='Test Company A',
            gs1_company_prefix='0351991',
            GLN13='0351991000000'
        )

        # For rfXcel - not IRIS
        masterdata.Company.objects.create(
            name='Test Company B',
            gs1_company_prefix='0342195',
            GLN13='0342195000008'
        )

        # For PharmaSecure
        masterdata.Company.objects.create(
            name='Test Company C',
            gs1_company_prefix='0370010',
            GLN13='0370010000001'
        )

        # For QU4RTET
        masterdata.Company.objects.create(
            name='Test Company D',
            gs1_company_prefix='0352817',
            GLN13='0352817000002'
        )

    def test_execute_import_iris(self):

        if sys.version_info[1] > 5:

            curpath = os.path.dirname(__file__)

            file_path = os.path.join(curpath, 'data/mmd-iris-import.csv')
            with open(file_path, "rb") as f:
                create_and_queue_task(
                data=f.read(),
                rule_name=self.iris_rule.name,
                run_immediately=True
            )



