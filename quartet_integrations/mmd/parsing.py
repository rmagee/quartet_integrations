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
import sys
from io import StringIO
import logging
from django.db import transaction
from django.db.utils import IntegrityError
from list_based_flavorpack.models import ProcessingParameters

from quartet_capture.models import Rule
from quartet_integrations.management.commands import utils
from quartet_masterdata.models import TradeItem, TradeItemField, Company
from quartet_output.models import EndPoint, AuthenticationInfo
from serialbox.models import Pool, ResponseRule
from random_flavorpack.models import RandomizedRegion

logger = logging.getLogger(__name__)


class PartnerParser:
    """
    Parses provided customer .csv file and creates QU4RTET
    companies.
    """

    def parse(self, data: bytes):
        file_stream = StringIO(data.decode('utf-8'))
        parsed_data = csv.DictReader(file_stream)
        for datarow in parsed_data:
            row = list(datarow.values())
            try:
                city, state, zip, country = self.parse_location(row)

                Company.objects.get_or_create(
                    name=row[1],
                    address1=row[5],
                    city=city,
                    state_province=state,
                    postal_code=zip,
                    country=country,
                    gs1_company_prefix=row[2],
                    GLN13=row[2],
                    SGLN='urn:epc:id:sgln:%s' % row[4]
                )
            except IntegrityError:
                pass
            except Exception as e:
                raise

    def parse_location(self, row):

        city = row[9]
        state = row[10]
        country_code = row[12]
        zip = row[11]
        return city, state, zip, country_code


class PartnerMMDParser:
    """
     Parses partner Master Material Data from provided .csv file
    """

    def __init__(self):
        self.company_records = {}
        self.info_func = None
        self.replenishment_size = None
        self.threshold = None
        self.minimum = None
        self.maximum = None
        self.sending_system_gln = None
        self.response_rule_name = None
        self.secondary_replenishment_size = None

    def parse(self, data: bytes, info_func: object, threshold: int,
              response_rule_name: str, sending_system_gln: str,
              replenishment_size: int, secondary_replenishment_size: int
              ):

        self.replenishment_size = int(replenishment_size)
        self.threshold = threshold
        self.minimum = 0
        self.maximum = 999999
        self.sending_system_gln = sending_system_gln
        self.response_rule_name = response_rule_name

        self.info_func = info_func
        self.secondary_replenishment_size = secondary_replenishment_size

        file_stream = StringIO(data.decode('utf-8'))
        parsed_data = csv.DictReader(file_stream)

        for datarow in parsed_data:
            row = list(datarow.values())
            if row[12] not in ['TraceLink', 'FrequentZ/RFXCEL', 'Pharmasecure']:

                company = self.get_company_by_gln13(row[13])
                if company is None:
                    company = self.create_company(row)

                self.create_trade_item(material_number=row[0],
                                       unit_of_measure='Ea' if row[1] == '' else row[1],
                                       gtin14=row[2],
                                       pallet_pack=row[9],
                                       name=row[10],
                                       l4=row[12],
                                       GLN=row[13],
                                       SGLN=row[14],
                                       company_prefix=row[15],
                                       company=company,

                                           )
                self.create_trade_item(material_number=row[0],
                                       unit_of_measure=row[3],
                                       gtin14=row[4],
                                       pack_count=row[5],
                                       pallet_pack=row[9],
                                       name=row[10],
                                       l4=row[12],
                                       GLN=row[13],
                                       SGLN=row[14],
                                       company_prefix=row[15],
                                       company=company,

                                       )
                if row[6]:
                    self.create_trade_item(material_number=row[0],
                                           unit_of_measure=row[6],
                                           gtin14=row[7],
                                           pack_count=row[8],
                                           pallet_pack=row[9], name=row[10],
                                           l4=row[12],
                                           GLN=row[13],
                                           SGLN=row[14],
                                           company_prefix=row[15],
                                           company=company,

                                           )

    def create_trade_item(self, material_number, unit_of_measure, gtin14,
                          pack_count=None, pallet_pack=None, name=None,
                          l4=None, GLN=None, SGLN=None, company_prefix=None,
                          company: Company = None
                          ):
        """

        :type company: Company
        """
        if company == None:
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

        trade_item = self._get_trade_item_model(company, gtin14,
                                                material_number, name,
                                                pack_count,
                                                pallet_pack,
                                                unit_of_measure)

        self.create_serial_number_range(trade_item, material_number)

    def _get_trade_item_model(self, company, gtin14, material_number, name,
                              pack_count, pallet_pack, unit_of_measure):
        try:
            trade_item = TradeItem.objects.get(GTIN14=gtin14)
        except TradeItem.DoesNotExist:
            trade_item = TradeItem.objects.create(
                GTIN14=gtin14,
                company=company
            )

        trade_item.additional_id = material_number
        trade_item.package_uom = unit_of_measure
        trade_item.pack_count = 0 if pack_count is None or pack_count == '' else pack_count
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

    def create_serial_number_range(self, trade_item: TradeItem, material_number) -> None:

        # create a Random Number based number range
        self.create_random_pool(trade_item, material_number)

    def create_company(self, row):
        """
        Updates or Creates a company record to use when creating pools.
        :param row: The row from the import data with customer name
        and company prefix.
        :return: Company Model.
        """
        try:
            company, _ = Company.objects.get_or_create(
                name=row[11],
                gs1_company_prefix=row[15],
                GLN13=row[13]
            )
            if row[14] is not None and row[14] != '':
                company.SGLN = 'urn:epc:id:sgln:%s' % row[14]
            self.company_records[row[13]] = company
        except Exception as e:
            print('Exception occurred creating company %s .' % row[13])
            raise e

        return company

    def create_random_pool(self, trade_item: TradeItem, material_number) -> None:
        """
        Will create a randomized range for the inbound material record.
        :param trade_item: A TradeItem instance
        :param material_number: Material Number from the imported .csv data.
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
        except IntegrityError:
            pass

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
        Makes sure the Number Request rule exists, will throw an
        exception if the rule does not exist...
        :return: None
        """
        return Rule.objects.get(name='Partner Number Request')

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

    def get_company_by_gln13(self, gln: str):
        try:
            return Company.objects.get(GLN13=gln)
        except Company.DoesNotExist:
            return None

    def get_company(self, gtin: str):
        """
        Looks for the company prefix in the GTIN and returns the company
        database model if that is found.
        :param gtin: The gtin to inspect
        :return: A quartet_masterdata.models.Company instance.
        """
        for company, db_company in self.company_records.items():
            if company in gtin: return db_company
