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
from django.db.utils import IntegrityError
from django.core.management import base
from quartet_capture import models
from quartet_output.models import EndPoint, EPCISOutputCriteria, \
    AuthenticationInfo
from quartet_templates.models import Template

class Command(base.BaseCommand):
    help = 'Creates an Append Shipping Rule that appends an ObjectEvent with a Shipping bizStep ' \
           'to an EPCIS Document.'

    def handle(self, *args, **options):

        cr = CreateRule()
        cr.create_template()
        cr.create_rule('Append Shipping Rule')


class CreateRule():

    def create_template(self):
        curpath = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '../../../', 'tests'))
        data_path = os.path.join(curpath, 'data/ext-add-shipping.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            Template.objects.update_or_create(
                name='Append Shippment Template',
                content=content,
                description='The shipping event template'
            )

    def create_rule(self, rule_name):

        # Create the Auth, Endpoint, and Output Criteria
        endpoint = self._create_endpoint()
        auth = self._create_authentication()
        self._create_output_criteria(endpoint, auth)

        if not models.Rule.objects.filter(name=rule_name).exists():
            # The Rule
            rule, _ = models.Rule.objects.update_or_create(
                name=rule_name,
                description='Will Proccess the Inbound Message for Processing.'
            )

            # Output Parsing Step
            parse_step, _ = models.Step.objects.update_or_create(
                name='Parse Append Shippment EPCIS',
                description='Parse and insepect EPCIS events using output criteria.',
                step_class='quartet_output.steps.OutputParsingStep',
                order=1,
                rule=rule

            )

            # Parameter for Output Criteria
            models.StepParameter.objects.update_or_create(
                name='Output Criteria',
                step=parse_step,
                value='Add Shipment Output',
                description='This is the name of the EPCIS Output Criteria record to use.'

            )

            models.StepParameter.objects.update_or_create(
                name='LooseEnforcement',
                step=parse_step,
                value=False,
                description=''
            )

            add_shipment_step, _ = models.Step.objects.update_or_create(
                name='Add Append Shippment Event',
                description='Adds a Shipping Event to the Incoming EPCIS',
                order=2,
                step_class='quartet_integrations.extended.steps.AppendShippingStep',
                rule=rule
            )

            models.StepParameter.objects.update_or_create(
                step=add_shipment_step,
                name='Template Name',
                value='Shipping Event Template',
                description='The name of the template to use.'
            )

            models.StepParameter.objects.update_or_create(
                step=add_shipment_step,
                name='Quantity RegEx',
                value='^urn:epc:id:sgtin:[0-9]{6,12}\.0',
                description='The regex to look up item-levels with to determine count.'
            )

            output_step, _ = models.Step.objects.update_or_create(
                name='Queue Append Shippment Outbound Message',
                description='Creates a Task for sending any outbound data',
                step_class='quartet_output.steps.CreateOutputTaskStep',
                order=4,
                rule=rule
            )

            models.StepParameter.objects.update_or_create(
                step=output_step,
                name='Output Rule',
                value='Append Shippment Transport Rule'
            )


            self._create_transport_rule()
            return rule

    def _create_transport_rule(self):

        try:
            trule, _ = models.Rule.objects.update_or_create(
                name='Append Shippment Transport Rule',
                description='An output Rule for any data filtered by EPCIS Output Criteria rules.'
            )

            models.Step.objects.update_or_create(
                name='Send Data',
                description=
                    'This will send the task message using the source EPCIS Output '
                    'Critria EndPoint and Authentication Info.',
                step_class='quartet_output.steps.TransportStep',
                order=1,
                rule=trule
            )
        except IntegrityError:
            trule = models.Rule.objects.get(name='Append Shippment Transport Rule')
        return trule

    def _create_output_criteria(self, endpoint, auth):
        try:
            EPCISOutputCriteria.objects.update_or_create(
                name='Add Shipment Output',
                action='Observe',
                event_type='Object',
                biz_location='urn:epc:id:sgln:0951759.00000.0',
                end_point=endpoint,
                authentication_info=auth
            )
        except IntegrityError:
            print('Criteria already exists.')

    def _create_endpoint(self):
        try:
            endpoint, _ = EndPoint.objects.update_or_create(
                name='Local Server',
                urn= 'http://localhost'
            )
        except IntegrityError:
            print('Endpoint already exists.')
            endpoint = EndPoint.objects.get(name='Local Server')

        return endpoint

    def _create_authentication(self):
        try:
            auth, _ = AuthenticationInfo.objects.update_or_create(
                username='Test User',
                password='Password',
                type='Digest',
                description='A test user')
        except IntegrityError:
            print('Authentication info already exists.')
            auth = AuthenticationInfo.objects.get(username='Test User')

        return auth
