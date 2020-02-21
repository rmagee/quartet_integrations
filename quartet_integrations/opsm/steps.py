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
from gs123.conversion import BarcodeConverter

from quartet_integrations.serialbox.steps import \
    ListToUrnConversionStep as SBLTU


class ListToUrnConversionStep(SBLTU):
    """
    Converts serialbox lists to OPSM URNs using the data in the result.
    """

    def format_gtin_urn(self, company_prefix: str, indicator: str,
                        item_reference: str, serial_number: str):
        return '0.%s.%s%s.%s' % (
            company_prefix, indicator, item_reference,
            serial_number)



class ListBasedRegionConversionStep(SBLTU):
    """
    Converts 01/21 GTIN strings to OPSM URNS.
    """
    def format_gtin_urn(self, company_prefix: str, indicator: str,
                        item_reference: str, serial_number: str):
        ret = None
        ret = BarcodeConverter(serial_number, len(company_prefix)).epc_urn
        return ret.replace('urn:epc:id:sgtin:', '0.')
