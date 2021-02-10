import os
from logging import getLogger

from rest_framework.test import APITestCase
from django.contrib.auth.models import Group, User
from django.urls import reverse

from quartet_capture.models import Rule, Step, StepParameter
from quartet_templates.models import Template
from serialbox.management.commands.load_test_pools import Command as test_pools
from serialbox.management.commands.load_serialbox_auth import Command as load_auth
from serialbox.models import Pool, ResponseRule, SequentialRegion

from quartet_integrations.systech.unitrace.views import UniTraceNumberRangeView

logger = getLogger(__name__)


class UniTraceTestCase(APITestCase):
    # TODO: Change to only sequential region
    #       with data in range/list format
    def setUp(self):
        # create user
        user = User.objects.create_user(username='testuser',
                                        password='unittest',
                                        email='testuser@serallab.local')
        # run commands
        # load test_sequential_pools
        test_pools().handle()
        self.load_more_pools()
        # load pool auth groups and permissions
        load_auth().handle()
        # get group and add access to the user
        group = Group.objects.get(name='Pool API Access')
        user.groups.add(group)
        user.save()
        # authenticate user
        self.client.force_authenticate(user=user)
        self.create_range_template()
        self.rule = self.create_range_rule()
        self.create_range_response_rule()
        self.create_list_template()
        self.list_rule = self.create_list_rule()
        self.create_list_response_rule()
        self.create_range_sscc_pool()
        self.create_list_sscc_pool()

    def load_more_pools(self):
        sp = Pool.objects.create(
            readable_name='Logositol 100mg Cartons v2',
            machine_name='00313000007772',
            active=True,
            request_threshold=1000
        )
        SequentialRegion.objects.create(
            readable_name='Logositol 100mg Cartons v2',
            machine_name='00313000007772',
            order=1,
            start=1,
            end=9999999999,
            pool=sp
        )

    def create_range_sscc_pool(self):
        pool = Pool.objects.create(
            machine_name='00355555',
            readable_name='Unit test sscc range'
        )
        region = SequentialRegion.objects.create(
            machine_name=pool.machine_name,
            readable_name=pool.readable_name,
            start=1,
            end=999999999,
            order=1,
            state=1,
            pool=pool
        )
        ResponseRule.objects.create(
            rule=self.rule,
            pool=pool,
            content_type='xml'
        )

    def create_list_sscc_pool(self):
        pool = Pool.objects.create(
            machine_name='10355555',
            readable_name='Unit test sscc list'
        )
        region = SequentialRegion.objects.create(
            machine_name=pool.machine_name,
            readable_name=pool.readable_name,
            start=1,
            end=999999999,
            order=1,
            state=1,
            pool=pool
        )
        ResponseRule.objects.create(
            rule=self.rule,
            pool=pool,
            content_type='xml'
        )

    def create_range_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(
            curpath,
            'data/unitrace/range_response_template.xml'
        )
        with open(data_path, 'r') as f:
            content = f.read()
            Template.objects.create(
                name='UniTrace Range Response',
                content=content,
                description='The UniTech response template'
            )

    def create_list_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(
            curpath,
            'data/unitrace/list_response_template.xml'
        )
        with open(data_path, 'r') as f:
            content = f.read()
            Template.objects.create(
                name='UniTrace List Response',
                content=content,
                description='The UniTech response template'
            )

    def create_range_response_rule(self):
        pool = Pool.objects.get(
            machine_name='00377700000136'
        )
        ResponseRule.objects.create(
            pool=pool,
            rule=self.rule,
            content_type='xml'
        )

    def create_list_response_rule(self):
        pool = Pool.objects.get(
            machine_name='00313000007772'
        )
        ResponseRule.objects.create(
            pool=pool,
            rule=self.list_rule,
            content_type='xml'
        )

    def create_range_rule(self):
        rule = Rule.objects.create(
            name='UniTrace Range Number Reply',
            description='unit test'
        )
        template_step = Step.objects.create(
            name='Format with template',
            rule=rule,
            step_class='quartet_templates.steps.TemplateStep',
            description='unit test step',
            order=1
        )
        StepParameter.objects.create(
            name='Template Name',
            value='UniTrace Range Response',
            step=template_step
        )
        return rule

    def create_list_rule(self):
        rule = Rule.objects.create(
            name='UniTrace List Number Reply',
            description='unit test'
        )
        template_step = Step.objects.create(
            name='Format with template',
            rule=rule,
            step_class='quartet_templates.steps.TemplateStep',
            description='unit test step',
            order=1
        )
        StepParameter.objects.create(
            name='Template Name',
            value='UniTrace List Response',
            step=template_step
        )
        return rule

    def test_post_range_gtin_request(self):
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/unitrace/range_gtin_request.xml'
        )

        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('unitraceNumberRangeService')
            url = '%s?format=xml' % url
            result = self.client.post(url, request,
                            content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)

    def test_post_list_gtin_request(self):
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/unitrace/range_gtin_request.xml'
        )

        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('unitraceNumberRangeService')
            url = '%s?format=xml' % url
            result = self.client.post(url, request,
                            content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)

    def test_post_range_sscc_request(self):
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/unitrace/range_sscc_request.xml'
        )

        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('unitraceNumberRangeService')
            url = '%s?format=xml' % url
            result = self.client.post(url, request,
                            content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)

    def test_post_list_sscc_request(self):
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/unitrace/list_sscc_request.xml'
        )

        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('unitraceNumberRangeService')
            url = '%s?format=xml' % url
            result = self.client.post(url, request,
                            content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)
