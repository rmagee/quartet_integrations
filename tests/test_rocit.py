import os, io
import django
import xml.etree.ElementTree as ET
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from django.urls import reverse
from quartet_epcis.parsing.business_parser import BusinessEPCISParser
from quartet_masterdata.models import TradeItem, TradeItemField, Company, Location

os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.settings'
django.setup()


class TestRocIt(APITestCase):
    def setUp(self):
        user = User.objects.create_user(username='testuser',
                                        password='unittest',
                                        email='testuser@seriallab.local')

        self.client.force_authenticate(user=user)
        self.user = user

        company = Company.objects.create(
            name="Test Co"
        )

        trade_item = TradeItem.objects.create(
            GTIN14="33055555555558",
            additional_id="063915",
            company=company
        )
        tif = TradeItemField.objects.create(
            trade_item=trade_item,
            name="uom",
            value='Bx'
        )

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
        self.assertEquals(response.status_code, 400)

    def test_missing_tagId(self):
        url = reverse("retrievePackagingHierarchyResponse")
        data = self._get_test_data('rocit-search-missing-tagid.xml')
        response = self.client.post(url, data, content_type='application/xml')
        self.assertEquals(response.status_code, 400)

    def test_rocit_container1_query(self):
        '''
        Posting SOAP Request Content
        :return:
        '''
        url = reverse("retrievePackagingHierarchyResponse")
        data = self._get_test_data('rocit-search-container1-request.xml')
        response = self.client.post(url, data, content_type='application/xml')
        self.assertEquals(response.status_code, 200)

        root = ET.fromstring(response.data)
        for body in root.findall('{http://schemas.xmlsoap.org/soap/envelope/}Body'):
            for resp in body.findall(
                '{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/applicationModule/common/types/}retrievePackagingHierarchyResponse'):
                for result in resp.findall(
                    '{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/applicationModule/common/types/}result'):
                    sgtin = result.find(
                        '{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}TagId').text
                    self.assertEquals(sgtin, 'urn:epc:id:sgtin:305555.3555555.1')
                    childCount = result.find(
                        '{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}ChildTagCount').text
                    self.assertEquals(childCount, '5')
                    r = result.findall(
                        '{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}ChildTagsVO')
                    self.assertTrue(len(r) == int(childCount))

    def test_rocit_container2_query(self):
        '''
        Posting SOAP Request Content
        :return:
        '''
        url = reverse("retrievePackagingHierarchyResponse")
        data = self._get_test_data('rocit-search-container2-request.xml')
        response = self.client.post(url, data, content_type='application/xml')
        self.assertEquals(response.status_code, 200)

        root = ET.fromstring(response.data)
        for body in root.findall('{http://schemas.xmlsoap.org/soap/envelope/}Body'):
            for resp in body.findall(
                '{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/applicationModule/common/types/}retrievePackagingHierarchyResponse'):
                for result in resp.findall(
                    '{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/applicationModule/common/types/}result'):
                    sgtin = result.find(
                        '{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}TagId').text
                    self.assertEquals(sgtin, 'urn:epc:id:sgtin:305555.3555555.6')
                    status = result.find(
                        '{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}Status').text
                    #self.assertEquals(status, "CONTAINER_CLOSED")
                    state = result.find(
                        '{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}State').text
                    #self.assertEquals(state, 'PACKING')
                    childCount = result.find(
                        '{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}ChildTagCount').text
                    self.assertEquals(childCount, '5')
                    r = result.findall(
                        '{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}ChildTagsVO')
                    self.assertTrue(len(r) == int(childCount))


    # def test_rocit_sscc_query(self):
    #     '''
    #     Posting SOAP Request Content
    #     :return:
    #     '''
    #     url = reverse("retrievePackagingHierarchyResponse")
    #     data = self._get_test_data('rocit-search-sscc-request.xml')
    #     response = self.client.post(url, data, content_type='application/xml')
    #     self.assertEquals(response.status_code, 200)
    #
    #     root = ET.fromstring(response.data)
    #     for body in root.findall('{http://schemas.xmlsoap.org/soap/envelope/}Body'):
    #         for resp in body.findall('{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/applicationModule/common/types/}retrievePackagingHierarchyResponse'):
    #             for result in resp.findall('{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/applicationModule/common/types/}result'):
    #                 sscc = result.find('{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}TagId').text
    #                 self.assertEquals(sscc, "urn:epc:id:sscc:305555.0000000001")
    #                 status = result.find('{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}Status').text
    #                 self.assertEquals(status, "IN_TRANSIT")
    #                 state = result.find('{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}State').text
    #                 self.assertEquals(state,'SHIPPING')
    #                 childCount = result.find('{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}ChildTagCount').text
    #                 self.assertEquals(childCount, '2')
    #                 r = result.findall('{http://xmlns.oracle.com/oracle/apps/pas/serials/serialsService/view/common/}ChildTagsVO')
    #                 self.assertTrue(len(r)==int(childCount))



    def _get_test_data(self, file_name):
        '''
        Loads the XML file and passes its data back as a string.
        '''
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/{0}'.format(file_name))
        with open(data_path) as data_file:
            return data_file.read()
