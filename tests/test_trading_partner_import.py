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

from django.test import TransactionTestCase

from quartet_capture.models import Rule, Step
from quartet_capture.tasks import create_and_queue_task
from quartet_masterdata.models import Location, Company

class ImportTradingPartnerTestCase(TransactionTestCase):

    def create_rule(self):
        rule = Rule.objects.create(
            name='Trading Partner Import',
            description='unit test rule'
        )
        step = Step.objects.create(
            name='Parse data',
            step_class='quartet_integrations.oracle.steps.TradingPartnerImportStep',
            description='unit test step',
            order=1,
            rule=rule
        )

    def test_import_trading_partners(self):
        self.create_rule()
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(curpath, 'data/company_mappings.csv')

        with open(file_path, "rb") as f:
            create_and_queue_task(
                data=f.read(),
                rule_name="Trading Partner Import",
                run_immediately=True
            )
        self.assertGreater(
            Company.objects.all().count(), 0
        )
        self.assertGreater(
            Location.objects.all().count(), 0
        )

