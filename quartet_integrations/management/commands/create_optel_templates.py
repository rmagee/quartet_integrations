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
from django.db.utils import IntegrityError

from quartet_capture.models import Rule, Step, StepParameter
from quartet_templates.models import Template


class Command(base.BaseCommand):
    help = 'Creates the optel templates for use in number range response ' \
           'rules.'

    def handle(self, *args, **options):
        self.create_range_templates()
        self.create_random_templates()
        self.create_sequential_rules()
        self.create_random_rules()

    def create_range_templates(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 '../../../tests/data/tracelink/SN_Response_SGTIN_Random.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            try:
                Template.objects.create(
                    name='Optel GTIN Sequential Response',
                    content=content,
                    description='The optel response GTIN template'
                )
            except IntegrityError:
                print('Template Optel GTIN Range Response already exists.')

        data_path = os.path.join(curpath,
                                 '../../../tests/data/tracelink/SN_Response_SSCC_Range.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            try:
                Template.objects.create(
                    name='Optel SSCC Sequential Response',
                    content=content,
                    description='The optel response SSCC template'
                )
            except IntegrityError:
                print('Template Optel SSCC Range Response already exists.')

    def create_random_templates(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 '../../../tests/data/tracelink/SN_Response_SGTIN_Random.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            try:
                Template.objects.create(
                    name='Optel GTIN Random Response',
                    content=content,
                    description='The optel random GTIN response template'
                )
            except IntegrityError:
                print('Template Optel GTIN Random Response already exists.')

        data_path = os.path.join(curpath,
                                 '../../../tests/data/tracelink/SN_Response_SSCC_Random.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            try:
                Template.objects.create(
                    name='Optel SSCC Random Response',
                    content=content,
                    description='The optel random SSCC response template'
                )
            except IntegrityError:
                print('Template Optel SSCC Random Response already exists.')

    def create_sequential_rules(self):
        try:
            rule = Rule.objects.create(
                name='Optel GTIN Sequential Number Reply',
                description='Optel Sequential GTIN Number Reply'
            )
            template_step = Step.objects.create(
                name='Format With Template',
                rule=rule,
                step_class='quartet_templates.steps.TemplateStep',
                description='Renders a template with  provided serial numbers',
                order=1
            )
            StepParameter.objects.create(
                name='Template Name',
                value='Optel GTIN Sequential Response',
                step=template_step
            )
        except IntegrityError:
            print('Optel Sequential Number Reply rule already exists.')
        try:
            rule = Rule.objects.create(
                name='Optel SSCC Sequential Number Reply',
                description='Optel Sequential SSCC Number Reply'
            )
            template_step = Step.objects.create(
                name='Format With Template',
                rule=rule,
                step_class='quartet_templates.steps.TemplateStep',
                description='Renders a template with  provided serial numbers',
                order=1
            )
            StepParameter.objects.create(
                name='Template Name',
                value='Optel SSCC Sequential Response',
                step=template_step
            )
        except IntegrityError:
            print('Optel Sequential SSCC Number Reply rule already exists.')

    def create_random_rules(self):
        try:
            rule = Rule.objects.create(
                name='Optel GTIN Random Number Reply',
                description='unit test'
            )
            template_step = Step.objects.create(
                name='Format With Template',
                rule=rule,
                step_class='quartet_templates.steps.TemplateStep',
                description='Renders a template with  provided serial numbers',
                order=1
            )
            StepParameter.objects.create(
                name='Template Name',
                value='Optel GTIN Random Response',
                step=template_step
            )
        except IntegrityError:
            print('Optel GTIN Random Number Reply rule already exists')
        try:
            rule = Rule.objects.create(
                name='Optel SSCC Random Number Reply',
                description='unit test'
            )
            template_step = Step.objects.create(
                name='Format With Template',
                rule=rule,
                step_class='quartet_templates.steps.TemplateStep',
                description='Renders a template with  provided serial numbers',
                order=1
            )
            StepParameter.objects.create(
                name='Template Name',
                value='Optel SSCC Random Response',
                step=template_step
            )
        except IntegrityError:
            print('Optel SSCC Random Number Reply rule already exists.')
