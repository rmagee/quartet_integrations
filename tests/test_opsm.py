import os

from quartet_capture.models import Rule, StepParameter, Step
from serialbox.models import Pool, ResponseRule
from random_flavorpack import models
from quartet_templates.models import Template
from django.db import transaction
from django.urls import reverse
from rest_framework.test import APITestCase
from random_flavorpack.management.commands.load_random_flavorpack_auth import \
    Command
from serialbox.models import SequentialRegion
from django.contrib.auth.models import User, Permission, Group
from quartet_masterdata.models import TradeItem, Company


class OPSMTestCase(APITestCase):
    def setUp(self):
        self.create_random_range()
        self.create_gtin_response_rule()
        self.create_trade_item()
        user = User.objects.create_user(username='testuser',
                                        password='unittest',
                                        email='testuser@seriallab.local')
        Command().handle()
        for permission in Permission.objects.all():
            print(permission.name, permission.codename)
        group = Group.objects.get(name='Pool API Access')
        user.groups.add(group)
        user.save()
        self.client.force_authenticate(user=user)

    def create_gtin_response_rule(self):
        rule, created = Rule.objects.get_or_create(
            name='OPSM GTIN Response Rule',
            description='OPSM Response Rule (Auto Created)',
        )

        conversion_step, created = Step.objects.get_or_create(
            rule=rule,
            name='List Conversion',
            step_class='quartet_integrations.opsm.steps.ListToUrnConversionStep',
            order=1
        )
        if not created:
            conversion_step.description = 'Convert the list of numbers to ' \
                                          'GTINs or SSCCs for use by OPSM.',

        format_step, created = Step.objects.get_or_create(
            rule=rule,
            name='Format Message',
            description='A message template step.',
            step_class='quartet_templates.steps.TemplateStep',
            order=2
        )
        StepParameter.objects.get_or_create(
            step=format_step,
            name='Template Name',
            value='OPSM GTIN Response Template'
        )

        self.create_template()
        pool = Pool.objects.get(machine_name='00313000007772')
        response_rule = ResponseRule.objects.get_or_create(
            rule=rule,
            pool=pool,
            content_type='xml'
        )

    def create_SSCC_response_rule(self):
        rule, created = Rule.objects.get_or_create(
            name='OPSM SSCC Response Rule',
            description='OPSM SSCC Response Rule (Auto Created)',
        )

        conversion_step, created = Step.objects.get_or_create(
            rule=rule,
            name='List Conversion',
            step_class='quartet_integrations.serialbox.steps.ListToBarcodeConversionStep',
            order=1
        )
        if not created:
            conversion_step.description = 'Convert the list of numbers to ' \
                                          'SSCCs for use by OPSM.',

        cp = StepParameter.objects.create(
            name='Company Prefix',
            value='031300',
            description='Unit test prefix.',
            step=conversion_step
        )

        ed = StepParameter.objects.create(
            name='Indicator Digit',
            value='0',
            description='Unit test indicator',
            step=conversion_step
        )

        format_step, created = Step.objects.get_or_create(
            rule=rule,
            name='Format Message',
            description='A message template step.',
            step_class='quartet_templates.steps.TemplateStep',
            order=2
        )
        StepParameter.objects.get_or_create(
            step=format_step,
            name='Template Name',
            value='OPSM SSCC Response Template'
        )

        self.create_sscc_template()
        pool = Pool.objects.get(machine_name='031300000770000001-SSCC')
        return ResponseRule.objects.get_or_create(
            rule=rule,
            pool=pool,
            content_type='xml'
        )[0]

    def create_trade_item(self):
        company = Company.objects.create(
            name='Pharma Co',
            GLN13='0313000000011',
            SGLN='urn:epc:id:sgln:031300.1.0',
            gs1_company_prefix='031300',
        )
        TradeItem.objects.create(
            company=company,
            GTIN14='00313000007772',
            NDC_pattern='4-4-2',
            NDC='1300-0007-77',
            package_uom='EA'
        )

    def create_template(self):
        print('Creating the OPSM GTIN response template...')
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(curpath,
                                 '../quartet_integrations/templates/opsm/sgtin_response.xml')
        with open(file_path, 'r') as f:
            response_template = Template.objects.get_or_create(
                name='OPSM GTIN Response Template',
                content=f.read()
            )

    def create_sscc_template(self):
        print('Creating the OPSM SSCC response template...')
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(curpath,
                                 '../quartet_integrations/templates/opsm/sscc_response.xml')
        with open(file_path, 'r') as f:
            response_template = Template.objects.get_or_create(
                name='OPSM SSCC Response Template',
                content=f.read()
            )

    def create_random_range(self):
        sp1 = Pool.objects.create(
            readable_name='Pharmaprod 20mcg Pills',
            machine_name='00313000007772',
            active=True,
            request_threshold=1000
        )
        models.RandomizedRegion.objects.create(
            readable_name='Pharmaprod 20mcg Pills',
            machine_name='00313000007772',
            start=239380,
            active=True,
            order=1,
            pool=sp1,
            min=1,
            max=999999999999
        )

    def create_random_sscc_range(self):
        sp1 = Pool.objects.create(
            readable_name='Pharmaprod SSCC',
            machine_name='031300000770000001-SSCC',
            active=True,
            request_threshold=1000
        )
        # 031300 + 00000000000 + 1 = 18
        # the max length of the serial number is 99999999999
        models.RandomizedRegion.objects.create(
            readable_name='Pharmaprod 20mcg Pills',
            machine_name='031300000770000001-SSCC',
            start=239380,
            active=True,
            order=1,
            pool=sp1,
            min=1,
            max=99999999999
        )

    def create_sequential_sscc_range(self):
        sp1 = Pool.objects.create(
            readable_name='Pharmaprod SSCC',
            machine_name='031300000770000001-SSCC',
            active=True,
            request_threshold=1000
        )
        # 031300 + 00000000000 + 1 = 18
        # the max length of the serial number is 99999999999
        SequentialRegion.objects.create(
            readable_name='Pharmaprod 20mcg Pills',
            machine_name='031300000770000001-SSCC',
            start=1,
            active=True,
            order=1,
            pool=sp1,
            state=1,
            end=99999999999
        )

    def test_post_sscc_request(self):
        """
        Posts an SSCC request to the system using the OPSM format.

        """
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(curpath, 'data/opsm_sscc_request.xml')
        self.create_sequential_sscc_range()
        self.create_sscc_template()
        self.create_SSCC_response_rule()
        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('numberRangeService')
            result = self.client.post(url, request,
                                      content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)

    def test_post_gtin_request(self):
        """
        Posts an GTIN request to the system using the OPSM format.

        """
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(curpath, 'data/opsm_gtin_request.xml')
        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('numberRangeService')
            result = self.client.post(url, request,
                                      content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)
