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

from django.core.management import call_command, base
from django.db.utils import IntegrityError

from quartet_capture.models import Rule, Step, StepParameter
from quartet_templates.models import Template
from serialbox.models import Pool, ResponseRule
from random_flavorpack import models

def create_random_range():
    try:
        sp1 = Pool.objects.create(
            readable_name='Pharmaprod 20mcg Pills',
            machine_name='00313000007772',
            active=True,
            request_threshold=1000
        )
        models.RandomizedRegion.objects.create(
            readable_name='Pharmaprod 20mcg Pills',
            machine_name='00313000007772',
            start=239380,
            active=True,
            order=1,
            pool=sp1,
            min=1,
            max=999999999999
        )
    except IntegrityError:
        pass

# list conversion then format with template
def create_response_rule():
    rule, created = Rule.objects.get_or_create(
        name='OPSM Response Rule',
        description='OPSM Response Rule (Auto Created)',
    )

    conversion_step, created = Step.objects.get_or_create(
        rule = rule,
        name='List Conversion',
        step_class='quartet_integrations.opsm.steps.ListToUrnConversionStep',
        order=1
    )
    if not created:
        conversion_step.description = 'Convert the list of numbers to ' \
                                      'GTINs or SSCCs for use by OPSM.',

    format_step, created = Step.objects.get_or_create(
        rule=rule,
        name='Format Message',
        description='A message template step.',
        step_class='quartet_templates.steps.TemplateStep',
        order=2
    )
    StepParameter.objects.get_or_create(
        step=format_step,
        name='Template Name',
        value='OPSM GTIN Response Template'
    )

    create_template()
    pool = Pool.objects.get(machine_name='00313000007772')
    response_rule = ResponseRule.objects.get_or_create(
        rule=rule,
        pool=pool,
        content_type='json'
    )


def create_template():
    print('Creating the OPSM GTIN response template...')
    curpath = os.path.dirname(__file__)
    file_path = os.path.join(curpath,
                             '../../templates/opsm/sgtin_response.xml')
    with open(file_path, 'r') as f:
        response_template = Template.objects.get_or_create(
            name='OPSM GTIN Response Template',
            content=f.read()
        )

class Command(base.BaseCommand):
    help = 'Creates a reference implementation of a OPSM number range integrated ' \
           'with SerialBox/QU4RTET.'

    print('Creating a random number range...')
    create_random_range()
    print('Creating the response rule...')
    create_response_rule()
    print('Complete.')
