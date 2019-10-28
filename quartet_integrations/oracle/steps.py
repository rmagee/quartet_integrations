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
from quartet_capture import models
from quartet_capture.rules import Step, RuleContext
from quartet_integrations.oracle.parsing import MasterMaterialParser
import pandas
from io import BytesIO
from quartet_capture.rules import Step, RuleContext
from quartet_masterdata.models import Company


class TradeItemImportStep(Step):
    """
    Imports master material exports from oracle into the quartet trade
    items.
    """

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        param = self.get_or_create_parameter(
            'Company Prefix 1', '0347771',
            'A company prefix of the company we are importing for. '
            'Trade items must have a company associated with them so '
            'companies must be set up prior to running the import.'
        )
        self.parameters['Company Prefix 1'] = param

    def execute(self, data, rule_context: RuleContext):
        self.info('Invoking the parser.')
        company_records = self.get_company_records()
        MasterMaterialParser(company_records).parse(
            data, self.info, rule_context
        )

    def get_company_records(self):
        company_records = {}
        for name, value in self.parameters.items():
            if name.startswith('Company Prefix'):
                self.info('Looking for company with company prefix %s',
                          value)
                company_records[value] = Company.objects.get(
                    gs1_company_prefix=value
                )
                self.info('Company found.')
        return company_records

    @property
    def declared_parameters(self):
        return {
            'Company_X': 'There can be n number of "Company_X" records, '
                         'for example: Company_1 with a value of "0347771",'
                         'Company_2 with a value of "0345551", etc.  The '
                         'import will look for these company records in '
                         'order to associate with trade items.'
        }

    def on_failure(self):
        pass
