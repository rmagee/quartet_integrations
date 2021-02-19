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
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

from quartet_capture.models import Rule, Step, StepParameter
from quartet_templates.models import Template
from random_flavorpack.models import RandomizedRegion
from serialbox.management.commands.load_serialbox_auth import \
    Command as load_auth
from serialbox.models import Pool, ResponseRule, SequentialRegion

logger = getLogger(__name__)
from django.utils.translation import gettext as _
from django.contrib.auth.models import Group, Permission, ContentType
from serialbox import models



class TraceLinkSNXTestCase(APITestCase):
    def setUp(self):
        user = User.objects.create_user(username='testuser',
                                        password='unittest',
                                        email='testuser@seriallab.local')
        self.create_random_pool()
        self.create_sequential_pool()
        load_auth().handle()
        group = Group.objects.get(name='Pool API Access')
        user.groups.add(group)
        user.save()
        self.client.force_authenticate(user=user)
        self.create_template()
        self.rule = self.create_rule()
        self.create_permissions()
        self.create_response_rule()
        self.create_random_template()
        self.create_random_sscc_template()
        self.create_sequential_sscc_template()
        self.random_sscc_rule = self.create_random_sscc_rule()
        self.sequential_sscc_rule = self.create_sequential_sscc_rule()
        self.random_rule = self.create_random_rule()
        self.create_random_response_rule()
        self.create_sscc_pool()
        self.create_random_sscc_pool()

    def create_permissions(self, *args, **options):
        ct = ContentType.objects.get_for_model(models.Pool)
        pool_allocate, created = Permission.objects.get_or_create(
            codename='allocate_numbers',
            content_type=ct
        )
        if created:
            pool_allocate.name='Can allocate numbers'
            pool_allocate.save()

        group = Group.objects.get_or_create(
            name='Pool API Access'
        )[0]
        allocate_group = Group.objects.get_or_create(
            name='Allocate Numbers Access'
        )[0]
        self._add_permission(allocate_group, pool_allocate)
        self._add_permission(group,
           pool_allocate
        )
        self._add_permission(group,
            Permission.objects.get(codename='add_pool')
        )
        self._add_permission(group,
            Permission.objects.get(codename='change_pool')
        )
        self._add_permission(group,
            Permission.objects.get(codename='delete_pool')
        )
        self._add_permission(group,
            Permission.objects.get(codename='add_sequentialregion')
        )
        self._add_permission(group,
            Permission.objects.get(codename='change_sequentialregion')
        )
        self._add_permission(group,
            Permission.objects.get(codename='delete_sequentialregion')
        )
        for perm in group.permissions.all():
            print(perm.name)

    def _add_permission(self, group: Group, permission: Permission):
        group.permissions.add(permission)


    def create_sequential_pool(self):
        sp1 = models.Pool.objects.create(
            readable_name=_('Logositol 100mg Cartons'),
            machine_name='00377700000136',
            active=True,
            request_threshold=1000
        )
        models.SequentialRegion.objects.create(
            readable_name=_('Logositol 100mg Cartons'),
            machine_name='00377700000136',
            order=1,
            start=1,
            end=9999999999,
            pool=sp1
        )

    def create_random_pool(self):
        # this creates teh pool api access group
        sp1 = Pool.objects.create(
            readable_name=_('Pharmaprod 20mcg Pills'),
            machine_name='00313000007772',
            active=True,
            request_threshold=1000
        )
        RandomizedRegion.objects.create(
            readable_name=_('Pharmaprod 20mcg Pills'),
            machine_name='00313000007772',
            start=239380,
            active=True,
            order=1,
            pool=sp1,
            min=1,
            max=999999999999
        )

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
            rule=self.sequential_sscc_rule,
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
            rule=self.random_sscc_rule,
            pool=pool,
            content_type='xml'
        )

    def create_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 'data/tracelink/SN_Response_SGTIN_Range.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            Template.objects.create(
                name='TraceLink Sequential Response',
                content=content,
                description='The tracelink response template'
            )


    def create_random_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 'data/tracelink/SN_Response_SGTIN_Random.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            Template.objects.create(
                name='TraceLink Random Response',
                content=content,
                description='The tracelink random response template'
            )

    def create_random_sscc_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 'data/tracelink/SN_Response_SSCC_Random.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            Template.objects.create(
                name='TraceLink Random SSCC Response',
                content=content,
                description='The tracelink random response template'
            )

    def create_sequential_sscc_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 'data/tracelink/SN_Response_SSCC_Range.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            Template.objects.create(
                name='TraceLink Sequential SSCC Response',
                content=content,
                description='The tracelink random response template'
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
            name='TraceLink Sequential Number Reply',
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
            value='TraceLink Sequential Response',
            step=template_step
        )
        return rule

    def create_random_rule(self):
        rule = Rule.objects.create(
            name='TraceLink Random Number Reply',
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
            value='TraceLink Random Response',
            step=template_step
        )
        return rule

    def create_sequential_sscc_rule(self):
        rule = Rule.objects.create(
            name='TraceLink Sequential SSCC Number Reply',
            description='unit test'
        )
        Step.objects.create(
            name="Convert to SSCC 18",
            rule=rule,
            step_class='quartet_integrations.serialbox.'
                       'steps.ListToBarcodeConversionStep',
            description='Converts raw serialbox numbers to SSCC-18 values',
            order=1
        )
        template_step = Step.objects.create(
            name='Format With Template',
            rule=rule,
            step_class='quartet_templates.steps.TemplateStep',
            description='unit test step',
            order=2
        )
        StepParameter.objects.create(
            name='Template Name',
            value='TraceLink Sequential SSCC Response',
            step=template_step
        )
        return rule

    def create_random_sscc_rule(self):
        rule = Rule.objects.create(
            name='TraceLink Random SSCC Number Reply',
            description='unit test'
        )
        Step.objects.create(
            name="Convert to SSCC 18",
            rule=rule,
            step_class='quartet_integrations.serialbox.'
                       'steps.ListToBarcodeConversionStep',
            description='Converts raw serialbox numbers to SSCC-18 values',
            order=1
        )
        template_step = Step.objects.create(
            name='Format With Template',
            rule=rule,
            step_class='quartet_templates.steps.TemplateStep',
            description='unit test step',
            order=2
        )
        StepParameter.objects.create(
            name='Template Name',
            value='TraceLink Random SSCC Response',
            step=template_step
        )
        return rule

    def test_post_gtin_request(self):
        """
        Posts an GTIN request to the system using the Tracelink format.

        """
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/tracelink/SN_Request_SGTIN_Range.xml'
        )
        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('tracelinkSNX')
            url = '%s?format=xml' % url
            result = self.client.post(url, request,
                                      content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)

    def test_post_random_gtin_request(self):
        """
        Posts an GTIN request to the system using the Tracelink format.

        """
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/tracelink/SN_Request_SGTIN_Random.xml'
        )
        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('tracelinkSNX')
            url = '%s?format=xml' % url
            result = self.client.post(url, request,
                                      content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)

    def test_post_sequential_sscc_request(self):
        """
        Posts an GTIN request to the system using the Tracelink format.

        """
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/tracelink/SN_Request_SSCC_Range.xml'
        )
        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('tracelinkSNX')
            url = '%s?format=xml' % url
            result = self.client.post(url, request,
                                      content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)

    def test_post_random_sscc_request(self):
        """
        Posts an GTIN request to the system using the Tracelink format.

        """
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/tracelink/SN_Request_SSCC_Random.xml'
        )
        with open(file_path, 'r') as f:
            request = f.read()
            url = reverse('tracelinkSNX')
            url = '%s?format=xml' % url
            result = self.client.post(url, request,
                                      content_type='application/xml')
            print(result.data)
            self.assertEqual(result.status_code, 200)
