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

import os
from django.test import TestCase

from EPCPyYes.core.v1_2 import template_events as yes_events
from quartet_integrations.sap.parsing import SAPParser

class TestParser(SAPParser):

    def handle_object_event(self, epcis_event: yes_events.ObjectEvent):
        print(epcis_event.render())
        return super().handle_object_event(epcis_event)


class TestEparsecis(TestCase):
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        #logging.basicConfig(level=logging.DEBUG)

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_epcis_file(self):
        curpath = os.path.dirname(__file__)
        parser = TestParser(
            os.path.join(curpath, 'data/sap-epcis.xml'))
        parser.parse()
        parser.get_epcpyyes_object_event()
