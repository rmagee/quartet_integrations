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
from EPCPyYes.core.v1_2 import events as yes_events
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from quartet_integrations.gs1ushc import mixins
from quartet_output import parsing
from quartet_output.models import EPCISOutputCriteria


class BusinessOutputParser(mixins.ConversionMixin,
                           parsing.BusinessOutputParser):
    """
    This parser implements the GS1 USHC parsing logic found within
    the quartet_integrations.mixins.ConversionMixin class and will
    take inbound USHC and store it as EPCIS 1.2 ILMD and Source /
    Destination types when possible.  Overrides the default behavior of the
    BusinessOutputParser in the quartet_output class.
    """

    def __init__(self, stream, epcis_output_criteria: EPCISOutputCriteria,
                 event_cache_size: int = 1024,
                 recursive_decommission: bool = True, skip_parsing=False):
        super().__init__(stream, epcis_output_criteria, event_cache_size,
                         recursive_decommission, skip_parsing)
        self.lot = None
        self.expiry = None

    def handle_object_event(self, epcis_event: yes_events.ObjectEvent):
        epcis_event.event_time.replace('+00:00', 'Z')
        epcis_event.record_time.replace('+00:00', 'Z')
        super().handle_object_event(epcis_event)


class SimpleOutputParser(mixins.ConversionMixin, parsing.SimpleOutputParser):
    """
    This parser implements the GS1 USHC parsing logic found within
    the quartet_integrations.mixins.ConversionMixin class and will
    take inbound USHC and store it as EPCIS 1.2 ILMD and Source /
    Destination types when possible.  Overrides the default behavior of
    the SimpleOutputParser in the quartet_output package.
    """
    pass
