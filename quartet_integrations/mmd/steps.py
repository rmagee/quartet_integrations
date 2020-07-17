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

from quartet_capture.rules import RuleContext, Step
from quartet_integrations.oracle.steps import TradeItemNumberRangeImportStep
from quartet_integrations.mmd.parsing import (
    PartnerParser,
    TradeItemImportParser
)
from serialbox import models as sb_models


class PartnerParsingStep(Step):
    """
    Step that parses the Company Information from a provided .csv file
    """

    @property
    def declared_parameters(self):
        return {}

    def execute(self, data, rule_context: RuleContext):
        PartnerParser().parse(data, info_func=self.info)

    def on_failure(self):
        pass


class TradeItemImportStep(TradeItemNumberRangeImportStep):

    def execute(self, data, rule_context: RuleContext):
        self.info('Invoking the parser.')
        replenishment_size = self.get_integer_parameter('Replenishment Size',
                                                        2000)
        secondary_replenishment_size = self.get_integer_parameter(
            'Secondary Replenishment Size', int(replenishment_size / 2))

        TradeItemImportParser().parse(
            data,
            info_func=self.info,

            response_rule=self.get_parameter('Response Rule Name', None,
                                                  True),

            request_rule=self.get_parameter('Request Rule Name', None,
                                                  True),
            auth_id=self.get_parameter("Auth Id", None, True),
            endpoint=self.get_parameter("Endpoint Name", None, True),
            threshold=5000,

            sending_system_sgln=self.get_parameter('Sending System SGLN', None,
                                                  False),

            list_based=self.get_boolean_parameter("List Based", None, True),

            replenishment_size=replenishment_size,
            range_start=self.get_parameter('Range Start', None, 0),
            range_end=self.get_parameter('Range End', None, 0),
            template_name=self.get_parameter('Template Name', None, None),
        )

    @property
    def declared_parameters(self):
        self.params = super().declared_parameters

        self.params['Sending System SGLN'] = 'The GLN that will be used as the "sending system for the request'
        self.params['Replenishment Size'] = 'The size of the request to the external system.'
        self.params['Auth Id'] = 'The numerical id of the Authentication Object used to access the external SNM system'
        self.params['Endpoint Name'] = 'The Name of the Endpoint used to access the external SNM system'
        self.params['Response Rule Name'] = 'The name of the rule responsible for formatting the response'
        self.params['Request Rule Name'] = 'The name of the rule responsible for requesting the serial numbers'
        self.params['List Based'] = 'Whether or not the Serial Number Range is List-based'
        self.params['Range Start'] = 'The starting number of the Serial Number Region'
        self.params['Range End'] = 'The ending number of the Serial Number Region.'
        self.params['Template Name'] = 'The Template Name for requesting Serial Numbers'


        return self.params

    def on_failure(self):
        pass
