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
    help = 'Creates a reference implementation of a GTIN OPSM number ' \
           'range integrated ' \
           'with SerialBox/QU4RTET.'

    def handle(self, *args, **options):
        try:
            utils.create_random_range()
        except Exception as e:
            'Random range not created %s.' % str(e)
        try:
            utils.create_gtin_response_rule()
        except Exception as e:
            'GTIN response rule not created: %s' % str(e)
        try:
            utils.create_trade_item()
        except Exception as e:
            'Test Trade item not created: %s' % str(e)



