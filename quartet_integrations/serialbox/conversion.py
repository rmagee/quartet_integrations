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
import json

from quartet_capture import models
from quartet_capture.rules import Step, RuleContext
from quartet_masterdata.db import DBProxy
from gs123.conversion import BarcodeConverter, URNConverter


class OPSMConversion(Step):
    """
    Converts serialbox lists to OPSM URNs using the data in the result.
    """

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.get_or_create_parameter('Company Prefix Length',
                                     '0', 'The lenght of the company prefix '
                                          'to use during URN conversions.'
                                          'if set to zero, the system will '
                                          'look up the company prefix length '
                                          'in the master data in the company '
                                          'and Trade Item areas.')

    def execute(self, data, rule_context: RuleContext):
        """
        Inbound data should be in JSON format.
        :param data: The serial number response from serialbox.
        :param rule_context: The rule context.
        """
        # convert the JSON to a python object
        self.info('Parsing the JSON...')
        sb_response = json.loads(data)
        # first make sure we have a company prefix length we can use
        # check for a step parameter first, then look for the company
        # prefix in the master material if not declared in the step
        self.info('Looking for company prefix information...')
        cp_length = self.get_integer_parameter('Company Prefix Length')
        if cp_length == 0:
            self.info('Trying to get the company prefix by using the region '
                      'machine name / API Key value %s', sb_response.region)
            cp_length = DBProxy().get_company_prefix_length(sb_response.region)
        else:
            self.info('Company prefix length = %s', cp_length)
        numbers = sb_response.numbers
        # if we are dealing with gtins we need to make urn values sans the
        # epc declaration

        return_vals = []
        if len(sb_response.region) == 14:
            self.info('Formatting for GTIN response.')
            # provide a dummy serial number so we can just quickly parse the company prefix
            converter = BarcodeConverter(
                '01%s21%s' % (sb_response.region, '000000000001'), cp_length)
            company_prefix = converter.company_prefix
            indicator = converter.indicator_digit
            item_reference = converter.item_reference
            for number in numbers:
                return_vals.append(
                    '%s.%s.%s%s.%s' % (
                    '0', company_prefix, indicator, item_reference, number)
                )


    def on_failure(self):
        pass

    @property
    def declared_parameters(self):
        return {}
