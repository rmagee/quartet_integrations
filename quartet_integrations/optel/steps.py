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
import io
from quartet_integrations.sap.steps import SAPParsingStep
from quartet_integrations.optel.parsing import OptelEPCISLegacyParser, ConsolidationParser


class OptelLineParsingStep(SAPParsingStep):
    """
    A QU4RTET parsing step that can parse SAP XML data that contains
    custom event data.
    """

    def _parse(self, data):
        return OptelEPCISLegacyParser(data).parse()


class ConsolidationParsingStep(SAPParsingStep):
    """
    Uses the consolidation parser to handle any bloated optel messages.
    """
    def _parse(self, data):
        return ConsolidationParser(data).parse()
