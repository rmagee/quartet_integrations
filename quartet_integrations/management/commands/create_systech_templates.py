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
# Copyright 2021 SerialLab Corp.  All rights reserved.
import os
from django.core.management import base

from quartet_capture.models import Rule, Step, StepParameter
from quartet_templates.models import Template


class Command(base.BaseCommand):
    help = 'Creates the systech templates for use in number range response ' \
           'rules.'

    def handle(self, *args, **options):
        self.create_template()
        self.create_random_template()
        self.create_rule()
        self.create_random_rule()

    def create_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 '../../../tests/data/systech/sequential_response_template.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            Template.objects.create(
                name='Systech Sequential Response',
                content=content,
                description='The systech response template'
            )

    def create_random_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 '../../../tests/data/systech/random_response_template.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            Template.objects.create(
                name='Systech Random Response',
                content=content,
                description='The systech random response template'
            )

    def create_rule(self):
        rule = Rule.objects.create(
            name='Systech Sequential Number Reply',
            description='unit test'
        )
        template_step = Step.objects.create(
            name='Format With Template',
            rule=rule,
            step_class='quartet_templates.steps.TemplateStep',
            description='unit test step',
            order=1
        )
        StepParameter.objects.create(
            name='Template Name',
            value='Systech Sequential Response',
            step=template_step
        )
        return rule

    def create_random_rule(self):
        rule = Rule.objects.create(
            name='Systech Random Number Reply',
            description='unit test'
        )
        template_step = Step.objects.create(
            name='Format With Template',
            rule=rule,
            step_class='quartet_templates.steps.TemplateStep',
            description='unit test step',
            order=1
        )
        StepParameter.objects.create(
            name='Template Name',
            value='Systech Random Response',
            step=template_step
        )
        return rule
