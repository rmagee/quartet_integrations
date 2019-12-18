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
from django.conf import settings

class TestTraxeed2Tracelink(TestCase):


    def test_traxeed_to_tracelink_step(self):

        tr = TestRule()
        epcis_rule = tr.create_rule()
        tr.create_template()
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/tx_hk_comm_agg_epcis2.xml')
        task = self._create_task(epcis_rule)
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), task)


        comm_agg_epcis = context.context['COMM_AGG_DOCUMENT']
        shipping_epcis = context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value]

        self.assertTrue(str(comm_agg_epcis).index("ObjectEvent") > 0)
        self.assertTrue(str(comm_agg_epcis).index("Aggregation") > 0)
        self.assertTrue(str(shipping_epcis).index("shipping") > 0)


    def _create_task(self, rule):
        task = models.Task()
        task.rule = rule
        task.name = 'unit test comm, agg then ship task'
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

    def create_rule(self):

        # Create the Auth, Endpoint, and Output Criteria
        endpoint = self._create_endpoint()
        auth = self._create_authentication()
        self._create_output_criteria(endpoint, auth)
        rule_name='Send Comm, Agg, then Shipping Event'
        if not models.Rule.objects.filter(name=rule_name).exists():
            # The Rule
            rule = models.Rule.objects.create(
                name=rule_name,
                description='Process inbound EPCIS Create and Send Comm/Agg ObjectEvents then Send Shipping ObjectEvents'
            )

            # Output Parsing Step
            parse_step = models.Step.objects.create(
                name=_('Parse EPCIS'),
                description=_(
                    'Parse and inspect EPCIS events using output criteria.'),
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
                value='Comm Agg Output',
                description='This is the name of the EPCIS Output Criteria record to use.'

            )

            models.StepParameter.objects.create(
                name='LooseEnforcement',
                step=parse_step,
                value=False,
                description=''
            )

            process_traxeed_step = models.Step.objects.create(
                name='Process Traxeed',
                description='Processes incoming Traxeed EPCIS',
                order=2,
                step_class='quartet_integrations.traxeed.steps.ProcessTraxeedStep',
                rule=rule
            )

            models.StepParameter.objects.create(
                step=process_traxeed_step,
                name='Quantity RegEx',
                value='^urn:epc:id:sgtin:[0-9]{6,12}\.[0-9]{1,7}',
                description=_(
                    'The regex to look up item-levels with to determine count.')
            )


            render_tracelink = models.Step.objects.create(
                name='Render TraceLink EPCIS',
                description = 'Renders a Tracelink Compliant EPCIS Document',
                order=3,
                rule = rule,
                step_class='quartet_tracelink.steps.TracelinkOutputStep',
            )

            output_step = models.Step.objects.create(
                name=_('Queue Outbound Message'),
                description=_('Creates a Task for sending any outbound data'),
                step_class='quartet_output.steps.CreateOutputTaskStep',
                order=4,
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

            shipping_step = models.Step.objects.create(
                name='Shipping',
                description=_('Puts together the Shipping EPCIS Document'),
                step_class='quartet_integrations.traxeed.steps.ShipTraxeedStep',
                order=5,
                rule=rule
            )

            models.StepParameter.objects.create(
                step=shipping_step,
                name='Template Name',
                value='Shipping Event Template',
                description=_(
                    'The name of the template to use.')
            )

            # Parameter for Output Criteria
            models.StepParameter.objects.create(
                name='EPCIS Output Criteria',
                step=shipping_step,
                value='Delayed Transport Rule',
                description='This is the name of the Delayed EPCIS Output Criteria record to use.'

            )

            output_step2 = models.Step.objects.create(
                name='Queue Outbound Message',
                description='Creates a Task for sending any outbound data',
                step_class='quartet_output.steps.CreateOutputTaskStep',
                order=6,
                rule=rule
            )

            models.StepParameter.objects.create(
                step=output_step2,
                name='Output Rule',
                value='Transport Rule'
            )

            models.StepParameter.objects.create(
                step=output_step2,
                name='Run Immediately',
                value=True
            )


            self._create_transport_rule()
            self._create_delayed_transport_rule()
            return rule

    def _create_transport_rule(self):
        try:
            rule_name = 'Transport Rule'
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

    def _create_delayed_transport_rule(self):

        try:
            rule_name = 'Delayed Transport Rule'
            trule = models.Rule.objects.create(
                name=rule_name,
                description=
                    'An output Rule for any data filtered by EPCIS Output Criteria '
                    'rules.'
            )

            wait_step = models.Step.objects.create(
                name='Wait Before Sending Data',
                description=
                    'This will send the task message using the source EPCIS Output '
                    'Critria EndPoint and Authentication Info.',
                step_class='quartet_output.steps.DelayStep',
                order=1,
                rule=trule
            )

            models.StepParameter.objects.create(
                step=wait_step,
                name='timeout_interval',
                value=3
            )

            models.Step.objects.create(
                name=_('Send Data'),
                description=_(
                    'This will send the task message using the source EPCIS Output '
                    'Critria EndPoint and Authentication Info.'),
                step_class='quartet_output.steps.TransportStep',
                order=2,
                rule=trule
            )

        except IntegrityError:
            trule = models.Rule.objects.get(name=rule_name)
        return trule

    def _create_output_criteria(self, endpoint, auth):
        try:
            EPCISOutputCriteria.objects.create(
                name='Comm Agg Output',
                action='ADD',
                event_type='Object',
                biz_location='urn:epc:id:sgln:0362865.00000.0',
                end_point=endpoint,
                authentication_info=auth
            )
        except IntegrityError:
            print('Criteria already exists.')

    def _create_endpoint(self):
        try:
            endpoint = EndPoint.objects.create(
                name='Local Server',
                urn=getattr(settings, 'TEST_SERVER', 'http://testhost')
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
