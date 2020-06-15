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
    PartnerMMDParser,
    FirstTimeUSGenericsGPIImport
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


class FirstTimeUSGenericsGPIImportStep(TradeItemNumberRangeImportStep):


    def execute(self, data, rule_context: RuleContext):
        self.info('Starting Import')
        auth_id = self.get_integer_parameter(
            'Authentication Id', None)
        if auth_id is None:
            msg = "Authentication Id Step Parameter is Not Set on 'FirstTimeUSGenericsGPIImportStep' Step"
            self.error(msg)
            raise Exception(msg)

        response_rule = self.get_parameter(
            'Response Rule Name', "OPSM External GTIN Response Rule")

        request_rule = self.get_parameter(
            'Request Rule Name', "PharmaSecure Serial Numbers")

        endpoint = self.get_parameter(
            'Endpoint', "PharmaSecure SerialNumbers")

        FirstTimeUSGenericsGPIImport().parse(data, info_func=self.info,
                                             auth_id=auth_id,
                                             response_rule=response_rule,
                                             request_rule=request_rule,
                                             endpoint=endpoint);

    def on_failure(self):
        pass

    @property
    def declared_parameters(self):

        self.params[
            'Authentication Id'] = 'The Id of the authentication info ' \
                                        'instance to use to communicate with ' \
                                        'external PharamSecure System.'

        self.params['Response Rule Name'] = 'The Name of the Response Rule that will' \
                                       ' handle formatting the serial number response from PharamSecure.'

        self.params['Request Rule Name'] = 'The Name of the Request Rule that will' \
                                            ' request Serial Numbers from PharamSecure.'

        self.params[
            'Endpoint'] = 'The name of the Endpoint to use to communicate ' \
                          'with PharmaSecure.'
        self.params[
            'Replenishment Size'] = 'The size of the request to the external ' \
                                    'system.'
        return self.params


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
