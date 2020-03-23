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
from EPCPyYes.core.v1_2 import template_events
from eparsecis.eparsecis import FlexibleNSParser
from quartet_integrations.frequentz.environment import get_default_environment

"""
    The FrequentzOutputParser parses EPCIS from OPSM and collects the data points from the
    incoming EPCIS for use in the FrequentzOutputStep.
"""


class FrequentzOutputParser(FlexibleNSParser):
    """
        ctor
    """

    def __init__(self, data):

        self._epcs = []

        self._lot_number = ""
        self._product_code = ""
        self._exp_date = ""
        self._biz_location = ""
        self._read_point = ""
        self._object_events = []
        self._aggregation_events = []

        env = get_default_environment()
        temp = env.get_template('frequentz/frequentz_object_event.xml')
        self._template = temp
        # call the base constructor with the stream
        super(FrequentzOutputParser, self).__init__(stream=data)

    """
        When the base parser sees an ObjectEvent, this method is called
        The event is passed in as a parameter.
    """

    def handle_object_event(self, epcis_event: template_events.ObjectEvent):

        if epcis_event.ilmd is not None:
            for item in epcis_event.ilmd:
                if item.name == 'lotNumber':
                    self._lot_number = item.value
                elif item.name == "itemExpirationDate":
                    self._exp_date = item.value

        self._biz_location = epcis_event.biz_location
        self._read_point = epcis_event.read_point
        new_event = self._create_object_event(epcis_event)
        self._object_events.append(new_event)

    def handle_aggregation_event(
        self,
        epcis_event: template_events.AggregationEvent
    ):

        self._aggregation_events.append(epcis_event)

    def _create_object_event(self, epcis_event):
        """
        Change the template to the frequentz template and return.
        :param epcis_event:
        :return: The original event with a new template assigned.
        """
        epcis_event.template = self._template
        return epcis_event

    @property
    def lot_number(self):
        return self._lot_number

    @property
    def exp_date(self):
        return self._exp_date

    @property
    def object_events(self):
        return self._object_events

    @property
    def aggregation_events(self):
        return self._aggregation_events

    @property
    def read_point(self):
        return self._read_point

    @property
    def biz_location(self):
        return self._biz_location
