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
from quartet_masterdata import models
from quartet_templates import models as templates
from quartet_output.models import EndPoint, AuthenticationInfo
from list_based_flavorpack.models import ListBasedRegion
from quartet_tracelink.utils import TraceLinkHelper


class TestMasterMaterialImport(TransactionTestCase):
    """
    The master material import
    """

    def setUp(self) -> None:
        self.create_company()
        self.create_template()
        self.create_endpoint()
        self.create_authentication()
        self.create_tradeitem_import_rule()

    def create_endpoint(self):
        EndPoint.objects.create(
            name='PharmaSecure Serial Numbers',
            urn='http://175.101.5.247:2214/PSService.svc?wsdl'
        )

    def create_authentication(self):
        return

    def create_template(self):

        content= '<?xml version="1.0" encoding="utf-8"?> \
                            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/" xmlns:psid="http://schemas.datacontract.org/2004/07/psIDCodeMaker"> \
                                <soapenv:Header/> \
                                <soapenv:Body> \
                                    <tem:Generate> \
                                        <tem:req> \
                                            <psid:RequestID>{{ request_id }}</psid:RequestID> \
                                            <psid:EncodingType>{{ encoding_type }}</psid:EncodingType> \
                                            <psid:Size>{{ quantity }}</psid:Size> \
                                            <psid:ObjectName>{{ object_name }}</psid:ObjectName> \
                                            <psid:ObjectValue>{{ object_value }}</psid:ObjectValue> \
                                        </tem:req> \
                                    </tem:Generate> \
                                </soapenv:Body> \
                            </soapenv:Envelope>'


        templates.Template.objects.create(
            name="PharmaSecure Serial Number Template",
            content=content,
            description='Template for PharmaSecure Serial Number Requests'
        )

    def create_company(self):
        models.Company.objects.create(
            name='First Time US Generics-GPI',
            GLN13='0370010000001',
            gs1_company_prefix='0370010'
        )

    def create_tradeitem_import_rule(self):

        rule = Rule.objects.create(
            name='Unit Test FTUG_GPI Trade Item Import Rule',
            description='Unit test rule. Create Trade Item Import Rule'
        )
        step = Step.objects.create(
            name='Import Data',
            description='Unit test step',
            step_class='quartet_integrations.mmd.steps.FirstTimeUSGenericsGPIImportStep',
            rule=rule,
            order=1
        )

        self.create_request_rule()

        response_rule_name = self.create_response_rule()

        StepParameter.objects.create(
            name='Response Rule Name',
            value=response_rule_name,
            step=step
        )

        auth_info = AuthenticationInfo.objects.get(description='PharmaSecure Serial Numbers Authentication')

        StepParameter.objects.create(
            name='Authentication Id',
            value=auth_info.pk,
            step=step
        )

        return rule

    def create_response_rule(self):
        rule, _ = create_external_GTIN_response_rule()
        return rule.name

    def create_request_rule(self):
        """
        Gets or creates the external gtin request rule, if it doesn't exist.
        :return: A tuple with the rule and a boolean 'created'.
        """
        rule, created = Rule.objects.get_or_create(
            name='PharmaSecure Number Request',
            description='Requests GTIN and SSCC Serial Numbers from PharmaSecure'
        )

        if not created: return

        Step.objects.get_or_create(
            rule=rule,
            name='Save Serial Numbers',
            step_class='quartet_integrations.pharmasecure.steps.PharmaSecureNumberRequestProcessStep',
            order=1
        )

    def test_execute_tradeitem_import_rule(self):
        '''
         You can only run this test locally due to security.
         Can't put credentials in source control
        '''
        return

        if sys.version_info[1] > 5:
            curpath = os.path.dirname(__file__)

            file_path = os.path.join(curpath, 'data/first-time-us-generics-gpi.csv')
            with open(file_path, "rb") as f:
                create_and_queue_task(
                    data=f.read(),
                    rule_name='Unit Test FTUG_GPI Trade Item Rule',
                    run_immediately=True
                )

        trade_items = models.TradeItem.objects.all()
        self.assertTrue(len(trade_items) == 63)
        pools = Pool.objects.all()
        self.assertTrue(len(pools) == 63)
        regions = ListBasedRegion.objects.all()
        self.assertTrue(len(regions) == 63)
