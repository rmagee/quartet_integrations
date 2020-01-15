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

class TestTraxeed2Rfxcel(TestCase):


    def test_traxeed_to_rfxcel_step(self):

        tr = TestRule()
        epcis_rule = tr.create_rule()
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/tx_rf_comm_agg_epcis.xml')
        task = self._create_task(epcis_rule)
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), task)

        epcis = context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value]

        self.assertTrue(str(epcis).index("ObjectEvent") > 0)
        self.assertTrue(str(epcis).index("Aggregation") > 0)
        self.assertTrue(str(epcis).index("shipping") > 0)


    def _create_task(self, rule):
        task = models.Task()
        task.rule = rule
        task.name = 'unit test traxeed to rfxcel'
        task.save()
        return task


class TestRule():

    def create_rule(self):

        # Create the Auth, Endpoint, and Output Criteria
        endpoint = self._create_endpoint()
        auth = self._create_authentication()
        self._create_output_criteria(endpoint, auth)
        rule_name='Traxeed to Rfxcel'
        if not models.Rule.objects.filter(name=rule_name).exists():
            # The Rule
            rule = models.Rule.objects.create(
                name=rule_name,
                description='Process inbound EPCIS Create and Send Comm/Agg/Shipping Events'
            )

            # Output Parsing Step
            parse_step = models.Step.objects.create(
                name='Parse EPCIS',
                description='Parse and inspect EPCIS events using output criteria.',
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
                value='Rfxcel Output',
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
                step_class='quartet_integrations.traxeed.steps.TraxeedRfxcel',
                rule=rule
            )


            models.StepParameter.objects.create(
                step=process_traxeed_step,
                name='Source Owning Party',
                value='urn:epc:id:sgln:0684276.00001.0',
                description='The SGLN URN of the Source Owning Party'
            )

            models.StepParameter.objects.create(
                step=process_traxeed_step,
                name='Source Location',
                value='urn:epc:id:sgln:0351754.00000.0',
                description='The SGLN URN of the Source Location'
            )

            models.StepParameter.objects.create(
                step=process_traxeed_step,
                name='Destination Owning Party',
                value='urn:epc:id:sgln:0339822.00010.0',
                description='The SGLN URN of the Destination Owning Party'
            )

            models.StepParameter.objects.create(
                step=process_traxeed_step,
                name='Destination Location',
                value='urn:epc:id:sgln:0684276.00001.0',
                description='The SGLN URN of the Destination Location'
            )

            output_step = models.Step.objects.create(
                name='Queue Outbound Message',
                description='Creates a Task for sending any outbound data',
                step_class='quartet_output.steps.CreateOutputTaskStep',
                order=3,
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


    def _create_output_criteria(self, endpoint, auth):
        try:
            EPCISOutputCriteria.objects.create(
                name='Rfxcel Output',
                action='ADD',
                event_type='Object',
                biz_location='urn:epc:id:sgln:0351754.00000.0',
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
