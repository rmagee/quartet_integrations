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
import datetime
from datetime import timedelta
from gs123.check_digit import calculate_check_digit
from EPCPyYes.core.v1_2 import template_events
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from eparsecis.eparsecis import FlexibleNSParser
from quartet_integrations.extended.environment import get_default_environment

"""
    The TraxeedParser parses data EPCIS sent from Traxeed.    
"""
class TraxeedParser(FlexibleNSParser):
    """
        ctor
    """
    def __init__(self, data, reg_ex, pack_levels=None):

        self._ssccs = []  # internal list to hold collected SSCCs
        self._quantity = 0
        self._po = ""
        self._regEx = re.compile(reg_ex)
        self._lot_number = ""
        self._gtin = ""
        self._ndc = ""
        self._exp_date = ""
        self._biz_location = ""
        self._read_point = ""
        self._event_time = None
        self._time_zone_offset = None
        self._record_time = None
        self._object_events = []
        self._aggregation_events = []
        self.comm_eaches_event = None
        self.comm_cartons_event = None
        self.comm_partial_event = None
        self.comm_pallets_event = None
        self._pack_levels = pack_levels.split(',') if pack_levels and len(pack_levels) > 0 else []
        env = get_default_environment()
        temp = env.get_template('traxeed/tx_hk_object_events.xml')
        self._obj_template = temp
        temp = env.get_template('traxeed/tx_hk_object_pallet.xml')
        self._pallet_template = temp
        temp = env.get_template('traxeed/tx_hk_object_partial.xml')
        self._partial_template = temp
        # call the base constructor with the stream
        super(TraxeedParser, self).__init__(stream=data)

    """
    """
    def handle_object_event(self, epcis_event: template_events.ObjectEvent):

        if epcis_event.ilmd is not None:
            for item in epcis_event.ilmd:
                if item.name == 'lotNumber':
                    self._lot_number = item.value
                elif item.name == "itemExpirationDate":
                    self._exp_date = item.value
                elif item.name == "NDC":
                    self._gtin = self._convert_ndc_gtin(item.value)
                    self._ndc = item.value

        self._biz_location = epcis_event.biz_location
        self._read_point = epcis_event.read_point

        if len(epcis_event.business_transaction_list) > 0:
            po = epcis_event.business_transaction_list[0].biz_transaction
            self._po = po.split(':')[5]

        if epcis_event.action == "ADD":
            for epc in epcis_event.epc_list:
                if epc.startswith('urn:epc:id:sscc:'):
                    self._ssccs.append(epc)
                    # Add to Pallets commissioning Event
                    self._add_pallet(epcis_event, epc)
                else:
                    m = self._regEx.match(epc)
                    if m:

                        parts = epc.split('.')
                        if parts[1].startswith('0'):
                            # Add to Eaches commissioning Event
                            # adjust the quantity
                            self._quantity = self._quantity + 1
                            self._add_each(epcis_event, epc)
                        elif parts[1].startswith('5'):
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
                      self.comm_partial_event =  self._add_partial(epcis_event, epc)
                      self.comm_pallets_event.epc_list.remove(epc)


        self._time_zone_offset = epcis_event.event_timezone_offset
        t = datetime.datetime.strptime(epcis_event.record_time,'%Y-%m-%dT%H:%M:%SZ')
        dt = t + timedelta(seconds=10)
        epcis_event.record_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        epcis_event.event_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        self._record_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        self._event_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
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
            self.comm_eaches_event = self._create_comm_eaches(epcis_event, epc)

            self.comm_eaches_event._context['gtin'] = self.gtin
            self.comm_eaches_event._context['ndc'] = self.ndc
            self.comm_eaches_event._context['lot'] = self.lot_number
            self.comm_eaches_event._context['exp_date'] = self.exp_date
            self.comm_eaches_event._context['pack_level'] = "EA"
            self.comm_eaches_event._context['po'] = self.PO
            self.comm_eaches_event._context['location_id'] = epcis_event.biz_location.replace('urn:epc:id:sgln:', '')

            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_eaches_event)
        else:
            # A commissioning event for the Eaches does exist
            # Add the epc to the epc_list of the event.
            self.comm_eaches_event.epc_list.append(epc)

    def _create_comm_eaches(self, epcis_event, epc):
        ret_val = template_events.ObjectEvent(
            epc_list=[epc],
            record_time=epcis_event.record_time,
            event_time=epcis_event.event_time,
            event_timezone_offset=epcis_event.event_timezone_offset,
            action=epcis_event.action,
            biz_step=BusinessSteps.commissioning.value,
            disposition=Disposition.active.value,
            read_point=epcis_event.read_point,
            biz_location=epcis_event.biz_location,
            template=self._obj_template
        )

        return ret_val

    def _add_carton(self, epcis_event, epc):

        if self.comm_cartons_event is None:
           # A commissioning event for the Cartons does not exist
           # Create one
            self.comm_cartons_event = self._create_comm_cartons_event(epcis_event, epc)
            gtin = self.gtin[1:13]
            # change indicator
            gtin = "5{0}".format(gtin)
            gtin = calculate_check_digit(gtin)
            self.comm_cartons_event._context['gtin'] = gtin
            self.comm_cartons_event._context['ndc'] = self.ndc
            self.comm_cartons_event._context['lot'] = self.lot_number
            self.comm_cartons_event._context['exp_date'] = self.exp_date
            self.comm_cartons_event._context['pack_level'] = "CA"
            self.comm_cartons_event._context['po'] = self.PO
            self.comm_cartons_event._context['location_id'] = epcis_event.biz_location.replace('urn:epc:id:sgln:', '')

            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_cartons_event)
        else:
            # A commissioning event for the Cartons does exist
            # Add the epc to the epc_list of the event.
            self.comm_cartons_event.epc_list.append(epc)

    def _create_comm_cartons_event(self, epcis_event, epc):

        ret_val = template_events.ObjectEvent(
            epc_list=[epc],
            record_time=epcis_event.record_time,
            event_time=epcis_event.event_time,
            event_timezone_offset=epcis_event.event_timezone_offset,
            action=epcis_event.action,
            biz_step=BusinessSteps.commissioning.value,
            disposition=Disposition.active.value,
            read_point=epcis_event.read_point,
            biz_location=epcis_event.biz_location,
            template=self._obj_template
        )

        return ret_val

    def _add_partial(self, epcis_event, epc):

        if self.comm_partial_event is None:
            # A commissioning event for the Partial Cartons does not exist
            # Create one
            self.comm_partial_event = self._create_comm_partial_event(epcis_event, epc)

            val = epc.split(':')
            val = val[4].split('.')
            company_prefix = val[0]
            filter = val[1][0]

            self.comm_partial_event._context['company_prefix'] = company_prefix
            self.comm_partial_event._context['filter'] = filter
            self.comm_partial_event._context['pack_level'] = "CA"
            self.comm_partial_event._context['po'] = self.PO
            self.comm_partial_event._context['location_id'] = epcis_event.biz_location.replace('urn:epc:id:sgln:', '')



            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_partial_event)
        else:
            # A commissioning event for the Cartons does exist
            # Add the epc to the epc_list of the event.
            self.comm_partial_event.epc_list.append(epc)


    def _create_comm_partial_event(self, epcis_event, epc):

        # the event comming in is an AggregationEvent because the partial can only be discovered
        # by watching the aggregation events in the handle_aggregation method. So to make sure
        # the record and event times are in sync with the commissioning events, get a ref to
        # the first object event and use that record and event time.
        try:
            evt = self._object_events[0]
            record_time = evt.record_time
            event_time = evt.event_time
        except:
            # if there are no events in _object_events
            # fall back to the epcis_event and adjust the times down
            evt = epcis_event
            t = datetime.datetime.strptime(epcis_event.record_time, '%Y-%m-%dT%H:%M:%SZ')
            dt = t - timedelta(seconds=10)
            record_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            event_time = record_time

        ret_val = template_events.ObjectEvent(
            epc_list=[epc],
            record_time=record_time,
            event_time=event_time,
            event_timezone_offset=evt.event_timezone_offset,
            action=evt.action,
            biz_step=BusinessSteps.commissioning.value,
            disposition=Disposition.active.value,
            read_point=evt.read_point,
            biz_location=evt.biz_location,
            template=self._partial_template
        )

        return ret_val

    def _add_pallet(self, epcis_event, epc):

        if self.comm_pallets_event is None:
           # A commissioning event for the Pallets does not exist
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
                             template=self._pallet_template
                        )
            val = epc.split(':')
            val = val[4].split('.')
            company_prefix = val[0]
            filter = val[1][0]

            self.comm_pallets_event._context['company_prefix'] = company_prefix
            self.comm_pallets_event._context['filter'] = filter
            self.comm_pallets_event._context['pack_level'] = "PL"
            self.comm_pallets_event._context['po'] = self.PO
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
    def gtin(self):
        return self._gtin

    @property
    def ndc(self):
        return self._ndc

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

    @property
    def event_time(self):
        return self._event_time

    @property
    def time_zone_offset(self):
        return self._time_zone_offset

    @property
    def record_time(self):
        return self._record_time


