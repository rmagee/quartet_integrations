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
import re
from datetime import datetime
from typing import List

from EPCPyYes.core.v1_2 import template_events
from EPCPyYes.core.v1_2 import template_events as yes_events, events
from EPCPyYes.core.v1_2.events import Action
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.CBV.instance_lot_master_data import \
    InstanceLotMasterDataAttribute, LotLevelAttributeName, \
    ItemLevelAttributeName

from logging import getLogger

from quartet_capture.rules import RuleContext
from quartet_epcis.models import choices
from quartet_epcis.parsing.context_parser import BusinessEPCISParser
from quartet_integrations.gs1ushc import mixins
from quartet_integrations.optel.epcpyyes import get_default_environment
from quartet_output.parsing import BusinessOutputParser
from gs123.conversion import URNConverter


logger = getLogger(__name__)
ilmd_list = List[yes_events.InstanceLotMasterDataAttribute]
# https://regex101.com/r/D1coNK/1
time_regex = re.compile(r'([\+\-]([01]\d|2[0-3]):([0-5]\d)|24:00)')


class OptelOutputEPCISParser(BusinessOutputParser):

    def get_epcpyyes_object_event(self):
        return template_events.ObjectEvent(
            epc_list=[], quantity_list=[],
            env=get_default_environment(),
            template='quartet_integrations/optel/object_event.xml'
        )


class OptelEPCISLegacyParser(mixins.ConversionMixin, BusinessEPCISParser):
    """
    Parses the old Optel non-compliant epcis data and converts
    to use-able EPCIS data for QU4RTET.  The conversion mixin handles
    the gs1ushc namespace items.
    """

    def __init__(self, stream, event_cache_size: int = 1024,
                 recursive_decommission: bool = True,
                 recursive_child_update: bool = False,
                 child_update_from_top: bool = True,
                 rule_context: RuleContext = None):
        BusinessEPCISParser.__init__(
            self,
            stream, event_cache_size,
            recursive_decommission,
            recursive_child_update, child_update_from_top,
            rule_context
        )

    def parse(self, replace_timezone=False):
        """
        Will begin the parsing process of any inbound stream/file provided
        in the constructor.
        :param replace_timezone: Whether or not to replace timezones in
        event times with the timezone offset in the event.
        :return:
        """
        self._replace_timezone = replace_timezone
        return super().parse()

    def get_event_time(self, epcis_event: events.EPCISEvent) -> datetime:
        if self._replace_timezone and epcis_event.event_timezone_offset:
            epcis_event.event_time = time_regex.sub(
                epcis_event.event_timezone_offset,
                epcis_event.event_time
            )
            if epcis_event.record_time:
                epcis_event.record_time = time_regex.sub(
                    epcis_event.event_timezone_offset,
                    epcis_event.record_time
                )
        return super().get_event_time(epcis_event)

    def _parse_date(self, epcis_event):
        return self.get_event_time(epcis_event)


class OptelAutoShipParser(OptelEPCISLegacyParser):
    def handle_aggregation_event(self, epcis_event: events.AggregationEvent):
        if epcis_event.action == Action.add.value:
            epcis_event.disposition = Disposition.in_transit
        return super().handle_aggregation_event(epcis_event)


class ConsolidationParser(OptelEPCISLegacyParser):
    """
    Will condense the insane optel single object event per
    serial number into a single object event.  Only use this
    when you are sure that the structure of the lot messages
    is suitable.
    """

    def __init__(self, stream, event_cache_size: int = 1024,
                 recursive_decommission: bool = True):
        super().__init__(stream, event_cache_size, recursive_decommission)
        self.add_event = None
        self.db_event = None

    def handle_object_event(self, epcis_event: yes_events.ObjectEvent):
        if epcis_event.action == 'ADD':
            if self.add_event:
                # self.add_event.epc_list += epcis_event.epc_list
                self.handle_entries(self.db_event, epcis_event.epc_list,
                                    epcis_event)
                db_entries = self._get_entries(self.add_event.epc_list)
                self._update_event_entries(db_entries, self.db_event,
                                           epcis_event)
            else:
                logger.debug('Handling an ObjectEvent...')
                if not self.db_event:
                    self.db_event = self.get_db_event(epcis_event)
                    self.db_event.type = choices.EventTypeChoicesEnum.OBJECT.value
                self.handle_entries(self.db_event, epcis_event.epc_list,
                                    epcis_event)
                self.handle_common_elements(self.db_event, epcis_event)
                self.handle_ilmd(self.db_event.id, epcis_event.ilmd)
                self._append_event_to_cache(self.db_event)
                self.add_event = epcis_event
                db_entries = self._get_entries(self.add_event.epc_list)
                self._update_event_entries(db_entries, self.db_event,
                                           self.add_event)
        else:
            super().handle_object_event(epcis_event)


