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
# Copyright 2018 SerialLab Corp.  All rights reserved.
from datetime import datetime


from quartet_integrations.extended.environment import get_default_environment
from EPCPyYes.core.v1_2 import template_events, json_encoders
from EPCPyYes.core.v1_2.events import ErrorDeclaration, Action
from EPCPyYes.core.v1_2.template_events import TemplateMixin





class AppendedShippingObjectEvent(template_events.ObjectEvent):

    def __init__(self, event_time: datetime = datetime.utcnow().isoformat(),
                 event_timezone_offset: str = '+00:00',
                 record_time: datetime = None, action: str = Action.add.value,
                 epc_list: list = None, biz_step=None, disposition=None,
                 read_point=None, biz_location=None, event_id: str = None,
                 error_declaration: ErrorDeclaration = None,
                 source_list: list = None, destination_list: list = None,
                 business_transaction_list: list = None, ilmd: list = None,
                 quantity_list: list = None,
                 render_xml_declaration=None,
                 template=None,
                 qty=0):

        self._qty = qty
        env = get_default_environment()
        template = env.from_string(template)

        super().__init__(event_time, event_timezone_offset, record_time,
                         action, epc_list, biz_step, disposition, read_point,
                         biz_location, event_id, error_declaration,
                         source_list, destination_list,
                         business_transaction_list, ilmd, quantity_list, env,
                         template, render_xml_declaration)

