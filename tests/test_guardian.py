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
from random_flavorpack.management.commands.load_random_flavorpack_auth import \
    Command
from serialbox.management.commands.load_test_pools import Command as test_pools
from serialbox.models import Pool, ResponseRule
logger = getLogger(__name__)


class GuardianTestCase(APITestCase):
    def setUp(self):
        user = User.objects.create_user(username='testuser',
                                        password='unittest',
                                        email='testuser@seriallab.local')
        # this creates teh pool api access group
        Command().handle()
        test_pools().handle()
        group = Group.objects.get(name='Pool API Access')
        user.groups.add(group)
        user.save()
        self.client.force_authenticate(user=user)
        self.create_template()
        self.rule = self.create_rule()
        self.create_response_rule()

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

    def create_response_rule(self):
        pool = Pool.objects.get(
            machine_name='00377700000136'
        )
        ResponseRule.objects.create(
            pool=pool,
            rule=self.rule,
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
