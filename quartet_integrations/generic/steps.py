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
# Copyright 2020 SerialLab Corp.  All rights reserved.
from quartet_capture.rules import Step, RuleContext


class MyStep(Step):
    def execute(self, data, rule_context: RuleContext):
        self.debug('Executing task...using data %s', data)
        message = self.get_or_create_parameter('Message',
                                               'There was no message defined')
        self.debug('This is the message: %s', message)
        self.info('Finished')

    @property
    def declared_parameters(self):
        return {
            'Message': 'This is the message to display.'
        }

    def on_failure(self):
        self.error('That was a terrible error.')
