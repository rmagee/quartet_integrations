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

import csv

import logging
from io import StringIO
from django.db.utils import IntegrityError
from django.db import transaction

from list_based_flavorpack.models import ListBasedRegion, ProcessingParameters
from quartet_capture.models import Rule
from quartet_integrations.management.commands import utils
from quartet_masterdata.models import TradeItem
from quartet_masterdata.models import TradeItemField, Company
from quartet_masterdata.db import DBProxy
from quartet_output.models import EndPoint, AuthenticationInfo
from quartet_templates.models import Template
from random_flavorpack.models import RandomizedRegion
from serialbox.models import Pool
from serialbox.models import ResponseRule


logger = logging.getLogger(__name__)


class MasterMaterialParser:
    """
    Imports master material exports from oracle into the quartet trade
    items.
    """

    def __init__(self, company_records: dict):
        self.company_records = company_records
        self.info_func = None

    def parse(self, data, info_func, minimum: int = 0, maximum: int = 0,
              threshold: int = 0, response_rule_name: str = None,
              create_randomized_range=False
              ) -> None:
        self.minimum = minimum
        self.maximum = maximum
        self.threshold = threshold
        self.response_rule_name = response_rule_name
        self.create_randomized_range = create_randomized_range
        file_stream = StringIO(data.decode('utf-8'))
        self.info_func = info_func

        parsed_data = csv.DictReader(file_stream)
        for data in parsed_data:
            row = list(data.values())
            self.create_trade_item(row[0], row[1], row[2], pallet_pack=row[9],
                                   name=row[10]
                                   )
            self.create_trade_item(row[0], row[3], row[4], row[5],
                                   pallet_pack=row[9], name=row[10])
            if row[6]:
                self.create_trade_item(row[0], row[6], row[7],
                                       pack_count=row[8],
                                       pallet_pack=row[9], name=row[10])

    def create_trade_item(self, material_number, unit_of_measure, gtin14,
                          pack_count=None, pallet_pack=None, name=None):
        company = self.get_company(gtin14)
        if company == None:
            print('Company not found for record %s %s %s %s %s' % (
                name,
                gtin14,
                material_number,
                unit_of_measure,
                pack_count))
            self.info_func('Company not found for gtin %s- NOT CREATING'
                           ' TRADE ITEM.', gtin14)
        else:
            trade_item = TradeItem.objects.get_or_create(
                company=company,
                additional_id=material_number,
                package_uom=unit_of_measure,
                GTIN14=gtin14,
                pack_count=pack_count,
                regulated_product_name=name
            )[0]
            TradeItemField.objects.get_or_create(
                trade_item=trade_item,
                name='pallet_pack_count',
                value=pallet_pack
            )
            if self.create_randomized_range:
                self.create_random_pool(trade_item, material_number)

    def create_random_pool(self, trade_item: TradeItem, material_number
                           ) -> None:
        """
        Will create a randomized range for the inbound material record.
        :param minimum: The minimum number
        :param maximum: The maximum number to serialize to.
        :param threshold: The max atomic request size.
        :param response_rule_name: The response rule for response processing.
        :return: None
        """
        try:
            rule = Rule.objects.get(name=self.response_rule_name)
            readable_name = "%s (%s) | %s" % (
                trade_item.regulated_product_name, trade_item.package_uom,
                material_number
            )
            pool = Pool.objects.get_or_create(readable_name=readable_name,
                                              machine_name=trade_item.GTIN14,
                                              active=True,
                                              request_threshold=self.threshold
                                              )[0]
            ResponseRule.objects.get_or_create(pool=pool, rule=rule,
                                               content_type='xml')
            RandomizedRegion.objects.get_or_create(
                machine_name=trade_item.GTIN14,
                readable_name=trade_item.GTIN14,
                min=self.minimum,
                max=self.maximum,
                start=self.minimum,
                order=1,
                active=True,
                pool=pool
            )
        except Rule.DoesNotExist:
            # noinspection PyCallByClass
            raise Rule.DoesNotExist('The rule with name %s could not be found'
                                    '.  Either create a response rule and/or '
                                    'run the create_opsm_gtin_range '
                                    'management command.' %
                                    self.response_rule_name)

    def get_company(self, gtin: str):
        """
        Looks for the company prefix in the GTIN and returns the company
        database model if that is found.
        :param gtin: The gtin to inspect
        :return: A quartet_masterdata.models.Company instance.
        """
        for company, db_company in self.company_records.items():
            if company in gtin: return db_company

    def create_vendor_range(self, trade_item: TradeItem, material_number
                            ) -> None:
        raise NotImplementedError('The create vendor range is not implemented '
                                  'for this class.')


