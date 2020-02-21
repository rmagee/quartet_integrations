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
from quartet_integrations.oracle.parsing import MasterMaterialParser, \
    TradingPartnerParser
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
            data, info_func=self.info
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


class TradeItemNumberRangeImportStep(TradeItemImportStep):
    """
    Inherits from the TradeItemImport step and will, along with creating
    any trade item data, will create SerialBox number pools with randomized
    ranges set to randomize from 1 to 999,999,999,999.

    Before executing this step, make sure you have the following configured
     in you system:

    *   In Master Data, make sure you have all company prefixes that represent
        the companies you are importing configured in the step parameters of
        the import rule.  See the quartet_integrations.oracle.steps.TradeItemNumberRangeImportStep
        for more information on this.  The company prefix parameters are part
        of the parent class `TradeItemImportStep`.
    *   Make sure you have run the management command that creates the
        OPSM GTIN Response Rule.  This is the
        `python manage.py create_opsm_gtin_range`.  This will create a
        reference implementation number range as well which you can delete if
        you do not need it.
    """

    def __init__(self, db_task: models.Task, **kwargs):
        self.minimum = int(self.get_or_create_parameter(
            "Minimum Number", "1", "The minimum number for each range to "
                                   "randomize from."
        ))
        self.maximum = int(self.get_or_create_parameter(
            "Maximum Number", "999999999999", "The maximum number to "
                                              "randomize to."
        ))
        self.response_rule_name = self.response_rule_name = \
            self.get_or_create_parameter(
                "Response Rule Name",
                "OPSM GTIN Response Rule",
                "The name of the Response Rule to "
                "associate with the new number ranges."
            )
        self.threshold = int(self.get_or_create_parameter(
            "Threshold",
            "75000",
            "The maximum number of serial numbers that can be requested at "
            "once."
        ))
        super().__init__(db_task, **kwargs)

    def execute(self, data, rule_context: RuleContext):
        self.info('Invoking the parser.')
        company_records = self.get_company_records()
        MasterMaterialParser(company_records).parse(
            data, info_func=self.info, minimum=self.minimum,
            maximum=self.maximum, response_rule_name=self.response_rule_name,
            create_randomized_range=True,
            threshold=self.threshold
        )

    @property
    def declared_parameters(self):
        params = super().declared_parameters
        params['Minimum Number'] = 'The minimum number for each range to ' \
                                   'randomize from'
        params['Maximum Number'] = "The maximum number to randomize to."
        params['Reponse Rule Name'] = ("Default: OPSM GTIN Response Rule. "
                                       "The name of the Response Rule to "
                                       "associate with the new number ranges.")
        params["Threshold"] = "The maximum number of serial numbers " \
                              "that can be requested at once.  Default: 75,000"

        return params

    def on_failure(self):
        super().on_failure()


class TradingPartnerImportStep(Step):
    """
    Imports trading partner data in the format of the company_mappings file
    in the unit tests test/data directory of the main python project.
    """

    def execute(self, data, rule_context: RuleContext):
        self.info('Invoking the parser...')
        TradingPartnerParser().parse(data, self.info)

    def on_failure(self):
        pass

    def declared_parameters(self):
        return {}
