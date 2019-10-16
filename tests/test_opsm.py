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
from quartet_integrations.management.commands import utils


class OPSMTestCase(APITestCase):
    def setUp(self):
        utils.create_random_range()
        utils.create_gtin_response_rule()
        utils.create_trade_item()
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

    def test_post_sscc_request(self):
        """
        Posts an SSCC request to the system using the OPSM format.

        """
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(curpath, 'data/opsm_sscc_request.xml')
        utils.create_sequential_sscc_range()
        utils.create_sscc_template()
        utils.create_SSCC_response_rule()
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
