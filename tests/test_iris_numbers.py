import os
import django
from django.test import TestCase
from django.contrib.auth.models import User
from django.test.client import RequestFactory
from list_based_flavorpack.processing_classes import get_region_db_number_count
from quartet_templates.models import Template
from list_based_flavorpack.models import ListBasedRegion, ProcessingParameters
from quartet_output.models import EndPoint, AuthenticationInfo
from quartet_capture.models import Rule, Step
from serialbox import models
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
        self.user = User.objects.create(
            username='test',
            password='test',
            is_superuser=True
        )

    def test_send_request(self):
        # Don't run this test
        pass
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
        test_pool.request_threshold = 200
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
        step2 = Step()
        step2.name = "Save Response"
        step2.description = "Saves List of Serial Numbers"
        step2.step_class = "quartet_integrations.frequentz.steps.IRISNumberRequestProcessStep"
        step2.order = 2
        step2.rule = rule
        step2.save()


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
        ProcessingParameters.objects.create(
            list_based_region=list_based_region,
            key='format',
            value='SGTIN-96'
        )
        return list_based_region

    def generate_end_point(self):

        return None

    def generate_authinfo(self):

        return None

    def generate_allocation(self, size, test_pool):
        generator = get_generator(test_pool.machine_name)
        request_factory = RequestFactory()
        request = request_factory.get("allocate/00351991817017/" + str(size))
        response = generator.get_response(request, size,
                                           test_pool.machine_name)

        #serializer = serializers.ResponseSerializer(response)

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