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
from gs123.check_digit import calculate_check_digit
from EPCPyYes.core.v1_2 import template_events
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from eparsecis.eparsecis import FlexibleNSParser
from quartet_integrations.extended.environment import get_default_environment

"""
    The ExtendedParser Parser puts epcs in commissioning events into the Packaging Level Order.    
"""
class ExtendedParser(FlexibleNSParser):
    """
        ctor
    """
    def __init__(self, data, reg_ex):

        self._ssccs = []  # internal list to hold collected SSCCs
        self._quantity = 0
        self._po = ""
        self._regEx = re.compile(reg_ex)
        self._lot_number = ""
        self._product_code = ""
        self._exp_date = ""
        self._biz_location = ""
        self._read_point = ""
        self._object_events = []
        self._aggregation_events = []
        self.comm_eaches_event = None
        self.comm_cartons_event = None
        self.comm_pallets_event = None

        env = get_default_environment()
        temp = env.get_template('extended/ext_object_events.xml')
        self._template = temp
        # call the base constructor with the stream
        super(ExtendedParser, self).__init__(stream=data)

    """
        When the base parser sees an ObjectEvent, this method is called
        The event is passed in as a parameter. The epcis_event's epc_list
        is inspected for all SSCCs and, when an SSCC is found, the SSCC is
        placed into the internal _ssccs list
    """
    def handle_object_event(self, epcis_event: template_events.ObjectEvent):

        if epcis_event.ilmd is not None:
            for item in epcis_event.ilmd:
                if item.name == 'lotNumber':
                    self._lot_number = item.value
                elif item.name == "itemExpirationDate":
                    self._exp_date = item.value
                elif item.name == "NDC":
                    self._product_code = self._convert_ndc_gtin(item.value)

        self._biz_location = epcis_event.biz_location
        self._read_point = epcis_event.read_point

        if len(epcis_event.business_transaction_list) > 0:
            self._po = epcis_event.business_transaction_list[0].biz_transaction

        if epcis_event.action == "ADD":
            for epc in epcis_event.epc_list:
                if epc.startswith('urn:epc:id:sscc:'):
                    self._ssccs.append(epc)
                    # Add to Pallets commissioning Event
                    self._add_pallet(epcis_event, epc)
                else:
                    m = self._regEx.match(epc)
                    if m:
                        # adjust the quantity
                        self._quantity = self._quantity + 1
                        parts = epc.split('.')
                        if parts[1].startswith('0'):
                            # Add to Eaches commissioning Event
                            self._add_each(epcis_event, epc)
                        elif parts[1].startswith('2'):
                            # Add to Cartons commissioning Event
                            self._add_carton(epcis_event, epc)



    def handle_aggregation_event(
        self,
        epcis_event: template_events.AggregationEvent
    ):
        if epcis_event.parent_id.startswith('urn:epc:id:sscc:'):
           for epc in epcis_event.child_epcs:
               if epc in self._ssccs:
                  self._ssccs.remove(epc)
                  if epc in self.comm_pallets_event.epc_list:
                      self.comm_pallets_event.epc_list.remove(epc)
                      self.comm_cartons_event.epc_list.append(epc)
        self._aggregation_events.append(epcis_event)

    def _convert_ndc_gtin(self, ndc):

        part = ndc.replace('-','')
        gtin = "003{0}".format(part)
        ret_val = calculate_check_digit(gtin)
        return ret_val

    def _add_each(self, epcis_event, epc):

        if self.comm_eaches_event is None:
           # A commissioning event for the Eaches does not exist
           # Create one
            self.comm_eaches_event = template_events.ObjectEvent(
                             epc_list=[epc],
                             record_time=epcis_event.record_time,
                             event_time=epcis_event.event_time,
                             event_timezone_offset=epcis_event.event_timezone_offset,
                             action = epcis_event.action,
                             biz_step = BusinessSteps.commissioning.value,
                             disposition = Disposition.active.value,
                             read_point = epcis_event.read_point,
                             biz_location = epcis_event.biz_location,
                             template=self._template
                        )

            self.comm_eaches_event._context['product_code'] = self.product_code
            self.comm_eaches_event._context['lot'] = self.lot_number
            self.comm_eaches_event._context['exp_date'] = self.exp_date
            self.comm_eaches_event._context['pack_level'] = "EA"
            self.comm_eaches_event._context['location_id'] = epcis_event.biz_location.replace('urn:epc:id:sgln:', '')

            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_eaches_event)
        else:
            # A commissioning event for the Eaches does exist
            # Add the epc to the epc_list of the event.
            self.comm_eaches_event.epc_list.append(epc)

    def _add_carton(self, epcis_event, epc):

        if self.comm_cartons_event is None:
           # A commissioning event for the Cartons does not exist
           # Create one
            self.comm_cartons_event = template_events.ObjectEvent(
                             epc_list=[epc],
                             record_time=epcis_event.record_time,
                             event_time=epcis_event.event_time,
                             event_timezone_offset=epcis_event.event_timezone_offset,
                             action = epcis_event.action,
                             biz_step = BusinessSteps.commissioning.value,
                             disposition = Disposition.active.value,
                             read_point = epcis_event.read_point,
                             biz_location = epcis_event.biz_location,
                             template=self._template
                        )
            self.comm_cartons_event._context['product_code'] = self.product_code
            self.comm_cartons_event._context['lot'] = self.lot_number
            self.comm_cartons_event._context['exp_date'] = self.exp_date
            self.comm_cartons_event._context['pack_level'] = "CA"
            self.comm_cartons_event._context['location_id'] = epcis_event.biz_location.replace('urn:epc:id:sgln:', '')

            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_cartons_event)
        else:
            # A commissioning event for the Cartons does exist
            # Add the epc to the epc_list of the event.
            self.comm_cartons_event.epc_list.append(epc)

    def _add_pallet(self, epcis_event, epc):

        if self.comm_pallets_event is None:
           # A commissioning event for the Cartons does not exist
           # Create one
            self.comm_pallets_event = template_events.ObjectEvent(
                             epc_list=[epc],
                             record_time=epcis_event.record_time,
                             event_time=epcis_event.event_time,
                             event_timezone_offset=epcis_event.event_timezone_offset,
                             action = epcis_event.action,
                             biz_step = BusinessSteps.commissioning.value,
                             disposition = Disposition.active.value,
                             read_point = epcis_event.read_point,
                             biz_location = epcis_event.biz_location,
                             template=self._template
                        )
            self.comm_pallets_event._context['product_code'] = self.product_code
            self.comm_pallets_event._context['lot'] = self.lot_number
            self.comm_pallets_event._context['exp_date'] = self.exp_date
            self.comm_pallets_event._context['pack_level'] = "PL"
            self.comm_pallets_event._context['location_id'] = epcis_event.biz_location.replace('urn:epc:id:sgln:','')

            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_pallets_event)
        else:
            # A commissioning event for the Cartons does exist
            # Add the epc to the epc_list of the event.
            self.comm_pallets_event.epc_list.append(epc)

    @property
    def quantity(self):
        return self._quantity

    @property
    def sscc_list(self):
        # Returns the SSCCs collected in self.handle_object_event
        # Only call after parse() is called.
        return self._ssccs

    @property
    def lot_number(self):
        return self._lot_number

    @property
    def exp_date(self):
        return self._exp_date

    @property
    def product_code(self):
        return self._product_code

    @property
    def cartons(self):
        return self._cartons

    @property
    def object_events(self):
        return self._object_events

    @property
    def read_point(self):
        return self._read_point

    @property
    def biz_location(self):
        return self._biz_location

    @property
    def PO(self):
        return self._po

