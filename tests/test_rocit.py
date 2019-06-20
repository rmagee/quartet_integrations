import os, io
import django
from rest_framework.test import APITestCase
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from quartet_epcis.parsing.business_parser import BusinessEPCISParser
from quartet_epcis.db_api.queries import EPCISDBProxy

os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.settings'
django.setup()


class TestRocIt(APITestCase):
    def setUp(self):
        user = User.objects.create_user(username='testuser',
                                        password='unittest',
                                        email='testuser@seriallab.local')

        self.client.force_authenticate(user=user)
        self.user = user

        dir = os.path.dirname(os.path.abspath(__file__))
        file_name = "rocit-test-data-epcis.xml"
        path = os.path.join(os.path.join(dir, "data"), file_name)
        # parse EPCIS Data
        with open(path, "rb") as epcis_doc:
            epcis_bytes = io.BytesIO(epcis_doc.read())
            parser = BusinessEPCISParser(stream=epcis_bytes)
            parser.parse()

    def test_empty_request(self):
        '''
        Test for an Empty Request. Server should return 500
        :return:
        '''
        url = reverse("retrievePackagingHierarchyResponse")
        response = self.client.post(url)
        self.assertEquals(response.status_code, 500)

    def test_missing_tagId(self):
        url = reverse("retrievePackagingHierarchyResponse")
        data = self._get_test_data('rocit-search-missing-tagid.xml')
        response = self.client.post(url, data, content_type='application/xml')
        self.assertEquals(response.status_code, 500)

    def test_rocit_query(self):
        '''
        Posting SOAP Request Content
        :return:
        '''
        url = reverse("retrievePackagingHierarchyResponse")
        data = self._get_test_data('rocit-search-request.xml')
        response = self.client.post(url, data, content_type='application/xml')
        self.assertEquals(response.status_code, 200)

    def test_rocit_gtin_query(self):
        '''
        Posting SOAP Request Content
        :return:
        '''
        url = reverse("retrievePackagingHierarchyResponse")
        data = self._get_test_data('rocit-gtin-request.xml')
        response = self.client.post(url, data, content_type='application/xml')
        self.assertEquals(response.status_code, 200)

    def _get_test_data(self, file_name):
        '''
        Loads the XML file and passes its data back as a string.
        '''
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/{0}'.format(file_name))
        with open(data_path) as data_file:
            return data_file.read()
