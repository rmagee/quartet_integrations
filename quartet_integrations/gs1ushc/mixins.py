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
from EPCPyYes.core.v1_2 import template_events as yes_events
from EPCPyYes.core.v1_2.CBV import InstanceLotMasterDataAttribute, \
    ItemLevelAttributeName, LotLevelAttributeName, \
    TradeItemLevelAttributeName, SourceDestinationTypes
from EPCPyYes.core.v1_2.events import Destination, Source


class ConversionMixin:
    """
    To be used with a parser that needs to understand/convert the old
    GS1 USHC namespace elements to EPCIS 1.2
    """

    def parse_unexpected_obj_element(self, oevent: yes_events.ObjectEvent,
                                     child):
        self.parse_element(oevent, child)

    def parse_unexpected_xact_element(self,
                                      xevent: yes_events.TransactionEvent,
                                      child):
        self.parse_element(xevent, child)

    def parse_element(self, event,
                      child):
        """
        Parses the optel ILMD elements that fall inside
        the standard object events.
        :param event: The object event EPCPyYes object.
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
                self.parse_unexpected_obj_element(event, sub_element)
        elif child.tag.endswith('transferredToId'):
            destination = Destination(
                SourceDestinationTypes.owning_party.value,
                child.text.strip()
            )
            event.destination_list.append(destination)
        elif child.tag.endswith('transferredById'):
            source = Source(
                SourceDestinationTypes.possessing_party.value,
                child.text.strip()
            )
            event.source_list.append(source)
        elif child.tag.endswith('shipToLocationId'):
            destination = Destination(
                SourceDestinationTypes.location.value,
                child.text.strip()
            )
            event.destination_list.append(destination)
        elif child.tag.endswith('shipFromLocationId'):
            source = Source(
                SourceDestinationTypes.possessing_party.value,
                child.text.strip()
            )
            event.source_list.append(source)
        if ilmd:
            event.ilmd.append(ilmd)


class ParsingMixin:
    """
    To be used with a parser that needs to store the old
    GS1 USHC namespace elements in QU4RTET as-is.
    """
    def parse_unexpected_obj_element(
        self,
        oevent: yes_events.ObjectEvent,
        child
    ):
        self.parse_element(oevent, child)

    def parse_unexpected_xact_element(
        self,
        xevent: yes_events.TransactionEvent,
        child
    ):
        self.parse_element(xevent, child)

    def parse_element(self, event,
                      child):
        """
        Parses any gs1ushc ILMD elements that fall inside
        the standard shipping events.
        :param event: The object event EPCPyYes object.
        :param child:
        :return:
        """
        ilmd_types = ['lotNumber', 'itemExpirationDate', 'unitOfMeasure',
                      'additionalTradeItemIdentificationValue',
                      'additionalTradeItemIdentification']
        for type in ilmd_types:
            if child.tag.endswith(type):
                ilmd = InstanceLotMasterDataAttribute(
                    TradeItemLevelAttributeName
                        .additionalTradeItemIdentification.value,
                    child.text.strip()
                )
                event.ilmd.append(ilmd)
                return
        id_type = child.tag.get('type')
        source_dest_types = ['transferredToId', 'transferredById',
                             'shipToLocationId',
                             'shipFromLocationId']
        for sdt in source_dest_types:
            if child.tag.endswith(sdt) and sdt in ['transferredToId',
                                                   'shipToLocationId']:
                event.destination_list.append(
                    Destination(
                        'gs1ushc:%s type="%s"' % (sdt, id_type) if id_type
                        else 'gs1ushc:%s' % sdt,
                        child.text.strip
                    )
                )
            elif child.tag.endswith(sdt) and sdt in ['shipFromLocationId',
                                                     'transferredById']:
                event.source_list.append(
                    Source(
                        'gs1ushc:%s type="%s"' % (sdt, id_type) if id_type
                        else 'gs1ushc:%s' % sdt,
                        child.text.strip
                    )
                )

