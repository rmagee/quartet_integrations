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

from django.core.management import base
from quartet_capture.models import Filter, RuleFilter, Rule, Step, \
    StepParameter
from quartet_masterdata.models import Company


class Command(base.BaseCommand):
    help = 'Creates an Oracle master material import rule that accepts ' \
           'data in an excel spreadsheet format.'

    def handle(self, *args, **options):
        self.create_companies()
        self.create_rule()

    def create_rule(self):
        rule = Rule.objects.create(
            name='Oracle Master Material Import',
            description='Imports oracle master material spreadsheet and '
                        'creates Trade Item records.'
        )
        step = Step.objects.create(
            name='Import Spreadsheet Data',
            description='Convert the spreadsheet data to Trade Item '
                        'records.',
            step_class='quartet_integrations.oracle.steps.TradeItemNumberRangeImportStep',
            rule=rule,
            order=1
        )
        StepParameter.objects.create(
            name='Company Prefix 1',
            value='0377777',
            step=step
        )
        StepParameter.objects.create(
            name='Company Prefix 2',
            value='0347771',
            step=step
        )
        return rule

    def create_companies(self):
        """
        creates the example company records
        :return: None
        """
        Company.objects.create(
            name='Example Company for Oracle Import',
            gs1_company_prefix='0347771'
        )
        Company.objects.create(
            name='Example Company for Oracle Import',
            gs1_company_prefix='0377777'
        )
