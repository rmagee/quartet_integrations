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


class TradeItemImportStep(Step):

    def execute(self, data, rule_context: RuleContext):

        self.info('Executing Step {0}'.format(self.db_step.name))

        self.info('{0} Invoking TradeItemImportParser parser.'.format(self.db_step.name))

        TradeItemImportParser().parse(
            data,
            step=self,
            response_rule=self.get_parameter('Response Rule Name', None, True),
            snm_output_criteria=self.get_parameter("SNM Output Criteria", None, False),
            threshold=50000,
            replenishment_size=self.get_parameter('Replenishment Size', 5000, False),
            template_name=self.get_parameter('Request Template Name', None, False),
            processing_parameters=self.get_parameter('Processing Parameters', None, False),
            serialbox_output_criteria=self.get_parameter('SerialBox Output Criteria', None, False),
            minimum_number=self.get_parameter('Minimum Number', 100000000000, False),
            maximum_number=self.get_parameter('Maximum Number', 999999999999, False)
        )

    @property
    def declared_parameters(self):
        self.params = super().declared_parameters
        self.params['Replenishment Size'] = 'The size of the request to the external system.'
        self.params['SNM Output Criteria'] = 'The Name of the Output Criteria used to access an external SNX System'
        self.params['Response Rule Name'] = 'The name of the rule responsible for formatting the response'
        self.params['Minimum Number'] = 'The starting number of the Serial Number Region'
        self.params['Maximum Number'] = 'The ending number of the Serial Number Region.'
        self.params['Request Template Name'] = 'The Template Name for requesting Serial Numbers'
        self.params['SerialBox Output Criteria'] = 'The Output Criteria of Serialbox. Used to test generated Pools and Regions'

        return self.params

    def on_failure(self):
        pass
