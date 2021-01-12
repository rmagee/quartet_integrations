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

from django.test import TestCase
from quartet_capture.models import Rule, Step, StepParameter
from quartet_capture.tasks import create_and_queue_task


class MyStepTest(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.create_my_rule()

    def create_my_rule(self):
        rule = Rule.objects.create(
            name='My New Rule',
            description='This is created by the unit test.'
        )
        step = Step.objects.create(
            name='My Step',
            description='This is my unit test step.',
            step_class='quartet_integrations.generic.steps.MyStep',
            order=1,
            rule=rule
        )
        StepParameter.objects.create(
            name='Message',
            value='This is the messsge for the unit test.',
            step=step
        )

    def test_my_new_rule(self):
        task = create_and_queue_task(
            data='this is just junk data for unit test.',
            rule_name='My New Rule',
            run_immediately=True
        )
        self.assertEqual(task.taskmessage_set.count(), 6,
                         'hey, what is going '
                         'on there should only be 6 messages.')
        print(task)
