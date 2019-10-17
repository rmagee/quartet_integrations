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
from quartet_capture.models import Filter, RuleFilter, Rule, Step
from quartet_integrations.management.commands import utils


class Command(base.BaseCommand):
    help = 'Creates an OPSM capture rule and a filter to route to a rule ' \
           'that can be reconfigured later.'

    def handle(self, *args, **options):
        opsm_rule = Rule.objects.create(
            name='OPSM Capture',
            description='The OPSM Capture rule.'
        )
        Step.objects.create(
            rule=opsm_rule,
            name='Parse Optel Data',
            step_class='quartet_integrations.optel.steps.ConsolidationParsingStep',
            order=1,
            description='Parses optel EPCIS and lot batch info into the '
                        'database.  Consolidates all of the object events '
                        'into one to make parsing more efficient.'
        )
        filter = Filter.objects.create(
            name='opsm',
            description='The default filter for OPSM.'
        )
        RuleFilter.objects.create(
            filter=filter,
            name='default',
            search_value='<epcis',
            search_type='search',
            default=True,
            break_on_true=True,
            order=1,
            rule=opsm_rule
        )
