from rest_framework.test import APITestCase
from django.urls import reverse

class OPSMTestCase(APITestCase):

    def test_post_sscc_request(self):
        request = """<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:typ="http://xmlns.oracle.com/apps/pas/transactions/transactionsService/applicationModule/common/types/" xmlns:com="http://xmlns.oracle.com/apps/pas/transactions/transactionsService/view/common/">
           <soapenv:Header/>
           <soapenv:Body>
              <typ:createProcessSerialGenerationRequest>
                 <typ:serialGenerationRequest>
                    <!--Optional:-->
                    <com:SerialQuantity>1</com:SerialQuantity>
                    <!--Optional:-->
                    <com:Location>03422910000-SSCC</com:Location>
                    <!--Optional:-->
                    <com:Gtin></com:Gtin>
                 </typ:serialGenerationRequest>
              </typ:createProcessSerialGenerationRequest>
           </soapenv:Body>
        </soapenv:Envelope>"""

        url = reverse('numberRangeService')

        self.client.post(url, request, content_type='application/xml')

    def test_post_gtin_request(self):
        request = """<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:typ="http://xmlns.oracle.com/apps/pas/transactions/transactionsService/applicationModule/common/types/" xmlns:com="http://xmlns.oracle.com/apps/pas/transactions/transactionsService/view/common/">
           <soapenv:Header/>
           <soapenv:Body>
              <typ:createProcessSerialGenerationRequest>
                 <typ:serialGenerationRequest>
                    <!--Optional:-->
                    <com:SerialQuantity>1</com:SerialQuantity>
                    <!--Optional:-->
                    <com:Location>03422910000-GTIN</com:Location>
                    <!--Optional:-->
                    <com:Gtin>00342291527102</com:Gtin>
                 </typ:serialGenerationRequest>
              </typ:createProcessSerialGenerationRequest>
           </soapenv:Body>
        </soapenv:Envelope>
        """
        url = reverse('numberRangeService')
        self.client.post(url, request, content_type='application/xml')
