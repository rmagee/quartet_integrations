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

from typing import List
from quartet_epcis.parsing.business_parser import BusinessEPCISParser
from EPCPyYes.core.v1_2 import events as yes_events

from EPCPyYes.core.v1_2.CBV.instance_lot_master_data import \
    InstanceLotMasterDataAttribute, \
    LotLevelAttributeName, \
    ItemLevelAttributeName, \
    TradeItemLevelAttributeName

ilmd_list = List[yes_events.InstanceLotMasterDataAttribute]


class OptelEPCISLegacyParser(BusinessEPCISParser):
    """
    Parses the old Optel non-compliant epcis data and converts
    to use-able EPCIS data for QU4RTET.
    """
    def parse_unexpected_obj_element(self, oevent: yes_events.ObjectEvent,
                                     child):
        """
        Parses the optel ILMD elements that fall inside
        the standard object events.
        :param oevent: The object event EPCPyYes object.
        :param child:
        :return:
        """
        ilmd = None
        if child.tag.endswith('lotNumber'):
            ilmd = InstanceLotMasterDataAttribute(
                ItemLevelAttributeName.lotNumber.value,
                child.text.strip()
            )
        elif child.tag.endswith('itemExpirationDate'):
            ilmd = InstanceLotMasterDataAttribute(
                LotLevelAttributeName.itemExpirationDate.value,
                child.text.strip()
            )
        elif child.tag.endswith('unitOfMeasure'):
            ilmd = InstanceLotMasterDataAttribute(
                ItemLevelAttributeName.measurementUnitCode.value,
                child.text.strip()
            )
        elif child.tag.endswith('additionalTradeItemIdentificationValue'):
            ilmd = InstanceLotMasterDataAttribute(
                TradeItemLevelAttributeName
                    .additionalTradeItemIdentification.value,
                child.text.strip()
            )
        elif child.tag.endswith('additionalTradeItemIdentification'):
            for sub_element in child:
                self.parse_unexpected_obj_element(oevent, sub_element)
        if ilmd:
            oevent.ilmd.append(ilmd)
