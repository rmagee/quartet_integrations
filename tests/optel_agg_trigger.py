import os

from django.test import TestCase
from django.conf import settings

from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.events import EventType
from quartet_capture.models import Rule, Step, StepParameter, Task
from quartet_capture.tasks import execute_rule, execute_queued_task
from quartet_epcis.parsing.business_parser import BusinessEPCISParser
from quartet_output import models
from quartet_output.models import EPCISOutputCriteria
from quartet_output.steps import ContextKeys
from quartet_templates.models import Template


class TestOutputParsing(TestCase):
    def _create_endpoint(self):
        ep = models.EndPoint()
        ep.urn = getattr(settings, 'TEST_SERVER', 'http://testhost')
        ep.name = 'Test EndPoint'
        ep.save()
        return ep

    def _create_auth(self):
        auth = models.AuthenticationInfo()
        auth.description = 'Unit test auth.'
        auth.username = 'UnitTestUser'
        auth.password = 'UnitTestPassword'
        auth.save()
        return auth

    def _create_template(self):
        content = """<ObjectEvent>
            {% include "epcis/event_times.xml" %}
            {% include "epcis/base_extension.xml" %}
            {% if event.epc_list %}
                <epcList>
                    {% for epc in event.epc_list %}
                        <epc>{{ epc }}</epc>
                    {% endfor %}
                </epcList>
            {% endif %}
            {% include "epcis/business_data.xml" %}
            {% if event.ilmd and event.action == 'ADD' %}
            {% if additional_context != None %}
                {% if additional_context.search_value != None and additional_context.reverse_search == False and additional_context.search_value in event.epc_list[0] %}
                    {% include "optel/optel_ilmd.xml" %}
                    {{ additional_context.object_ilmd|default('', true) }}
                {% elif additional_context.search_value != None and additional_context.reverse_search == True and additional_context.search_value not in event.epc_list[0] %}
                    {% include "optel/optel_ilmd.xml" %}
                    {{ additional_context.object_ilmd|default('', true) }}
                {% else %}
                    {% include "optel/optel_ilmd.xml" %}
                {% endif %}
            {% else %}
                {% include "optel/optel_ilmd.xml" %}
            {% endif %}
            {% endif %}
        </ObjectEvent>"""
        Template.objects.create(name='Unit Test Template',
                                content=content,
                                description='a unit test template'
                                )


    def _create_good_ouput_criterion(self):
        endpoint = self._create_endpoint()
        auth = self._create_auth()
        eoc = EPCISOutputCriteria()
        eoc.name = "Test Criteria"
        eoc.action = "ADD"
        eoc.event_type = EventType.Aggregation.value
        eoc.disposition = Disposition.in_progress.value
        eoc.biz_step = BusinessSteps.packing.value
        eoc.authentication_info = auth
        eoc.end_point = endpoint
        eoc.save()
        return eoc

    def _create_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 1
        step.name = 'Output Determination'
        step.step_class = 'quartet_output.steps.OutputParsingStep'
        step.description = 'unit test step'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'EPCIS Output Criteria'
        step_parameter.value = 'Test Criteria'
        step_parameter.save()
        return step

    def _create_comm_step(self, rule, use_template=False):
        step = Step()
        step.rule = rule
        step.order = 3
        step.name = 'CreateCommissioning'
        step.step_class = 'quartet_integrations.optel.steps.AppendCommissioningStep'
        step.description = 'unit test commissioning step'
        step.save()
        if use_template:
            StepParameter.objects.create(
                name='Template',
                value='Unit Test Template',
                step=step
            )

    def _create_epcpyyes_step(self, rule, json=False, reverse_search=False,
                              create_data=True):
        step = Step()
        step.rule = rule
        step.order = 4
        step.name = 'Create EPCIS'
        step.step_class = 'quartet_integrations.optel.steps.EPCPyYesOutputStep'
        step.description = 'Creates EPCIS XML or JSON and inserts into rule' \
                           'context.'
        step.save()
        if json:
            param = StepParameter.objects.create(
                step=step,
                name='JSON',
                value=True
            )
        if create_data:
            self.create_gs1ushc_data(step)
        self._create_search_param(step)
        self._create_search_direction_step(step, reverse_search)

    def create_gs1ushc_data(self, step):
        param = StepParameter()
        param.name = 'Additional Context'
        param.value = (
            '<gs1ushc:unitOfMeasure xmlns:gs1ushc="http://epcis.gs1us.org/hc/ns">Btl</gs1ushc:unitOfMeasure>'
            '<gs1ushc:additionalTradeItemIdentification xmlns:gs1ushc="http://epcis.gs1us.org/hc/ns">'
            '<gs1ushc:additionalTradeItemIdentificationValue>034390</gs1ushc:additionalTradeItemIdentificationValue>'
            '</gs1ushc:additionalTradeItemIdentification>'
        )
        param.step = step
        param.save()

    def _create_search_direction_step(self, step, reverse=False):
        param = StepParameter()
        param.name = 'Context Reverse Search'
        param.value = str(reverse)
        param.step = step
        param.save()

    def _create_search_param(self, step):
        param2 = StepParameter()
        param2.name = 'Context Search Value'
        param2.value = '000101'
        param2.step = step
        param2.save()

    def _create_task_step(self, rule, order=5):
        step = Step()
        step.rule = rule
        step.order = order
        step.name = 'Create Output Task'
        step.step_class = 'quartet_output.steps.CreateOutputTaskStep'
        step.description = 'Looks for any EPCIS data on the context and ' \
                           'then, if found, creates a new output task using ' \
                           'the configured Output Rule step parameter.'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'Output Rule'
        step_parameter.value = 'Transport Rule'
        step_parameter.description = 'The name of the rule to create a new ' \
                                     'task with.'
        step_parameter.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'run-immediately'
        step_parameter.value = 'True'
        step_parameter.description = 'The name of the rule to create a new ' \
                                     'task with.'
        step_parameter.save()
        return step

    def _create_rule(self):
        rule = Rule()
        rule.name = 'output-test'
        rule.description = 'output test rule'
        rule.save()
        return rule

    def _create_transport_rule(self):
        rule = Rule()
        rule.name = 'Transport Rule'
        rule.description = 'Attempts to send data using transport step(s).'
        rule.save()
        return rule

    def _create_transport_step(self, rule, put_data='False'):
        step = Step()
        step.rule = rule
        step.order = 1
        step.name = 'Transport'
        step.step_class = 'quartet_output.steps.TransportStep'
        step.description = 'Sends test data.'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'run-immediately'
        step_parameter.value = 'True'
        step_parameter.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'put-data'
        step_parameter.value = put_data
        step_parameter.save()

    def _create_task(self, rule):
        task = Task()
        task.rule = rule
        task.name = 'unit test task'
        task.save()
        return task

    def _parse_test_data(self, test_file='data/epcis.xml',
                         parser_type=BusinessEPCISParser,
                         recursive_decommission=False):
        curpath = os.path.dirname(__file__)
        if isinstance(parser_type, BusinessEPCISParser):
            parser = BusinessEPCISParser(
                os.path.join(curpath, test_file),
                recursive_decommission=recursive_decommission
            )
        else:
            parser = parser_type(
                os.path.join(curpath, test_file),
            )
        message_id = parser.parse()
        print(parser.event_cache)
        parser.clear_cache()
        return message_id, parser

    def test_rule_with_agg_comm_output(self):
        self._create_good_ouput_criterion()
        db_rule = self._create_rule()
        self._create_step(db_rule)
        self._create_comm_step(db_rule)
        self._create_epcpyyes_step(db_rule, create_data=True)
        self._create_task_step(db_rule)
        db_rule2 = self._create_transport_rule()
        self._create_transport_step(db_rule2)
        db_task = self._create_task(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        self._parse_test_data('data/commissioning.xml')
        data_path = os.path.join(curpath, 'data/aggregation.xml')
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
            self.assertEqual(
                len(context.context[ContextKeys.FILTERED_EVENTS_KEY.value]),
                12,
                "There should be twelve filtered events."
            )
            task_name = context.context[ContextKeys.CREATED_TASK_NAME_KEY]
            execute_queued_task(task_name=task_name)
            task = Task.objects.get(name=task_name)
            self.assertEqual(task.status, 'FINISHED')
            print(
                context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value])

    def test_rule_with_agg_comm_output_reverse(self):
        self._create_good_ouput_criterion()
        db_rule = self._create_rule()
        self._create_step(db_rule)
        self._create_comm_step(db_rule, use_template=True)
        self._create_epcpyyes_step(db_rule, reverse_search=True)
        self._create_task_step(db_rule)
        self._create_template()
        db_rule2 = self._create_transport_rule()
        self._create_transport_step(db_rule2)
        db_task = self._create_task(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        self._parse_test_data('data/commissioning.xml')
        data_path = os.path.join(curpath, 'data/aggregation.xml')
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
            self.assertEqual(
                len(context.context[ContextKeys.FILTERED_EVENTS_KEY.value]),
                12,
                "There should be twelve filtered events."
            )
            task_name = context.context[ContextKeys.CREATED_TASK_NAME_KEY]
            execute_queued_task(task_name=task_name)
            task = Task.objects.get(name=task_name)
            self.assertEqual(task.status, 'FINISHED')
            print(
                context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value])

    def test_rule_with_agg_comm_output_reverse_no_data(self):
        self._create_good_ouput_criterion()
        db_rule = self._create_rule()
        self._create_step(db_rule)
        self._create_comm_step(db_rule)
        self._create_epcpyyes_step(db_rule, reverse_search=True,
                                   create_data=False)
        self._create_task_step(db_rule)
        db_rule2 = self._create_transport_rule()
        self._create_transport_step(db_rule2)
        db_task = self._create_task(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        self._parse_test_data('data/sun-commissioning.xml')
        data_path = os.path.join(curpath, 'data/sun-aggregation.xml')
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
            self.assertEqual(
                len(context.context[ContextKeys.FILTERED_EVENTS_KEY.value]),
                12,
                "There should be twelve filtered events."
            )
            task_name = context.context[ContextKeys.CREATED_TASK_NAME_KEY]
            execute_queued_task(task_name=task_name)
            task = Task.objects.get(name=task_name)
            self.assertEqual(task.status, 'FINISHED')
            print(
                context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value])
