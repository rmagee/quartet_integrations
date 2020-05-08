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

import abc
import sqlite3
import time
from lxml import etree, objectify

from list_based_flavorpack.models import ListBasedRegion
from list_based_flavorpack.processing_classes.third_party_processing.rules import get_region_table
from quartet_capture import models
from quartet_capture.rules import RuleContext, Step
from quartet_integrations.oracle.steps import TradeItemNumberRangeImportStep
from quartet_integrations.mmd.parsing import PartnerParser, PartnerMMDParser
from serialbox import models as sb_models


class PartnerParsingStep(Step):
    """
    Step that parses the Company Information from a provided .csv file
    """
    @property
    def declared_parameters(self):
        return {}

    def execute(self, data, rule_context: RuleContext):
        PartnerParser().parse(data)

    def on_failure(self):
        pass

class TradeItemImportStep(TradeItemNumberRangeImportStep):

    def execute(self, data, rule_context: RuleContext):
        self.info('Invoking the parser.')
        replenishment_size = self.get_integer_parameter('Replenishment Size',
                                                        2000)
        secondary_replenishment_size = self.get_integer_parameter(
            'Secondary Replenishment Size', int(replenishment_size / 2))

        PartnerMMDParser().parse(
            data,
            info_func=self.info,
            response_rule_name=self.get_parameter('Response Rule Name', None,
                                                  True),
            threshold=75000,

            sending_system_gln=self.get_parameter('Sending System GLN', None,
                                                  False),
            replenishment_size=replenishment_size,
            secondary_replenishment_size=secondary_replenishment_size
        )

        @property
        def declared_parameters(self):
            params = super().declared_parameters

            params[
                'Sending System GLN'] = 'The GLN that will be used as the "sending systmem' \
                                        ' during template rendering for tracelink.',
            params[
                'Replenishment Size'] = 'The size of the request to the external ' \
                                        'system.'
            params[
                'Secondary Replenishment Size'] = 'To request a smaller amount ' \
                                                  'for secondary packaging use ' \
                                                  'this.'
            return params
