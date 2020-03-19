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
import traceback
import logging
import uuid
import random
from logging import getLogger
from rest_framework import status
from rest_framework.response import Response
from EPCPyYes.core.v1_2 import helpers
from quartet_epcis.db_api.queries import EPCISDBProxy
from quartet_epcis.models import events, entries, headers
from quartet_masterdata.models import TradeItem, TradeItemField
from gs123 import check_digit

logger = getLogger(__name__)

class RocItQuery():

    @staticmethod
    def RetrievePackagingHierarchy(tag_id, send_children, send_product_info):

        quantity = 0
        product = ""
        uom = ""
        lot = ""
        expiry = ""
        status = ""
        state = ""
        document_id = str(random.randrange(1111111, 9999999))
        document_type = "RECADV"
        child_tag_count = 0
        child_tags = []
        saleable_units = []
        send_children = (send_children is not None and send_children.lower() == 'true')

        # Create the DBProxy
        query = EPCISDBProxy()

        # Get the entry, then get the last Event the entry participated in.
        entry = query.get_entries_by_epcs(epcs=[tag_id], select_for_update=False)[0]
        last_event = entry.last_aggregation_event
        parent_tag = query.get_parent_epc(last_event)

        if parent_tag == tag_id:
           parent_tag = None

        if last_event is not None:
            # If there was a last_event, then get the bizStep (state in the response)
            # And disposition (status in the response)
            try:
                state = last_event.biz_step.split(':')[4]
                if state == 'receiving' or state == 'shipping':
                   state = status.upper()
                else:
                   state = 'COMMISSIONING'
            except:
                raise Exception('Invalid CBV bizStep urn found.')
            try:
                status = last_event.disposition.split(':')[4]
                if status == 'in_transit' or status == 'in_progress':
                   status = status.upper()
                else:
                   status = 'ACTIVE'
            except:
                # disposition may not have been sent in the EPCIS Doc, ignore
                status = 'ACTIVE'

        if send_children:
            # The request is to return the children.
            # get the direct children of the tag_id
            children = query.get_epcs_by_parent_identifier(identifier=tag_id, select_for_update=False)
            child_tag_count = len(children)
            # go through the direct children identifers and collect the lowest saleable units
            for child in children:
                # retrieve the lowest saleable unit from the child
                saleable_units += RocItQuery.get_lowest_saleable_units(query, child)
                # add child to child_tags
                child_tags.append(child)

            if len(saleable_units) == 0:
                # if no saleable_units where located then the searched value, tag_id
                # is a saleable_unit, add it to the salable_units list so the ILMD data
                # can be located.
                saleable_units.append(tag_id)

            # The quantity is the saleable_units count
            quantity = len(saleable_units)

            # go through saleable_units to get the ILMD information
            for id in saleable_units:
                events = query.get_events_by_entry_identifer(entry_identifier=id)
                for event in events:
                    # look for ILMD info
                    ilmds = query.get_ilmd(db_event=event.event)
                    for ilmd in ilmds:
                        if ilmd.name == 'itemExpirationDate':
                            expiry = ilmd.value
                        elif ilmd.name == 'lotNumber':
                            lot = ilmd.value
                        elif ilmd.name == 'additionalTradeItemIdentification':
                            product = ilmd.value
                        elif ilmd.name == 'measurementUnitCode':
                            uom = ilmd.value
                    # if uom, lot, expiry, and product have values, stop going through events
                    if len(lot) > 0 and len(expiry) > 0 and len(uom) > 0 and len(product) > 0:
                       break
                # if uom, lot, expiry, and product have values, stop going through saleable_units
                if len(lot) > 0 and len(expiry) > 0 and len(uom) > 0 and len(product) > 0:
                    break

        # set up the template parameters
        ret_val = {
                    "message_id": str(uuid.uuid4()),
                    "tag_id": tag_id,
                    "parent_tag": parent_tag,
                    "status": status,
                    "state": state,
                    "child_tag_count": child_tag_count,
                    "quantity": quantity,
                    "child_tags": child_tags,
                    "document_id":document_id,
                    "document_type":document_type,
                    "expiry": expiry,
                    "lot": lot,
                    "uom": uom if uom else "" ,
                    "product": product if product else ""
                }

        return ret_val

    @staticmethod
    def get_lowest_saleable_units(query, tag_id):
        ret_val = []
        children = query.get_epcs_by_parent_identifier(identifier=tag_id, select_for_update=False)
        if len(children) == 0:
           ret_val.append(tag_id)
        else:
            for child in children:
                identifiers = RocItQuery.get_lowest_saleable_units(query, child)
                if len(identifiers) == 0:
                    ret_val.append(child)
                ret_val += identifiers
        return ret_val





