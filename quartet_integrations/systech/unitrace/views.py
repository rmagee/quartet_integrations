from logging import getLogger

from lxml import etree

from quartet_integrations.systech.guardian.views import GuardianNumberRangeView

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
