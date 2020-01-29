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
# Copyright 2019 SerialLab Corp.  All rights reserved.
from list_based_flavorpack.models import ListBasedRegion, ProcessingParameters
from quartet_capture.models import Rule, Step, StepParameter, RuleParameter
from quartet_integrations.oracle.parsing import MasterMaterialParser
from quartet_output.models import EndPoint, AuthenticationInfo
from quartet_templates.models import Template
from serialbox.models import Pool
from quartet_masterdata.models import TradeItem



class TracelinkMMParser(MasterMaterialParser):

    def __init__(self, company_records: dict):
        super().__init__(company_records)

    def create_vendor_range(self, trade_item: TradeItem, material_number
                            ) -> None:
        # create a list based number range
        self._create_list_based_pool(trade_item)

    def _create_list_based_pool(self,
                                trade_item: TradeItem,
                                endpoint: EndPoint,
                                template: Template,
                                response_rule: Rule,
                                authentication_info: AuthenticationInfo,
                                sending_system_gln: str,
                                receiving_system_gln: str
                                ) -> None:
        """
        Creates a list based pool for use in the system.
        :param trade_item: The TradeItem to use for creating the pool.
        :return: None
        """
        request_rule = self._verify_request_rule()
        pool = Pool.objects.create(
            readable_name=trade_item.regulated_product_name,
            machine_name=trade_item.GTIN14,
            request_threshold=50000
        )
        region = ListBasedRegion(
            readable_name=trade_item.regulated_product_name,
            machine_name=trade_item.GTIN14,
            active=True,
            order=1,
            number_replenishment_size=5000,
            processing_class_path='list_based_flavorpack.processing_classes.third_party_processing.processing.DBProcessingClass',
            end_point=endpoint,
            rule=request_rule,
            authentication_info=authentication_info,
            template=template,
            pool=pool
        )
        region.save()
        params = {
            'randomized_number': 'X',
            'object_key_value': trade_item.GTIN14,
            'object_key_name': 'GTIN',
            'encoding_type': 'SGTIN',
            'id_type': 'GS1_SER',
            'receiving_system': receiving_system_gln,
            'sending_system': sending_system_gln
        }
        self._create_processing_parameters(params, region)

    def _create_processing_parameters(self, input: dict, region):
        for k, v in input.items():
            try:
                ProcessingParameters.objects.get(key=k,
                                                 list_based_region=region)
            except ProcessingParameters.DoesNotExist:
                ProcessingParameters.objects.create(key=k,
                                                    value=v,
                                                    list_based_region=region)

    def _create_response_rule(self):
        pass

    def _verify_request_rule(self):
        """
        Makes sure the Tracelink Number Request rule exists, will throw an
        exception if the rule does not exist...
        :return: None
        """
        return Rule.objects.get(name='Tracelink Number Request')

