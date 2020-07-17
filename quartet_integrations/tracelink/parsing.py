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

import logging
from django.db import transaction
from django.db.utils import IntegrityError

from list_based_flavorpack.models import ListBasedRegion, ProcessingParameters

from quartet_capture.models import Rule
from quartet_integrations.management.commands import utils
from quartet_masterdata.models import TradeItem
from quartet_masterdata.models import TradeItemField
from quartet_output.models import EndPoint, AuthenticationInfo
from quartet_templates.models import Template
from serialbox.models import Pool, ResponseRule

logger = logging.getLogger(__name__)
import csv
from io import StringIO
from quartet_masterdata.models import Company


class TraceLinkPartnerParser:
    """
    Parses tracelink partner export spreadsheet data and creates QU4RTET
    company instances.
    """
    def parse(self, data: bytes):
        file_stream = StringIO(data.decode('utf-8'))
        parsed_data = csv.DictReader(file_stream)
        for datarow in parsed_data:
            row = list(datarow.values())
            try:
                city, state, zip, country = self.parse_location(row[5])
                company = Company.objects.create(
                    name=row[3],
                    address1=row[4],
                    city=city,
                    state_province=state,
                    postal_code=zip,
                    country=country
                )
                ids = row[7].split(',')
                for type_id in ids:
                    try:
                        type, id = type_id.strip().split(' ')
                        if type == "GLN":
                            company.GLN13 = id
                        if type == "SGLN":
                            company.SGLN = 'urn:epc:id:sgln:%s' % id
                    except ValueError:
                        print('passing on %s', type_id)
                company.save()
            except:
                raise

    def parse_location(self, location_row):
        unpacked = location_row.split(',')
        city = unpacked[0]
        state_zip_country = unpacked[1].strip().split(' ')
        state = state_zip_country[0]
        country_code = state_zip_country[-1]
        state_zip_country.pop(-1)
        state_zip_country.pop(0)
        zip = ' '.join(state_zip_country)
        return city, state, zip, country_code


class TracelinkMMParser:

    def __init__(self):
        self.company_records = {}
        self.info_func = None

    def parse(self, data: bytes, info_func: object, threshold: int,
              response_rule_name: str, endpoint: str,
              authentication_info: str, sending_system_gln: str,
              replenishment_size: int, secondary_replenishment_size: int
              ):
        self.replenishment_size = int(replenishment_size)
        self.threshold = threshold
        self.sending_system_gln = sending_system_gln
        self.response_rule_name = response_rule_name
        file_stream = StringIO(data.decode('utf-8'))
        self.info_func = info_func
        self.endpoint = endpoint
        self.authentication_info = authentication_info
        self.secondary_replenishment_size = secondary_replenishment_size

        parsed_data = csv.DictReader(file_stream)
        for datarow in parsed_data:
            row = list(datarow.values())
            if row[12].lower() == 'tracelink':
                company = self.create_company(row)
                self.create_trade_item(row[0], row[1], row[2],
                                       pallet_pack=row[9],
                                       name=row[10],
                                       l4=row[12],
                                       GLN=row[13],
                                       SGLN=row[14],
                                       company_prefix=row[15],
                                       company=company,
                                       NDC=row[16]
                                       )
                self.create_trade_item(row[0], row[3], row[4], row[5],
                                       pallet_pack=row[9], name=row[10],
                                       l4=row[12],
                                       GLN=row[13],
                                       SGLN=row[14],
                                       company_prefix=row[15],
                                       company=company,
                                       NDC=row[16]
                                       )
                if row[6]:
                    self.create_trade_item(row[0], row[6], row[7],
                                           pack_count=row[8],
                                           pallet_pack=row[9], name=row[10],
                                           l4=row[12],
                                           GLN=row[13],
                                           SGLN=row[14],
                                           company_prefix=row[15],
                                           company=company,
                                           NDC=row[16]
                                           )

    def create_trade_item(self, material_number, unit_of_measure, gtin14,
                          pack_count=None, pallet_pack=None, name=None,
                          l4=None, GLN=None, SGLN=None, company_prefix=None,
                          company: Company = None, NDC=None
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

        trade_item = self._get_trade_item_model(company, gtin14,
                                                material_number, name,
                                                pack_count,
                                                pallet_pack,
                                                unit_of_measure,
                                                NDC=NDC)

        self.create_vendor_range(trade_item, material_number, company)

    def _get_trade_item_model(self, company, gtin14, material_number, name,
                              pack_count, pallet_pack, unit_of_measure, NDC):
        try:
            trade_item = TradeItem.objects.get(GTIN14=gtin14)
        except TradeItem.DoesNotExist:
            trade_item = TradeItem.objects.create(
                GTIN14=gtin14,
                company=company
            )
        trade_item.NDC = NDC
        trade_item.NDC_pattern = self.get_NDC_pattern(NDC)
        trade_item.additional_id = material_number
        trade_item.package_uom = unit_of_measure
        trade_item.pack_count = pack_count
        trade_item.regulated_product_name = name
        trade_item.company = company
        trade_item.save()
        TradeItemField.objects.get_or_create(
            trade_item=trade_item,
            name='pallet_pack_count',
            value=pallet_pack
        )
        return trade_item

    def get_NDC_pattern(self, NDC: str):
        split_vals = NDC.split('-')
        lens = []
        for val in split_vals:
            lens.append(str(len(val)))
        result = ('-').join(lens)
        return result

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
                gs1_company_prefix=row[15],
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
        replenishment_size = int(
            self.replenishment_size) if trade_item.GTIN14.startswith(
            '0') else self.secondary_replenishment_size
        self._create_response_rule()
        request_rule = self._verify_request_rule()
        db_endpoint = self._get_endpoint(self.endpoint)
        db_authentication_info = self._get_authentication_info_by_id(
            self.authentication_info)
        template = Template.objects.get(name='Tracelink Number Request')
        try:
            pool = Pool.objects.create(
                readable_name='%s | %s | %s' % (
                    trade_item.regulated_product_name, material_number,
                    trade_item.GTIN14),
                machine_name=trade_item.GTIN14,
                request_threshold=self.threshold
            )
            region = ListBasedRegion(
                readable_name=pool.readable_name,
                machine_name=trade_item.GTIN14,
                active=True,
                order=1,
                number_replenishment_size=replenishment_size,
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
            self._get_response_rule(pool)
            self._create_processing_parameters(params, region)
        except IntegrityError:
            print('Duplicate number range %s | %s being skipped' %
                  (trade_item.regulated_product_name, material_number))

    def _get_response_rule(self, pool):
        rule = Rule.objects.get(name=self.response_rule_name)
        ResponseRule.objects.create(
            pool=pool, rule=rule, content_type='xml'
        )

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

    def _create_response_rule(self):
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
