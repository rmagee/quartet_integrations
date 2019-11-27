import os
from django.test import TestCase
from django.utils.translation import gettext as _
from django.db.utils import IntegrityError
from quartet_capture import models
from quartet_output.models import EndPoint, EPCISOutputCriteria, \
    AuthenticationInfo
from quartet_templates.models import Template
from quartet_capture.tasks import execute_rule
from quartet_output.steps import ContextKeys


class TestAddShipping(TestCase):


    def test_add_shipping_step(self):

        tr = TestRule()
        epcis_rule = tr.create_rule(rule_name='Add Shipping Event')
        tr.create_template()
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/comm_agg_epcis.xml')
        task = self._create_task(epcis_rule)
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), task)

        message = context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value]

        self.assertTrue(str(message).index("ObjectEvent") > 0)
        self.assertTrue(str(message).index("shipping") > 0)
        self.assertTrue(str(message).index("in_transit") > 0)

    def _create_task(self, rule):
        task = models.Task()
        task.rule = rule
        task.name = 'unit test task'
        task.save()
        return task


class TestRule():

    def create_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/ext-add-shipping.xml')
        with open(data_path, 'r') as f:
            content = f.read()
            Template.objects.create(
                name='Shipping Event Template',
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
            rule = models.Rule.objects.create(
                name=rule_name,
                description='Will Proccess the Inbound Message for Processing.'
            )

            # Output Parsing Step
            parse_step = models.Step.objects.create(
                name=_('Parse EPCIS'),
                description=_(
                    'Parse and insepect EPCIS events using output criteria.'),
                step_class='quartet_output.steps.OutputParsingStep',
                order=1,
                rule=rule

            )

            models.StepParameter.objects.create(
                step=parse_step,
                name='Run Immediately',
                value=True
            )

            # Parameter for Output Criteria
            models.StepParameter.objects.create(
                name='EPCIS Output Criteria',
                step=parse_step,
                value='Add Shipment Output',
                description='This is the name of the EPCIS Output Criteria record to use.'

            )

            models.StepParameter.objects.create(
                name='LooseEnforcement',
                step=parse_step,
                value=False,
                description=''
            )

            add_shipment_step = models.Step.objects.create(
                name='Add Shipping Event',
                description='Adds a Shipping Event to the Incoming EPCIS',
                order=2,
                step_class='quartet_integrations.extended.steps.AppendShippingStep',
                rule=rule
            )

            models.StepParameter.objects.create(
                step=add_shipment_step,
                name='Template Name',
                value='Shipping Event Template',
                description=_(
                    'The name of the template to use.')
            )

            models.StepParameter.objects.create(
                step=add_shipment_step,
                name='Quantity RegEx',
                value='^urn:epc:id:sgtin:[0-9]{6,12}\.[0-9]{1,7}',
                description=_(
                    'The regex to look up item-levels with to determine count.')
            )

            output_step = models.Step.objects.create(
                name=_('Queue Outbound Message'),
                description=_('Creates a Task for sending any outbound data'),
                step_class='quartet_output.steps.CreateOutputTaskStep',
                order=5,
                rule=rule
            )

            models.StepParameter.objects.create(
                step=output_step,
                name='Output Rule',
                value='Transport Rule'
            )

            models.StepParameter.objects.create(
                step=output_step,
                name='Run Immediately',
                value=True
            )

            self._create_transport_rule()
            return rule

    def _create_transport_rule(self, rule_name='Transport Rule'):
        try:
            trule = models.Rule.objects.create(
                name=rule_name,
                description=_(
                    'An output Rule for any data filtered by EPCIS Output Criteria '
                    'rules.')
            )

            models.Step.objects.create(
                name=_('Send Data'),
                description=_(
                    'This will send the task message using the source EPCIS Output '
                    'Critria EndPoint and Authentication Info.'),
                step_class='quartet_output.steps.TransportStep',
                order=1,
                rule=trule
            )
        except IntegrityError:
            trule = models.Rule.objects.get(name=rule_name)
        return trule

    def _create_output_criteria(self, endpoint, auth):
        try:
            EPCISOutputCriteria.objects.create(
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
            endpoint = EndPoint.objects.create(
                name='Local Server',
                urn=_('http://localhost')
            )
        except IntegrityError:
            print('Endpoint already exists.')
            endpoint = EndPoint.objects.get(name='Local Server')

        return endpoint

    def _create_authentication(self):
        try:
            auth = AuthenticationInfo.objects.create(
                username='Test User',
                password='Password',
                type='Digest',
                description=_('A test user'))
        except IntegrityError:
            print('Authentication info already exists.')
            auth = AuthenticationInfo.objects.get(username='Test User')

        return auth
