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

from quartet_integrations.management.commands import utils


class Command(base.BaseCommand):
    help = 'Creates a reference implementation of a SSCC OPSM number ' \
           'range integrated ' \
           'with SerialBox/QU4RTET.'

    def handle(self, *args, **options):

        try:
            utils.create_sequential_sscc_range()
        except Exception as e:
            'SSCC sequential range not created %s.' % str(e)
        try:
            utils.create_sscc_template()
        except Exception as e:
            'SSCC template not created: %s' % str(e)
        try:
            utils.create_SSCC_response_rule()
        except Exception as e:
            'Response Rule not created: %s' % str(e)
