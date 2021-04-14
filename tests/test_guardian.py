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
# Copyright 2020 SerialLab Corp.  All rights reserved.
from logging import getLogger

import os
from django.contrib.auth.models import User, Group
from django.urls import reverse
from rest_framework.test import APITestCase
from quartet_templates.models import Template
from quartet_capture.models import Rule, Step, StepParameter
from random_flavorpack.management.commands.load_test_random_pools import \
    Command
from random_flavorpack.models import RandomizedRegion
from serialbox.management.commands.load_test_pools import Command as test_pools
from serialbox.management.commands.load_serialbox_auth import Command as load_auth
from serialbox.models import Pool, ResponseRule, SequentialRegion
logger = getLogger(__name__)


class GuardianTestCase(APITestCase):
    def setUp(self):
        user = User.objects.create_user(username='testuser',
                                        password='unittest',
                                        email='testuser@seriallab.local')
        # this creates teh pool api access group
        Command().handle()
        test_pools().handle()
        load_auth().handle()
        group = Group.objects.get(name='Pool API Access')
        user.groups.add(group)
        user.save()
        self.client.force_authenticate(user=user)
        self.create_template()
        self.rule = self.create_rule()
        self.create_response_rule()
        self.create_random_template()
        self.random_rule = self.create_random_rule()
        self.create_random_response_rule()
        self.create_sscc_pool()
        self.create_random_sscc_pool()

    def create_sscc_pool(self):
        pool = Pool.objects.create(
            machine_name='00355555',
            readable_name='Unit test ssccc'
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

    def create_random_sscc_pool(self):
        pool = Pool.objects.create(
            machine_name='10355555',
            readable_name='Random Unit test ssccc'
        )
        region = RandomizedRegion.objects.create(
            machine_name=pool.machine_name,
            readable_name=pool.readable_name,
            min=1,
            max=999999999,
            order=1,
            pool=pool
        )
        ResponseRule.objects.create(
            rule=self.random_rule,
            pool=pool,
            content_type='xml'
        )

    def create_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 'data/systech/sequential_response_template.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            Template.objects.create(
                name='Systech Sequential Response',
                content=content,
                description='The systech response template'
            )

    def create_random_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 'data/systech/random_response_template.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            Template.objects.create(
                name='Systech Random Response',
                content=content,
                description='The systech random response template'
            )

    def create_response_rule(self):
        pool = Pool.objects.get(
            machine_name='00377700000136'
        )
        ResponseRule.objects.create(
            pool=pool,
            rule=self.rule,
            content_type='xml'
        )

    def create_random_response_rule(self):
        pool = Pool.objects.get(
            machine_name='00313000007772'
        )
        ResponseRule.objects.create(
            pool=pool,
            rule=self.random_rule,
            content_type='xml'
        )

    def create_rule(self):
        rule = Rule.objects.create(
            name='Systech Sequential Number Reply',
            description='unit test'
        )
        template_step = Step.objects.create(
            name='Format With Template',
            rule=rule,
            step_class='quartet_templates.steps.TemplateStep',
            description='unit test step',
            order=1
        )
        StepParameter.objects.create(
            name='Template Name',
            value='Systech Sequential Response',
            step=template_step
        )
        return rule

    def create_random_rule(self):
        rule = Rule.objects.create(
            name='Systech Random Number Reply',
            description='unit test'
        )
        template_step = Step.objects.create(
            name='Format With Template',
            rule=rule,
            step_class='quartet_templates.steps.TemplateStep',
            description='unit test step',
            order=1
        )
        StepParameter.objects.create(
            name='Template Name',
            value='Systech Random Response',
            step=template_step
        )
        return rule

    def test_post_gtin_request(self):
        """
        Posts an GTIN request to the system using the OPSM format.

        """
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/systech/gtin_sequential_number_request.xml'
        )
        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('guardianNumberRangeService')
            url = '%s?format=xml' % url
            result = self.client.post(url, request,
                                      content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)

    def test_post_random_gtin_request(self):
        """
        Posts an GTIN request to the system using the OPSM format.

        """
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/systech/gtin_random_number_request.xml'
        )
        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('guardianNumberRangeService')
            url = '%s?format=xml' % url
            result = self.client.post(url, request,
                                      content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)

    def test_post_sscc_request(self):
        """
        Posts an GTIN request to the system using the OPSM format.

        """
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/systech/sscc_sequential_number_request.xml'
        )
        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('guardianNumberRangeService')
            url = '%s?format=xml' % url
            result = self.client.post(url, request,
                                      content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)

    def test_post_random_sscc_request(self):
        """
        Posts an GTIN request to the system using the OPSM format.

        """
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/systech/sscc_random_number_request.xml'
        )
        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('guardianNumberRangeService')
            url = '%s?format=xml' % url
            result = self.client.post(url, request,
                                      content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)

    def test_accept_xml_text(self):
        rule = Rule.objects.create(name="EPCIS", description="unit test rule")
        Step.objects.create(
            step_class="quartet_epcis.parsing.steps.EPCISParsingStep",
            order=1,
            name="EPCIS",
            rule=rule
        )

        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/epcis.xml'
        )
        with open(file_path, "r") as f:
            request = f.read()
            url = reverse('guardianCapture')
            url = "%s%s" % (url, "/?rule=EPCIS&run-immediately=true")
            result = self.client.post(url, request,
                                      content_type='text/xml',
                                      Accept='TEXT/XML')
            self.assertEqual(result.data, "OK")
            self.assertEqual(result.status_code, 200)
