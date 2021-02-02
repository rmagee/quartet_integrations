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
# Copyright 2021 SerialLab Corp.  All rights reserved.
from EPCPyYes.core.v1_2 import template_events
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from eparsecis.eparsecis import EPCISParser

class FailedMessageParser(EPCISParser):
    def __init__(self, stream,
                 header_namespace='http://www.unece.org/cefact/namespaces/StandardBusinessDocumentHeader'):
        super().__init__(stream, header_namespace)
        self.biz_transaction = None
        self.epc_list = None
        self.shipping_event = False

    def handle_object_event(self, epcis_event: template_events.ObjectEvent):
        # now we have the failed event
        # lets make sure it is a shipping event
        if epcis_event.biz_step == BusinessSteps.shipping.value:
            self.shipping_event = True
            self.epc_list = epcis_event.epc_list
            # before we grab  any business transactions we check to see if
            # there are any
            if len(epcis_event.business_transaction_list) > 0:
                # now we most likely have the sales order number
                self.biz_transaction = \
                    epcis_event.business_transaction_list[0].biz_transaction