class TraxeedRfxcelParser(FlexibleNSParser):

    def __init__(self, data, reg_ex):

        self._ssccs = []  # internal list to hold collected SSCCs
        self._quantity = 0
        self._po = ""
        self._regEx = re.compile(reg_ex)
        self._lot_number = ""
        self._gtin = ""
        self._ndc = ""
        self._exp_date = ""
        self._biz_location = ""
        self._read_point = ""
        self._event_time = None
        self._time_zone_offset = None
        self._record_time = None
        self._object_events = []
        self._aggregation_events = []
        self.comm_eaches_event = None
        self.comm_cartons_event = None
        self.comm_partial_event = None
        self.comm_pallets_event = None
        env = get_default_environment()
        temp = env.get_template('traxeed/tx_rf_object_events.xml')
        self._obj_template = temp
        # call the base constructor with the stream
        super(TraxeedRfxcelParser, self).__init__(stream=data)


    def handle_object_event(self, epcis_event: template_events.ObjectEvent):

        if epcis_event.ilmd is not None:
            for item in epcis_event.ilmd:
                if item.name == 'lotNumber':
                    self._lot_number = item.value
                elif item.name == "itemExpirationDate":
                    self._exp_date = item.value

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
                        parts = epc.split('.')
                        if parts[1].startswith('0'):
                            # Add to Eaches commissioning Event
                            # adjust the quantity
                            self._quantity = self._quantity + 1
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
                      self.comm_partial_event =  self._add_partial(epcis_event, epc)
                      self.comm_pallets_event.epc_list.remove(epc)


        self._time_zone_offset = epcis_event.event_timezone_offset
        t = datetime.datetime.strptime(epcis_event.record_time,'%Y-%m-%dT%H:%M:%SZ')
        dt = t + timedelta(seconds=10)
        epcis_event.record_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        epcis_event.event_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        self._record_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        self._event_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        self._aggregation_events.append(epcis_event)


    def _add_carton(self, epcis_event, epc):

        if self.comm_cartons_event is None:
           # A commissioning event for the Cartons does not exist
           # Create one
            self.comm_cartons_event = self._create_comm_cartons_event(epcis_event, epc)

            self.comm_cartons_event._context['lot'] = self.lot_number
            self.comm_cartons_event._context['exp_date'] = self.exp_date


            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_cartons_event)
        else:
            # A commissioning event for the Cartons does exist
            # Add the epc to the epc_list of the event.
            self.comm_cartons_event.epc_list.append(epc)

    def _create_comm_cartons_event(self, epcis_event, epc):

        ret_val = template_events.ObjectEvent(
            epc_list=[epc],
            record_time=epcis_event.record_time,
            event_time=epcis_event.event_time,
            event_timezone_offset=epcis_event.event_timezone_offset,
            action=epcis_event.action,
            biz_step=BusinessSteps.commissioning.value,
            disposition=Disposition.active.value,
            read_point=epcis_event.read_point,
            biz_location=epcis_event.biz_location,
            template=self._obj_template
        )

        return ret_val

    def _add_partial(self, epcis_event, epc):

        if self.comm_partial_event is None:
            # A commissioning event for the Partial Cartons does not exist
            # Create one
            self.comm_partial_event = self._create_comm_partial_event(epcis_event, epc)
            self.comm_partial_event._context['lot'] = self.lot_number
            self.comm_partial_event._context['exp_date'] = self.exp_date
            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_partial_event)
        else:
            # A commissioning event for the Cartons does exist
            # Add the epc to the epc_list of the event.
            self.comm_partial_event.epc_list.append(epc)


    def _create_comm_partial_event(self, epcis_event, epc):

        # the event comming in is an AggregationEvent because the partial can only be discovered
        # by watching the aggregation events in the handle_aggregation method. So to make sure
        # the record and event times are in sync with the commissioning events, get a ref to
        # the first object event and use that record and event time.
        try:
            evt = self._object_events[0]
            record_time = evt.record_time
            event_time = evt.event_time
        except:
            # if there are no events in _object_events
            # fall back to the epcis_event and adjust the times down
            evt = epcis_event
            t = datetime.datetime.strptime(epcis_event.record_time, '%Y-%m-%dT%H:%M:%SZ')
            dt = t - timedelta(seconds=10)
            record_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            event_time = record_time

        ret_val = template_events.ObjectEvent(
            epc_list=[epc],
            record_time=record_time,
            event_time=event_time,
            event_timezone_offset=evt.event_timezone_offset,
            action=evt.action,
            biz_step=BusinessSteps.commissioning.value,
            disposition=Disposition.active.value,
            read_point=evt.read_point,
            biz_location=evt.biz_location,
            template=self._obj_template
        )

        return ret_val

    def _add_pallet(self, epcis_event, epc):

        if self.comm_pallets_event is None:
           # A commissioning event for the Pallets does not exist
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
                             template=self._obj_template
                        )

            self.comm_pallets_event._context['lot'] = self.lot_number
            self.comm_pallets_event._context['exp_date'] = self.exp_date

            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_pallets_event)
        else:
            # A commissioning event for the Cartons does exist
            # Add the epc to the epc_list of the event.
            self.comm_pallets_event.epc_list.append(epc)

    def _add_each(self, epcis_event, epc):

        if self.comm_eaches_event is None:
           # A commissioning event for the Eaches does not exist
           # Create one
            self.comm_eaches_event = self._create_comm_eaches(epcis_event, epc)
            self.comm_eaches_event._context['lot'] = self.lot_number
            self.comm_eaches_event._context['exp_date'] = self.exp_date
            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_eaches_event)
        else:
            # A commissioning event for the Eaches does exist
            # Add the epc to the epc_list of the event.
            self.comm_eaches_event.epc_list.append(epc)

    def _create_comm_eaches(self, epcis_event, epc):
        ret_val = template_events.ObjectEvent(
            epc_list=[epc],
            record_time=epcis_event.record_time,
            event_time=epcis_event.event_time,
            event_timezone_offset=epcis_event.event_timezone_offset,
            action=epcis_event.action,
            biz_step=BusinessSteps.commissioning.value,
            disposition=Disposition.active.value,
            read_point=epcis_event.read_point,
            biz_location=epcis_event.biz_location,
            template=self._obj_template
        )

        return ret_val

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
    def gtin(self):
        return self._gtin

    @property
    def ndc(self):
        return self._ndc

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

    @property
    def event_time(self):
        return self._event_time

    @property
    def time_zone_offset(self):
        return self._time_zone_offset

    @property
    def record_time(self):
        return self._record_time


