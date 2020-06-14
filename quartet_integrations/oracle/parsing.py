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
from sqlite3 import IntegrityError as sqlIE
from quartet_capture.models import Rule
from quartet_masterdata.models import TradeItem
from quartet_masterdata.models import TradeItemField, Company, Location, LocationField, CompanyType
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
            try:
                trade_item = TradeItem.objects.get(GTIN14=gtin14)
                trade_item.company = company
                trade_item.additional_id=material_number
                trade_item.package_uom=unit_of_measure
                trade_item.pack_count=pack_count
                trade_item.regulated_product_name=name
                trade_item.save()
            except TradeItem.DoesNotExist:
                trade_item = TradeItem.objects.create(
                    company=company,
                    additional_id=material_number,
                    package_uom=unit_of_measure,
                    GTIN14=gtin14,
                    pack_count=pack_count,
                    regulated_product_name=name
                )
            self.info_func('Trade item is %s %s', gtin14, name)
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
        except IntegrityError:
            self.info_func('Randomized region with name %s already exists',
                           trade_item.GTIN14)

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


class TradingPartnerParser:

    def parse(self, data: bytes, info_func):
        """
        Parses inbound trading partner spreadsheet data.
        """
        file_stream = StringIO(data.decode('utf-8'))
        self.info_func = info_func
        parsed_data = csv.DictReader(file_stream)
        for data in parsed_data:
            data = list(data.values())
            from_company = self.create_from_company(data)
            to_company = self.create_to_company(data)
            try:
                self.create_location(from_company)
                self.create_location(to_company)
            except (IntegrityError, sqlIE):
                info_func('Skipping location.  Already exists.')

    def create_location(self, company: Company):
        """
        Creates a location which is a duplicate of the company.  This
        allows for mapping of locations to companies and vise-versa
        freely after importing the data.
        :param data: The data row with partner info
        :param company: The location's parent company
        :param location_type: The type of location.
        :return: The Location model instance that was created.
        """
        try:
            location = Location.objects.get(
                GLN13=company.GLN13
            )
            location.name = company.name
        except Location.DoesNotExist:
            try:
                location = Location.objects.get(
                    SGLN=company.SGLN
                )
                location.name = company.name
                location.GLN13 = company.GLN13
            except Location.DoesNotExist:
                location = Location.objects.create(
                    GLN13=company.GLN13,
                    name=company.name
                )
        location.SGLN = company.SGLN
        location.address1 = company.address1
        location.address2 = company.address2
        location.address3 = company.address3
        location.city = company.city
        location.state_province = company.state_province
        location.postal_code = company.postal_code
        location.country = company.country
        location.save()
        LocationField.objects.get_or_create(
            name='Import Type', value='Oracle', location=location
        )

    def create_from_company(self, data):
        try:
            company = Company.objects.get(
                GLN13=data[3]
            )
            company.name = data[1]
        except Company.DoesNotExist:
            company = Company.objects.create(
                name=data[1],
                gs1_company_prefix=data[2]
            )
        company.GLN13 = data[3]
        company.SGLN = 'urn:epc:id:sgln:%s' % data[4]
        company.address1 = data[5]
        company.address2 = data[6]
        company.address3 = data[7]
        company.city = data[9]
        company.state_province = data[10]
        company.postal_code = data[11]
        company.country = data[12]
        CompanyType.objects.get_or_create(
            identifier='Import Type',
            description='Oracle',
            company=company
        )
        try:
            company.save()
        except (IntegrityError, sqlIE):
            self.info_func('Company %s already exists.', company.name)

        return company

    def create_to_company(self, data: list):
        try:
            company = Company.objects.get(
                GLN13=data[23]
            )
            company.name = data[13]
        except Company.DoesNotExist:
            company = Company.objects.create(
                name=data[13],
                gs1_company_prefix=data[22]
            )
        company.GLN13 = data[23]
        company.SGLN = 'urn:epc:id:sgln:%s' % data[24]
        company.address1 = data[14]
        company.address2 = data[15]
        company.address3 = data[16]
        company.city = data[18]
        company.state_province = data[19]
        company.postal_code = data[20]
        company.country = data[21]
        try:
            company.save()
        except (IntegrityError, sqlIE):
            self.info_func('Company %s already exists.', company.name)
        return company
