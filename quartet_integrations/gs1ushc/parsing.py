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
from quartet_output import parsing
from quartet_integrations.gs1ushc import mixins


class BusinessOutputParser(mixins.ConversionMixin,
                           parsing.BusinessOutputParser):
    """
    This parser implements the GS1 USHC parsing logic found within
    the quartet_integrations.mixins.ConversionMixin class and will
    take inbound USHC and store it as EPCIS 1.2 ILMD and Source /
    Destination types when possible.  Overrides the default behavior of the
    BusinessOutputParser in the quartet_output class.
    """

    def handle_object_event(self, epcis_event: yes_events.ObjectEvent):
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