class OptelCompactV2Parser(BusinessEPCISParser):
    '''
    Parses EPCIS data from Optel's Compact connector
    '''
    def __init__(self, stream, event_cache_size: int = 1024,
                 recursive_decommission: bool = True,
                 recursive_child_update: bool = False,
                 child_update_from_top: bool = True,
                 rule_context: RuleContext = None,
                 skip_parsing: bool = False,
                 extension_digit: str = '0'):
        super().__init__(stream, event_cache_size, recursive_decommission,
                         recursive_child_update, child_update_from_top)
        self.extension_digit = extension_digit
        self.gtin = None
        self.lot_number = None
        self.ssccs = []
        self.skip_parsing = skip_parsing
        self.trade_item_list = []
    
    def parse_extension(self, epcis_event, extension):
        super().parse_extension(epcis_event, extension)
        # Get data from optelvision:extension tags
        self.handle_optelvision_extension(epcis_event, extension)
    
    def handle_optelvision_extension(self, epcis_event, extension):
        # Get Lot/Batch info
        if extension.attrib.get('name').upper() == 'BATCH':
            ilmd = InstanceLotMasterDataAttribute(
                ItemLevelAttributeName.lotNumber.value,
                value=extension.text.strip()
            )
            epcis_event.ilmd.append(ilmd)
        elif extension.attrib.get('name').upper() == 'EXPIRY':
            # Convert EXPIRY to valid format 
            expiry_date = extension.text.strip()
            expiry_date = self._format_date(expiry_date)
            ilmd = InstanceLotMasterDataAttribute(
                LotLevelAttributeName.itemExpirationDate.value,
                value=expiry_date
            )
            epcis_event.ilmd.append(ilmd)
    
    def _format_date(self, date_str):
        """
            Converts date from YYYYMMDD to YYYY-MM-DD format

            :param date_str: string value containing date

            :return: date_str in a valid format
        """
        if len(date_str) == 8:
                year, month, day = (
                    date_str[:4],
                    date_str[4:6],
                    date_str[6:8],
                )
                date_str = '-'.join([year, month, day])
        return date_str


    def handle_object_event(self, epcis_event: events.ObjectEvent):
        if not self.skip_parsing:
            super().handle_object_event(epcis_event)
        self.evaluate_object_event(epcis_event)

    def handle_aggregation_event(self, epcis_event: events.AggregationEvent):
        if not self.skip_parsing:
            if epcis_event.action == Action.add.value:
                epcis_event.disposition = Disposition.in_progress
            super().handle_aggregation_event(epcis_event)
    
    def evaluate_object_event(self, epcis_event: events.ObjectEvent):
        # Check if this is commissioning object event
        if epcis_event.action == 'ADD':
            if ':sgtin:' in epcis_event.epc_list[0]:
                epc = epcis_event.epc_list[0]
                gtin = URNConverter(epc).gtin14
                # check if the extension digit matches
                if not self.gtin and self.extension_digit == epc.split('.')[1][0]:
                    # build and save gtin
                    self.gtin = gtin
                # Add to Trade Item List (For Master Data)
                if gtin not in self.trade_item_list:
                    self.trade_item_list.append(gtin)    
            elif ':sscc:' in epcis_event.epc_list[0]:
                self.ssccs += epcis_event.epc_list
                conv = URNConverter(epcis_event.epc_list[0])
                item = conv.extension_digit + conv.company_prefix
                if item not in self.trade_item_list:
                    self.trade_item_list.append(item)
            if not self.lot_number:
                for ilmd in epcis_event.ilmd:
                    if 'lotNumber' in ilmd.name: self.lot_number = ilmd.value