class TraxeedIRISParser(FlexibleNSParser):

    def __init__(self, data, reg_ex):

        self._ssccs = []  # internal list to hold collected SSCCs
        self._quantity = 0
        self._po = ""
        self._regEx = re.compile(reg_ex)
        self._lot_number = ""
        self._gtin = ""
        self._ndc = ""
        self._exp_date = ""
        self._biz_location = ""
        self._read_point = ""
        self._event_time = None
        self._time_zone_offset = None
        self._record_time = None
        self._object_events = []
        self._aggregation_events = []
        self.comm_eaches_event = None
        self.comm_cartons_event = None
        self.comm_partial_event = None
        self.comm_pallets_event = None
        env = get_default_environment()
        temp = env.get_template('traxeed/tx_rf_object_events.xml')
        self._obj_template = temp
        # call the base constructor with the stream
        super(TraxeedIRISParser, self).__init__(stream=data)


    def handle_object_event(self, epcis_event: template_events.ObjectEvent):

        if epcis_event.ilmd is not None:
            for item in epcis_event.ilmd:
                if item.name == 'lotNumber':
                    self._lot_number = item.value
                elif item.name == "itemExpirationDate":
                    self._exp_date = item.value

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
                        parts = epc.split('.')
                        if parts[1].startswith('1'):
                            # Add to Eaches commissioning Event
                            # adjust the quantity
                            self._quantity = self._quantity + 1
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
                      self.comm_partial_event =  self._add_partial(epcis_event, epc)
                      self.comm_pallets_event.epc_list.remove(epc)


        self._time_zone_offset = epcis_event.event_timezone_offset
        try:
            t = datetime.datetime.strptime(epcis_event.record_time,'%Y-%m-%dT%H:%M:%SZ')
        except:
            t = datetime.datetime.strptime(epcis_event.record_time, '%Y-%m-%dT%H:%M:%S.%f')
        dt = t + timedelta(seconds=10)
        epcis_event.record_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        epcis_event.event_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        self._record_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        self._event_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        self._aggregation_events.append(epcis_event)


    def _add_carton(self, epcis_event, epc):

        if self.comm_cartons_event is None:
           # A commissioning event for the Cartons does not exist
           # Create one
            self.comm_cartons_event = self._create_comm_cartons_event(epcis_event, epc)
            self.comm_cartons_event._context['lot'] = self.lot_number
            self.comm_cartons_event._context['exp_date'] = self.exp_date
            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_cartons_event)
        else:
            # A commissioning event for the Cartons does exist
            # Add the epc to the epc_list of the event.
            self.comm_cartons_event.epc_list.append(epc)

    def _create_comm_cartons_event(self, epcis_event, epc):

        ret_val = template_events.ObjectEvent(
            epc_list=[epc],
            record_time=epcis_event.record_time,
            event_time=epcis_event.event_time,
            event_timezone_offset=epcis_event.event_timezone_offset,
            action=epcis_event.action,
            biz_step=BusinessSteps.commissioning.value,
            disposition=Disposition.active.value,
            read_point=epcis_event.read_point,
            biz_location=epcis_event.biz_location,
            template=self._obj_template
        )

        return ret_val

    def _add_partial(self, epcis_event, epc):

        if self.comm_partial_event is None:
            # A commissioning event for the Partial Cartons does not exist
            # Create one
            self.comm_partial_event = self._create_comm_partial_event(epcis_event, epc)
            self.comm_partial_event._context['lot'] = self.lot_number
            self.comm_partial_event._context['exp_date'] = self.exp_date
            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_partial_event)
        else:
            # A commissioning event for the Cartons does exist
            # Add the epc to the epc_list of the event.
            self.comm_partial_event.epc_list.append(epc)


    def _create_comm_partial_event(self, epcis_event, epc):

        # the event comming in is an AggregationEvent because the partial can only be discovered
        # by watching the aggregation events in the handle_aggregation method. So to make sure
        # the record and event times are in sync with the commissioning events, get a ref to
        # the first object event and use that record and event time.
        try:
            evt = self._object_events[0]
            record_time = evt.record_time
            event_time = evt.event_time
        except:
            # if there are no events in _object_events
            # fall back to the epcis_event and adjust the times down
            evt = epcis_event
            t = datetime.datetime.strptime(epcis_event.record_time, '%Y-%m-%dT%H:%M:%SZ')
            dt = t - timedelta(seconds=10)
            record_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            event_time = record_time

        ret_val = template_events.ObjectEvent(
            epc_list=[epc],
            record_time=record_time,
            event_time=event_time,
            event_timezone_offset=evt.event_timezone_offset,
            action=evt.action,
            biz_step=BusinessSteps.commissioning.value,
            disposition=Disposition.active.value,
            read_point=evt.read_point,
            biz_location=evt.biz_location,
            template=self._obj_template
        )

        return ret_val

    def _add_pallet(self, epcis_event, epc):

        if self.comm_pallets_event is None:
           # A commissioning event for the Pallets does not exist
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
                             template=self._obj_template
                        )
            self.comm_pallets_event._context['lot'] = self.lot_number
            self.comm_pallets_event._context['exp_date'] = self.exp_date
            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_pallets_event)
        else:
            # A commissioning event for the Cartons does exist
            # Add the epc to the epc_list of the event.
            self.comm_pallets_event.epc_list.append(epc)

    def _add_each(self, epcis_event, epc):

        if self.comm_eaches_event is None:
           # A commissioning event for the Eaches does not exist
           # Create one
            self.comm_eaches_event = self._create_comm_eaches(epcis_event, epc)
            self.comm_eaches_event._context['lot'] = self.lot_number
            self.comm_eaches_event._context['exp_date'] = self.exp_date
            # Add to the Object Events List of the Parser
            self._object_events.append(self.comm_eaches_event)
        else:
            # A commissioning event for the Eaches does exist
            # Add the epc to the epc_list of the event.
            self.comm_eaches_event.epc_list.append(epc)

    def _create_comm_eaches(self, epcis_event, epc):
        ret_val = template_events.ObjectEvent(
            epc_list=[epc],
            record_time=epcis_event.record_time,
            event_time=epcis_event.event_time,
            event_timezone_offset=epcis_event.event_timezone_offset,
            action=epcis_event.action,
            biz_step=BusinessSteps.commissioning.value,
            disposition=Disposition.active.value,
            read_point=epcis_event.read_point,
            biz_location=epcis_event.biz_location,
            template=self._obj_template
        )

        return ret_val

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
    def gtin(self):
        return self._gtin

    @property
    def ndc(self):
        return self._ndc

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

    @property
    def event_time(self):
        return self._event_time

    @property
    def time_zone_offset(self):
        return self._time_zone_offset

    @property
    def record_time(self):
        return self._record_time
