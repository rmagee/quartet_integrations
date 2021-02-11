from serialbox.api.views import AllocateView
from quartet_integrations.systech.guardian.views import GuardianNumberRangeView
from lxml import etree

from logging import getLogger
from quartet_capture import views as capture_views
from quartet_capture.models import TaskParameter
from serialbox.api.views import AllocateView
from io import BytesIO

logger = getLogger(__name__)


class UniTraceNumberRangeView(GuardianNumberRangeView):

    def check_object_key(self, object_key: etree.Element) -> tuple:
        """
        Iterates through the children of an ObjectKey element to ascertain
        whether or not there is a GTIN, SSCC or COMPANY_PREFIX identifier 
        present.
        :param element: The element to check
        :return: Will return the GTIN or SSCC if found, otherwise none.
        """
        name = None
        value = None
        for child in object_key:
            if child.text and (
                'GTIN' in child.text
                or 'SSCC' in child.text
                or 'GCP' in child.text
                or 'COMPANY_PREFIX' in child.text
            ):
                logger.debug('Found GTIN, GCP, SSCC or COMPANY_PREFIX '
                             'object key...getting the machine name.')
                name = child.text
            elif name and 'Value' in child.tag:
                logger.debug('Getting the value...')
                value = child.text
        return name, value


# class UniTraceNumberRangeView(AllocateView):

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.type = None
#         self.machine_name = None
#         self.sending_system = None
#         self.id_type = None
#         self.encoding_type = None

#     def post(self, request):
#         request_data = etree.iterparse(
#             BytesIO(request.body),
#             events=('end',),
#             remove_comments=True)

#         count = None
#         for event, element in request_data:
#             if 'Size' in element.tag:
#                 count = element.text
#                 logger.debug(f'size = {count}.')
#             elif 'IDType' in element.tag:
#                 # This does not to be included?
#                 self.id_type = element.text
#                 logger.debug('IDType found.')
#             elif 'SendingSystem' in element.tag:
#                 self.sending_system = element.text
#                 logger.debug('Name Found')
#             if 'ObjectKey' in element.tag:
#                 logger.debug('object key found')
#                 self.type, self.machine_name = self.check_object_key(element)
#             elif 'EncodingType' in element.tag:
#                 self.encoding_type = element.text

#         ret = super().get(request, self.machine_name, count)
#         return ret
#
    # def check_object_key(self, object_key: etree.Element) -> tuple:
    #     """
    #     Iterates through the children of an ObjectKey element to ascertain
    #     whether or not there is a GTIN, SSCC or COMPANY_PREFIX identifier 
    #     present.
    #     :param element: The element to check
    #     :return: Will return the GTIN or SSCC if found, otherwise none.
    #     """
    #     name = None
    #     value = None
    #     for child in object_key:
    #         if child.text and (
    #             'GTIN' in child.text
    #             or 'SSCC' in child.text
    #             or 'GCP' in child.text
    #             or 'COMPANY_PREFIX' in child.text
    #         ):
    #             logger.debug('Found GTIN, GCP, SSCC or COMPANY_PREFIX '
    #                          'object key...getting the machine name.')
    #             name = child.text
    #         elif name and 'Value' in child.tag:
    #             logger.debug('Getting the value...')
    #             value = child.text
    #     return name, value
#
#     def _set_task_parameters(self, pool, region, response_rule, size, request):
#         """
#         Override the _set_task_parameters so that we can pass in the
#         additional systech parameters for the rule.
#         """
#         db_task = super()._set_task_parameters(pool, region, response_rule, size,
#                                                request)
#         TaskParameter.objects.create(
#             task=db_task,
#             name='type',
#             value=self.type
#         )
#         TaskParameter.objects.create(
#             task=db_task,
#             name='machine_name',
#             value=self.machine_name
#         )
#         TaskParameter.objects.create(
#             task=db_task,
#             name='sending_system',
#             value=self.sending_system
#         )
#         TaskParameter.objects.create(
#             task=db_task,
#             name='id_type',
#             value=self.id_type
#         )
#         TaskParameter.objects.create(
#             task=db_task,
#             name='encoding_type',
#             value=self.encoding_type
#         )
#         return db_task