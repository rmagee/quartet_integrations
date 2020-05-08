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

from enum import Enum
from gs123.conversion import URNConverter
from EPCPyYes.core.v1_2 import template_events as events
from EPCPyYes.core.v1_2.events import EPCISBusinessEvent
from quartet_epcis.db_api.queries import EPCISDBProxy
from quartet_masterdata.models import Company, Location
from quartet_masterdata.db import DBProxy
from quartet_capture.rules import RuleContext
from EPCPyYes.core.v1_2.CBV import InstanceLotMasterDataAttribute, \
    ItemLevelAttributeName, LotLevelAttributeName, \
    TradeItemLevelAttributeName, SourceDestinationTypes
from EPCPyYes.core.v1_2.events import Destination, Source


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
        ob_event = events.ObjectEvent()
        ob_event.epc_list = [entry.identifier for entry in child_entries]
        ob_event.action = events.Action.observe.value
        ob_event.source_list = copy(event.source_list) if use_sources else []
        ob_event.destination_list = copy(
            event.destination_list) if use_destinations else []
        return ob_event


class CompanyFromURNMixin:
    """
    Will return a quartet_masterdata Company by inspecting URNs in an
    EPCIS message, grabbing the company prefix and looking up the company
    based on that.  Will use the first company prefix it finds.  Will not
    match against multiple company prefixes.
    """

    def get_company_by_urn(self, epcis_event: events.ObjectEvent,
                           rule_context: RuleContext):
        epc = epcis_event.epc_list[0]
        company_prefix = URNConverter(epc).company_prefix
        try:
            return Company.objects.get(
                gs1_company_prefix=company_prefix)
        except Company.DoesNotExist:
            raise self.CompanyNotFoundError(
                'could not find a company for prefix %s',
                company_prefix)

    class CompanyNotFoundError(Exception):
        pass


class CompanyLocationMixin:
    """
    Will return a company or location model instance by its identifer (GLN 13
    or SGLN.  Useful if you need to inject company or location data into a
    step's logic or the rule context.
    """

    def get_company_by_identifier(
        self,
        epcis_event: EPCISBusinessEvent,
        type=SourceDestinationTypes.owning_party.value,
        source_list=True
    ):
        cur_list = epcis_event.source_list if source_list else epcis_event.destination_list
        attr = 'source' if source_list else 'destination'
        for source_dest in cur_list:
            if source_dest.type == type:
                id = getattr(source_dest, attr)
                try:
                    if len(id) == 13:
                        ret = Company.objects.get(GLN13=id)
                    else:
                        ret = Company.objects.get(SGLN=id)
                    return ret
                except Company.DoesNotExist:
                    raise Company.DoesNotExist('Could not locate a company '
                                               'with the %s id using '
                                               'the GLN or SGLN fields.'
                                               ' Make sure a company is '
                                               ' configured with this id or '
                                               'that the current id being '
                                               'used is correct.' % id)

    def get_location_by_identifier(
        self,
        epcis_event: EPCISBusinessEvent,
        type=SourceDestinationTypes.owning_party.value,
        source_list=True
    ):
        """
        Will look for a Location model instance by identifier.
        :param epcis_event: The event to use to find the identifier
        :param type: The type of SourceDestination to look for
        :param source_list: If true, will look through the source list, if
        false will look through destinations.
        :return: A Location model instance.
        """
        cur_list = epcis_event.source_list if source_list else epcis_event.destination_list
        attr = 'source' if source_list else 'destination'
        for source_dest in cur_list:
            if source_dest.type == type:
                id = getattr(source_dest, attr)
                try:
                    if len(id) == 13:
                        ret = Location.objects.get(GLN13=id)
                    else:
                        ret = Location.objects.get(SGLN=id)
                    return ret
                except Location.DoesNotExist:
                    raise Location.DoesNotExist('Could not locate a company '
                                                'with the %s id using '
                                                'the GLN or SGLN fields.'
                                                ' Make sure a company is '
                                                ' configured with this id or '
                                                'that the current id being '
                                                'used is correct.' % id)
