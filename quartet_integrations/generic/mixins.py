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
from copy import copy
from quartet_epcis.db_api.queries import EPCISDBProxy
from datetime import datetime
from EPCPyYes.core.v1_2 import template_events as events


class ObserveChildrenMixin:

    def create_observation_event(self, event: events.ObjectEvent,
                         use_sources=True,
                         use_destinations=True):
        """
        Will return an observation object event with all of the children
        of the epcs passed in the original event in the event parameter.
        This is usefull if you need to apply certain field events to entries
        by observing them with different locations, destinations, business
        steps, etc.
        :param event: The event containing the parents.
        :param use_sources: Whether or not to use the existing sources in the
            event being passed in.  If so, those sources will be appended
            to the new event before it is returned.
        :param use_destinations: Same as above but with destinations instead
            of sources.
        :return: Returns a new object event with an action of OBSERVE with
            all of the children of the original event included.
        """
        dbp = EPCISDBProxy()
        entries = dbp.get_entries_by_epcs(
            event.epc_list, select_for_update=False
        )
        child_entries = dbp.get_entries_by_parents(
            entries, select_for_update=False
        )
        ob_event = events.ObjectEvent(datetime.utcnow().isoformat())
        ob_event.epc_list = [entry.identifier for entry in child_entries]
        ob_event.action = events.Action.observe.value
        ob_event.source_list = copy(event.source_list) if use_sources else []
        ob_event.destination_list = copy(
            event.destination_list) if use_destinations else []
        return ob_event

