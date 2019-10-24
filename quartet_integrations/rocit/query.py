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

    def __init__(self):
        pass

    @staticmethod
    def count_eaches(query, tag_id):

        cnt = 0
        entry = entries.Entry.objects.get(identifier=tag_id)
        agg_evt = query.get_epcis_event(entry.last_aggregation_event)
        for child in agg_evt.child_epcs:
            res = query.get_epcs_by_parent_identifier(child,False)
            cnt = cnt + len(res)
        return cnt

    @staticmethod
    def RetrievePackagingHierarchy(tag_id, send_children, send_product_info):

        gtin = None
        parent_tag = ""
        quantity = 0
        product = None
        lot = ""
        uom=None
        expiry = ""
        status = ""
        state = ""
        document_id = str(random.randrange(1111111, 9999999))
        document_type = "RECADV"
        child_tag_count = 0
        child_tags = []
        send_product_info = (send_product_info is not None and send_product_info.lower() == 'true')
        send_children = (send_children is not None and send_children.lower() == 'true')

        # Create the DBProxy
        query = EPCISDBProxy()

        # Get the entry, then get the last Event the entry participated in.
        entry = query.get_entries_by_epcs(epcs=[tag_id], select_for_update=False)[0]
        last_event = entry.last_event
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
            try:
                # get the children of tag_id

                children = query.get_epcs_by_parent_identifier(identifier=tag_id, select_for_update=False)
                if tag_id.find('sscc') > 0:
                    quantity = RocItQuery.count_eaches(query, tag_id)
                    child_tag_count = len(children)
                elif tag_id.find('sgtin') > 0:
                    quantity = len(children)
                    child_tag_count = quantity

                # build the child_tags array witht he children of tag_id
                for child in children:
                    child_tags.append(child)
                    if send_product_info:
                        if str(tag_id).find('sgtin') > 0 and product is None:
                            gtin = tag_id.split(':')
                            gtin = gtin[4].split('.')
                            gtin = "{0}{1}{2}".format(gtin[1][:1], gtin[0], gtin[1][1:])
                            gtin = check_digit.calculate_check_digit(gtin)
                            product, uom = RocItQuery.get_product_info(gtin)
                        elif str(tag_id).find('sscc') > 0 and product is None:
                            gtin = child.split(':')
                            gtin = gtin[4].split('.')
                            gtin = "{0}{1}{2}".format(gtin[1][:1], gtin[0], gtin[1][1:])
                            gtin = check_digit.calculate_check_digit(gtin)
                            product, uom = RocItQuery.get_product_info(gtin)

                    if len(lot) == 0 and len(expiry) == 0:
                        events = query.get_events_by_entry_identifer(entry_identifier=child)
                        for event in events:
                            ilmds = query.get_ilmd(db_event=event.event)
                            for ilmd in ilmds:
                                if ilmd.name == 'itemExpirationDate':
                                    expiry = ilmd.value
                                elif ilmd.name == 'lotNumber':
                                    lot = ilmd.value

                            if len(lot) > 0 and len(expiry) > 0:
                                break

            except entries.Entry.DoesNotExist:
                # No Children found. This can be ignored.
                pass



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
    def get_product_info(gtin):

        trade_item = None
        product = None
        uom = None
        try:
            trade_item = TradeItem.objects.get(GTIN14=gtin)
            product = trade_item.additional_id
            uom = trade_item.package_uom
        except:
            raise Exception('Trade Item or Unit of Measure not configured in QU4RTET')

        return product, uom