class TracelinkMMParser:

    def __init__(self, company_records: dict):
        self.company_records = company_records
        self.info_func = None

    def parse(self, data: bytes, info_func: object, threshold: int,
              response_rule_name: str, endpoint: str,
              authentication_info: str, sending_system_gln: str
              ):
        self.threshold = threshold
        self.sending_system_gln = sending_system_gln
        self.response_rule_name = response_rule_name
        file_stream = StringIO(data.decode('utf-8'))
        self.info_func = info_func
        self.endpoint = endpoint
        self.authentication_info = authentication_info

        parsed_data = csv.DictReader(file_stream)
        for datarow in parsed_data:
            row = list(datarow.values())
            if row[12] == 'TraceLink':
                company = self.create_company(row)
                self.create_trade_item(row[0], row[1], row[2],
                                       pallet_pack=row[9],
                                       name=row[10],
                                       l4=row[12],
                                       GLN=row[13],
                                       SGLN=row[14],
                                       company_prefix=[15],
                                       company=company
                                       )
                self.create_trade_item(row[0], row[3], row[4], row[5],
                                       pallet_pack=row[9], name=row[10],
                                       l4=row[12],
                                       GLN=row[13],
                                       SGLN=row[14],
                                       company_prefix=[15],
                                        company = company
                                       )
                if row[6]:
                    self.create_trade_item(row[0], row[6], row[7],
                                           pack_count=row[8],
                                           pallet_pack=row[9], name=row[10],
                                           l4=row[12],
                                           GLN=row[13],
                                           SGLN=row[14],
                                           company_prefix=[15],
                                           company=company
                                           )

    def create_trade_item(self, material_number, unit_of_measure, gtin14,
                          pack_count=None, pallet_pack=None, name=None,
                          l4=None, GLN=None, SGLN=None, company_prefix=None,
                          company: Company=None
                          ):
        """

        :type company: Company
        """
        if company == None:
            print('Company not found for record %s %s %s %s %s' % (
                name,
                gtin14,
                material_number,
                unit_of_measure,
                pack_count))
            self.info_func('Company not found for gtin %s- NOT CREATING'
                           ' TRADE ITEM.', gtin14)
        else:
            with transaction.atomic():
                trade_item = TradeItem.objects.get_or_create(
                    company=company,
                    additional_id=material_number,
                    package_uom=unit_of_measure,
                    GTIN14=gtin14,
                    pack_count=pack_count,
                    regulated_product_name=name
                )[0]
                TradeItemField.objects.get_or_create(
                    trade_item=trade_item,
                    name='pallet_pack_count',
                    value=pallet_pack
                )
                self.create_vendor_range(trade_item, material_number, company)

    def create_vendor_range(self, trade_item: TradeItem, material_number,
                            company: Company
                            ) -> None:
        # create a list based number range
        self._create_list_based_pool(trade_item, material_number, company)

    def create_company(self, row):
        """
        Creates a company record to use when creating pools.
        :param row: The row from the import data with customer name
        and company prefix.
        :return: None.
        """
        try:
            company = Company.objects.create(
                name=row[11],
                gs1_company_prefix=[15],
                GLN13=row[13]
            )
            if row[14] is not None and row[14] != '':
                company.SGLN = 'urn:epc:id:sgln:%s' % row[14]
            self.company_records[row[13]] = company
        except IntegrityError:
            print('Company %s has already been created.' % row[13])
            company = Company.objects.get(GLN13=row[13])
        return company

    def _create_list_based_pool(self,
                                trade_item: TradeItem,
                                material_number,
                                company: Company
                                ) -> None:
        """
        Creates a list based pool for use in the system.
        :param trade_item: The TradeItem to use for creating the pool.
        :return: None
        """
        response_rule = self._get_response_rule()
        request_rule = self._verify_request_rule()
        db_endpoint = self._get_endpoint(self.endpoint)
        db_authentication_info = self._get_authentication_info_by_id(
            self.authentication_info)
        template = Template.objects.get(name='OPSM GTIN Response Template')
        try:
            pool = Pool.objects.create(
                readable_name='%s | %s' % (trade_item.regulated_product_name, material_number),
                machine_name=trade_item.GTIN14,
                request_threshold=self.threshold
            )
            region = ListBasedRegion(
                readable_name=pool.readable_name,
                machine_name=trade_item.GTIN14,
                active=True,
                order=1,
                number_replenishment_size=5000,
                processing_class_path='list_based_flavorpack.processing_classes.third_party_processing.processing.DBProcessingClass',
                end_point=db_endpoint,
                rule=request_rule,
                authentication_info=db_authentication_info,
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
                'receiving_system': company.GLN13,
                'sending_system': self.sending_system_gln
            }
            self._create_processing_parameters(params, region)
        except IntegrityError:
            print('Duplicate number range %s | %s being skipped' %
                  (trade_item.regulated_product_name, material_number))

    def _create_processing_parameters(self, input: dict, region):
        for k, v in input.items():
            try:
                ProcessingParameters.objects.get(key=k,
                                                 list_based_region=region)
            except ProcessingParameters.DoesNotExist:
                ProcessingParameters.objects.create(key=k,
                                                    value=v,
                                                    list_based_region=region)

    def _verify_request_rule(self):
        """
        Makes sure the Tracelink Number Request rule exists, will throw an
        exception if the rule does not exist...
        :return: None
        """
        return Rule.objects.get(name='Tracelink Number Request')

    def _get_response_rule(self):
        """
        Makes sure the response rule exists.  If not, creates it using the
        utils module in the management command package.
        :return: None
        """
        ret = None
        try:
            ret = Rule.objects.get(
                name="OPSM External GTIN Response Rule"
            )
        except Rule.DoesNotExist:
            # create the rule
            rule, created = utils.create_external_GTIN_response_rule()
            ret = rule
        return ret

    def _get_endpoint(self, endpoint):
        self.info_func('Looking for endpoint %s', endpoint)
        return EndPoint.objects.get(name=endpoint)

    def _get_authentication_info_by_id(self, authentication_info: str):
        self.info_func('Looking for auth info with id %s', authentication_info)
        return AuthenticationInfo.objects.get(id=int(authentication_info))

    def get_company(self, gtin: str):
        """
        Looks for the company prefix in the GTIN and returns the company
        database model if that is found.
        :param gtin: The gtin to inspect
        :return: A quartet_masterdata.models.Company instance.
        """
        for company, db_company in self.company_records.items():
            if company in gtin: return db_company
