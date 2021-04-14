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
import os

from django.test import TestCase

from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.events import EventType
from quartet_capture.models import Rule, Step, StepParameter, Task
from quartet_capture.tasks import execute_rule
from quartet_epcis.parsing.context_parser import BusinessEPCISParser
from quartet_output import models
from quartet_output.models import EPCISOutputCriteria
from quartet_output.steps import ContextKeys
from quartet_templates.models import Template


class TestOutputParsing(TestCase):
    def _create_endpoint(self):
        ep = models.EndPoint()
        ep.urn = 'mailto:crashtestdummie@unittest.local?body=send%20current-issue&subject=awesome email'
        ep.name = 'Test EndPoint'
        ep.save()
        return ep

    def _create_good_ouput_criterion(self):
        endpoint = self._create_endpoint()
        eoc = EPCISOutputCriteria()
        eoc.name = "Test Criteria"
        eoc.action = "OBSERVE"
        eoc.event_type = EventType.Object.value
        eoc.biz_step = BusinessSteps.shipping.value
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

    def _create_comm_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 2
        step.name = 'CreateCommissioning'
        step.step_class = 'quartet_output.steps.AddCommissioningDataStep'
        step.description = 'unit test commissioning step'
        step.save()

    def _create_add_agg_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 3
        step.name = 'CreateAggregation'
        step.step_class = 'quartet_output.steps.UnpackHierarchyStep'
        step.save()

    def _create_epcpyyes_step(self, rule, json=False):
        step = Step()
        step.rule = rule
        step.order = 4
        step.name = 'Create EPCIS'
        step.step_class = 'quartet_integrations.extended.steps.TemplateOutputStep'
        step.description = 'Creates EPCIS XML or JSON and inserts into rule' \
                           'context.'
        step.save()
        if json:
            param = StepParameter.objects.create(
                step=step,
                name='JSON',
                value=True
            )
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'Template'
        step_parameter.value = 'Test Template'
        step_parameter.description = 'The name of the rule to create a new ' \
                                     'task with.'
        step_parameter.save()
        sp2 = StepParameter()
        sp2.step = step
        sp2.name = "Append Filtered Events"
        sp2.value = 'True'
        sp2.description = 'Do not append the filtered event.'
        sp2.save()

    def _create_task_step(self, rule, order=10):
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
        step_parameter.name = 'Run Immediately'
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

    def _parse_test_data(self, test_file='data/templates/epcis.xml',
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

    def create_template(self):
        Template.objects.create(
            name='Test Template',
            content="""
<?xml version="1.0" encoding="utf-8"?>
<epcis:EPCISDocument xmlns:cbvmd="urn:epcglobal:cbv:mda" xmlns:gs1ushc="http://epcis.gs1us.org/hc/ns" xmlns:sbdh="http://www.unece.org/cefact/namespaces/StandardBusinessDocumentHeader" schemaVersion="1.2" creationDate="{{created_date}}-00:00" xmlns:epcis="urn:epcglobal:epcis:xsd:1">
  <EPCISHeader>
    <sbdh:StandardBusinessDocumentHeader>
      <sbdh:HeaderVersion>1.0</sbdh:HeaderVersion>
      <sbdh:Sender>
        <sbdh:Identifier Authority="SGLN">urn:epc:id:sgln:7777777.0.0</sbdh:Identifier>
      </sbdh:Sender>
      <sbdh:Receiver>
        <sbdh:Identifier Authority="SGLN">urn:epc:id:sgln:7777777.0.0</sbdh:Identifier>
      </sbdh:Receiver>
      <sbdh:DocumentIdentification>
        <sbdh:Standard>EPCGlobal</sbdh:Standard>
        <sbdh:TypeVersion>1.2</sbdh:TypeVersion>
        <sbdh:InstanceIdentifier>{{ additional_context.uuid }}</sbdh:InstanceIdentifier>
        <sbdh:Type>Events</sbdh:Type>
        <sbdh:CreationDateAndTime>{{ created_date }}-00:00</sbdh:CreationDateAndTime>
      </sbdh:DocumentIdentification>
    </sbdh:StandardBusinessDocumentHeader>
    <extension>
      <EPCISMasterData>
        <VocabularyList>
          <Vocabulary type="urn:epcglobal:epcis:vtype:location">
            <VocabularyElementList>
              <VocabularyElement id="urn:epc:id:sgln:7777777.00000.0">
                <attribute id="urn:epcglobal:cbv:mda#name">asdf</attribute>
                <attribute id="urn:epcglobal:cbv:mda#streetAddressOne">7590 asd Street</attribute>
                <attribute id="urn:epcglobal:cbv:mda#city">Sumpter</attribute>
                <attribute id="urn:epcglobal:cbv:mda#state">CA</attribute>
                <attribute id="urn:epcglobal:cbv:mda#postalCode">77777</attribute>
                <attribute id="urn:epcglobal:cbv:mda#countryCode">US</attribute>
              </VocabularyElement>
              <VocabularyElement id="urn:epc:id:sgln:7777777.0.0">
                <attribute id="urn:epcglobal:cbv:mda#name">PRODUCTS, INC</attribute>
                <attribute id="urn:epcglobal:cbv:mda#streetAddressOne">16 ASDF DR</attribute>
                <attribute id="urn:epcglobal:cbv:mda#city">SOME TOWN</attribute>
                <attribute id="urn:epcglobal:cbv:mda#state">AL</attribute>
                <attribute id="urn:epcglobal:cbv:mda#postalCode">77777</attribute>
                <attribute id="urn:epcglobal:cbv:mda#countryCode">US</attribute>
              </VocabularyElement>
            </VocabularyElementList>
          </Vocabulary>
          <Vocabulary type="urn:epcglobal:epcis:vtype:epcclass">
            <VocabularyElementList>
              <VocabularyElement id="urn:epc:idpat:sgtin:*">
                <attribute id="urn:epcglobal:cbv:mda#additionalTradeItemIdentification">777777777</attribute>
                <attribute id="urn:epcglobal:cbv:mda#additionalTradeItemIdentificationTypeCode">FDA_NDC_11</attribute>
                <attribute id="urn:epcglobal:cbv:mda#regulatedProductName">Tussen</attribute>
                <attribute id="urn:epcglobal:cbv:mda#manufacturerOfTradeItemPartyName">CORP, INC</attribute>
                <attribute id="urn:epcglobal:cbv:mda#dosageFormType">TABLET</attribute>
                <attribute id="urn:epcglobal:cbv:mda#strengthDescription">50MG</attribute>
              </VocabularyElement>
            </VocabularyElementList>
          </Vocabulary>
        </VocabularyList>
      </EPCISMasterData>
    </extension>
    <gs1ushc:dscsaTransactionStatement>
      <gs1ushc:affirmTransactionStatement>false</gs1ushc:affirmTransactionStatement>
    </gs1ushc:dscsaTransactionStatement>
  </EPCISHeader>
  <EPCISBody>
    <EventList>
        {% block events %}
            {% if template_events|length > 0 %}
                {% for event in template_events %}
                    {% include event.template %}
                {% endfor %}
            {% endif %}
        {% endblock %}
    </EventList>
  </EPCISBody>
</epcis:EPCISDocument>
""")

    def test_rule_with_agg_comm_output(self):
        self.create_template()
        self._create_good_ouput_criterion()
        db_rule = self._create_rule()
        self._create_step(db_rule)
        self._create_comm_step(db_rule)
        self._create_add_agg_step(db_rule)
        self._create_epcpyyes_step(db_rule)
        self._create_task_step(db_rule)
        db_rule2 = self._create_transport_rule()
        self._create_transport_step(db_rule2)
        db_task = self._create_task(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        data_path = os.path.join(curpath, 'data/templates/full.xml')
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
            self.assertEqual(
                len(context.context[ContextKeys.FILTERED_EVENTS_KEY.value]),
                1,
                "There should be one filtered event."
            )
            task_name = context.context[ContextKeys.CREATED_TASK_NAME_KEY]
            task = Task.objects.get(name=task_name)
            self.assertEqual(task.status, 'FINISHED')
            print(context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value])


