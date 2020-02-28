import os
import django
from django.test import TestCase
from django.test.client import RequestFactory
from list_based_flavorpack.processing_classes import get_region_db_number_count
from quartet_templates.models import Template
from list_based_flavorpack.models import ListBasedRegion
from quartet_output.models import EndPoint, AuthenticationInfo
from quartet_capture.models import Rule, Step, StepParameter
from serialbox import models
from serialbox.api import serializers
from serialbox.discovery import get_generator

os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.settings'
django.setup()


class IRISNumberTest(TestCase):

    def setUp(self):
        self.test_pool = self.generate_test_pool()
        self.rule = self.generate_step_rule()
        self.template = self.generate_template()
        self.list_based_region = self.generate_region(self.test_pool,
                                                      self.rule, self.template)

    def test_send_request(self):
        if os.path.exists(self.list_based_region.db_file_path):
            os.remove(self.list_based_region.db_file_path)
        size = 5
        response = self.generate_allocation(size, self.test_pool)
        # check that there are 195 rows in the table
        row_count = get_region_db_number_count(self.list_based_region)
        self.assertEqual(195, row_count)

    def generate_test_pool(self):
        # create pool
        test_pool = models.Pool()
        test_pool.readable_name = "IRIS Test Pool"
        test_pool.machine_name = "00351991817017"
        test_pool.active = True
        test_pool.request_threshold = 1000
        test_pool.save()
        return test_pool

    def generate_step_rule(self):
        # Create Rule and Step
        rule = Rule()
        rule.name = "IRIS Rule"

        rule.description = "Gets and Saves Serial Numbers"
        rule.save()
        step = Step()
        step.name = "Get Numbers"
        step.description = "Gets Serial Numbers"
        step.step_class = "quartet_integrations.frequentz.steps.IRISNumberRequestTransportStep"
        step.order = 1
        step.rule = rule
        step.save()
        StepParameter.objects.create(
            name='resource_name',
            value='00351991817017',
            step=step
        )
        StepParameter.objects.create(
            name='quantity',
            value='10',
            step=step
        )
        StepParameter.objects.create(
            name='format',
            value='SGTIN-198',
            step=step
        )

        step2 = Step()
        step2.name = "Save Response"
        step2.description = "Saves List of Serial Numbers"
        step2.step_class = "quartet_integrations.frequentz.steps.IRISNumberRequestProcessStep"
        step2.order = 2
        step2.rule = rule
        step2.save()
        StepParameter.objects.create(
            name='Serial Number Path',
            value='".//SerialNo"',
            step=step2
        )

        return rule

    def generate_region(self, test_pool, rule, template):
        # create region with third party processing class.
        list_based_region = ListBasedRegion()
        list_based_region.pool = test_pool
        list_based_region.readable_name = "IRIS Region"
        list_based_region.machine_name = "00351991817017"
        list_based_region.active = True
        list_based_region.order = 1
        list_based_region.rule = rule
        list_based_region.number_replenishment_size = 200
        list_based_region.template = template
        list_based_region.end_point = self.generate_end_point()
        list_based_region.authentication_info = self.generate_authinfo()
        list_based_region.directory_path = "/tmp"
        list_based_region.save()
        return list_based_region

    def generate_end_point(self):

        ret_val = EndPoint.objects.create(
            name="IRIS Endpoint",
            urn="https://qa-breckenridge.frequentz.com:9443/ts/engine/snm/services/TagManagerService"
        )

        return ret_val

    def generate_authinfo(self):

        ret_val = AuthenticationInfo.objects.create(
            username='apace',
            password='Breck2016#',
            type='Basic'
        )
        return ret_val

    def generate_allocation(self, size, test_pool):
        generator = get_generator(test_pool.machine_name)
        request_factory = RequestFactory()
        request = request_factory.get("allocate/00351991817017/" + str(size))
        response = generator.get_response(request, size,
                                          test_pool.machine_name)
        serializer = serializers.ResponseSerializer(response)
        return response

    def generate_template(self):
        content = '''
         <IRIS>
            <gtin>{{ GTIN }}<gtin> 
            <quantity>{{ QUANTITY }}</quantity>
         </IRIS>
        '''
        return Template.objects.create(name="Test IRIS Template", content=content,
                                       description="")