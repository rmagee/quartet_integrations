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

from django.contrib.auth.models import User, Permission, Group
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from quartet_masterdata.models import Company
from quartet_integrations.management.commands import utils
from serialbox.management.commands.load_serialbox_auth import Command
from serialbox.models import Pool, ResponseRule
from serialbox.models import SequentialRegion

MACHINE_NAME='503130000000000000'

class TestURNConversion(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        user = User.objects.create_user(username='testuser',
                                        password='unittest',
                                        email='testuser@seriallab.local')
        Command().handle()
        group = Group.objects.get(name='Pool API Access')
        user.groups.add(group)
        user.save()
        self.client.force_authenticate(user=user)
        self.user = user

    def create_sscc_pool(self, rule):
        pool = Pool.objects.create(
            machine_name=MACHINE_NAME,
            readable_name='Unit Test SSCC'
        )
        ResponseRule.objects.create(
            pool=pool,
            rule=rule,
            content_type='xml'
        )
        SequentialRegion.objects.create(
            pool=pool,
            start=1,
            end=999999999,
            machine_name=MACHINE_NAME,
            readable_name='Unit Test SSCC'
        )


    def allocate_numbers(self, machine_name, count, format):
        '''
        Ensure we can get numbers from the pool
        '''
        url = reverse('allocate-numbers', args=[machine_name, count])
        url = '%s%s' % (url, '?format=xml')
        response = self.client.get(url, format=format, content_type='application/xml')
        print(response.content or response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sscc(self):
        self.create_company('031300')
        print('creating test rule')
        rule = utils.create_serialbox_gtin_response_rule()
        print('creating test pool')
        self.create_sscc_pool(rule=rule)
        self.allocate_numbers(MACHINE_NAME, '10', 'xml')

    def create_company(self, company_prefix):
        Company.objects.create(
            gs1_company_prefix=company_prefix,
            name='Unit Test Co'
        )


