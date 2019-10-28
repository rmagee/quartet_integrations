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

import pandas
from io import BytesIO
from copy import copy
from quartet_capture.rules import Step, RuleContext
from quartet_masterdata.models import TradeItem, Company, TradeItemField


class MasterMaterialParser:
    """
    Imports master material exports from oracle into the quartet trade
    items.
    """

    def __init__(self, company_records: dict):
        self.company_records = company_records

    def parse(self, data: bytes, info_func, rule_context: RuleContext = None):
        file_stream = BytesIO(data)
        parsed_data = pandas.read_excel(
            file_stream,
            sheet_name='Sheet1',
            dtype=str,
            converters={
                'GTIN': str,
                'Level2 GTIN': str,
                'Level3 GTIN': str
            }
        )
        print(parsed_data)
        for row in parsed_data.values:
            self.create_trade_item(row[0], row[1], row[2], pallet_pack=row[9])
            self.create_trade_item(row[0], row[3], row[4], row[5], row[9])
            if row[6]:
                self.create_trade_item(row[0], row[6], row[7], row[9])

    def create_trade_item(self, material_number, unit_of_measure, gtin14,
                          pack_count=None, pallet_pack=None):
        company = self.get_company(gtin14)
        assert(company != None)
        trade_item = TradeItem.objects.get_or_create(
            company=company,
            additional_id=material_number,
            package_uom=unit_of_measure,
            GTIN14=gtin14,
            pack_count=pack_count
        )[0]
        TradeItemField.objects.get_or_create(
            trade_item=trade_item,
            name='pallet_pack_count',
            value=pallet_pack
        )

    def get_company(self, gtin: str):
        """
        Looks for the company prefix in the GTIN and returns the company
        database model if that is found.
        :param gtin: The gtin to inspect
        :return: A quartet_masterdata.models.Company instance.
        """
        for company, db_company in self.company_records.items():
            if company in gtin: return db_company
