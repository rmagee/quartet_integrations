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
from quartet_capture.models import Rule, Step, StepParameter
from serialbox.models import Pool, ResponseRule
from random_flavorpack.models import RandomizedRegion
from quartet_masterdata.models import TradeItem, TradeItemField

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
