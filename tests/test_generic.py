import os

from django.test import TestCase
from django.contrib.auth.models import User, Group

from quartet_capture.models import Rule, Step, StepParameter, Task
from quartet_output.models import EndPoint, EPCISOutputCriteria
from quartet_capture.tasks import execute_rule
from quartet_integrations.generic.steps import ErrorReportTransportStep


class TestGeneric(TestCase):

    def setUp(self):
        # create User
        user = User.objects.create_user(
            username='test-user',
            email='unit@test.com',
            password='testpassword123'
        )
        # create EndPoint
        end_point = EndPoint.objects.create(
            name='test-endpoint',
            urn='mailto:unit@test.com?subject=Error in EPCIS',
        )
        # create EPCIS Output Criteria
        output_criteria = EPCISOutputCriteria.objects.create(
            name='Shipment Failure',
            end_point=end_point
        )
        # create Rule
        self.rule = Rule.objects.create(
            name='ErrorNotificationRule',
            description='Parsing rule that catches error',
        )
        # create Steps
        self.create_steps()
        # Create Params for rules
        self.create_step_params()
        # add test data (gtin and sscc)
        self.create_epcis_test_data()

    def create_steps(self):
        self.parsing_step = Step.objects.create(
            rule=self.rule,
            name='Parsing-Step',
            description='Parsing step',
            order=1,
            step_class='quartet_integrations.generic.steps.EPCISNotifcationStep',
        )
        self.message_step = Step.objects.create(
            rule=self.rule,
            name='Message-Step',
            description='Message step',
            order=2,
            step_class='quartet_integrations.generic.steps.ErrorReportTransportStep',
        )

    def create_step_params(self):
        StepParameter.objects.create(
            name='Output Criteria',
            value='Shipment Failure',
            description='Prepare email on error',
            step=self.parsing_step
        )

    def create_epcis_test_data(self):
        # create EPCIS RULE
        rule = Rule.objects.create(
            name='ParseEPCIS',
            description='Parse EPCIS'
        )
        # create EPCIS PARSING STEP
        Step.objects.create(
            name='Parse',
            rule=rule,
            description='PARSE',
            step_class='',
            order=1
        )
        # get data from file
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/generic/commission_event.xml'
        )
        # create task
        task = self.create_task(self.rule, 'Commission')
        # run quartet capture with rule and file
        with open(file_path, 'r') as f:
            context = execute_rule(f.read().encode(), task)

    def create_task(self, rule, name):
        task = Task()
        task.rule = rule
        task.name = name
        task.save()
        return task

    #### TESTS ####
    def test_ErrorNotificationRule_error(self):
        # get invalid epcis xml
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/generic/shipping_event_invalid.xml'
        )
        # create task
        task = self.create_task(self.rule, 'Invalid')
        # send request
        with open(file_path, 'r') as f:
            # assert if execute rule raises
            # a FailedShipmentException error
            self.assertRaises(
                ErrorReportTransportStep.FailedShipmentException,
                execute_rule, message=f.read().encode(), db_task=task)

    def test_ErrorNotificationRule_valid(self):
        # get valid epcis xml file
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(
            curpath,
            'data/generic/shipping_event_valid.xml'
        )
        # create task
        task = self.create_task(self.rule, 'Valid')
        # send request
        with open(file_path, 'r') as f:
            context = execute_rule(f.read().encode(), task)
        # assert message ID == 2 means it works
        self.assertEqual(context.context['MESSAGE_ID'], 2)

    # test inserting body to mailto method
    def test_set_email_fields_method(self):
        # create temp task
        task = Task(name='unittest',
                    rule=self.rule)
        step = ErrorReportTransportStep(db_task=task)
        body = 'body-unittest'
        # mailto no params
        mailto = 'mailto:unit@test.com'
        self.assertEquals(
            step.set_email_fields(mailto, body),
            mailto + '?body=' + body)
        # mailto with one param
        mailto = 'mailto:unit@test.com?subject=subject-unittest'
        self.assertIn(
            'body=' + body,
            step.set_email_fields(mailto, body))
        # mailto with one param - body
        mailto = 'mailto:unit@test.com?body=change-me'
        self.assertIn(
            'body=' + body,
            step.set_email_fields(mailto, body))
        # mailto with multiple params with body
        mailto = 'mailto:unit@test.com?subject=sub-unittest' \
                 '&body=change-me&cc=some@mail.com'
        self.assertIn(
            'body=' + body,
            step.set_email_fields(mailto, body))
