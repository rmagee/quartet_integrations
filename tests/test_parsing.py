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

from django.conf import settings
from django.test import TestCase

from EPCPyYes.core.v1_2 import template_events as yes_events
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps

from quartet_capture.models import Rule, Step, Task, StepParameter
from quartet_capture.tasks import execute_rule
from quartet_epcis.models import events
from quartet_epcis.parsing.context import BusinessEPCISParser
from quartet_integrations.sap.parsing import SAPParser
from quartet_masterdata import models
from quartet_output.models import EPCISOutputCriteria, EndPoint
from quartet_output.steps import ContextKeys
from quartet_masterdata.models import Company, Location

class TestParser(SAPParser):

    def handle_object_event(self, epcis_event: yes_events.ObjectEvent):
        print(epcis_event.render())
        return super().handle_object_event(epcis_event)


class TestEparsecis(TestCase):
    def test_epcis_file(self):
        curpath = os.path.dirname(__file__)
        parser = TestParser(
            os.path.join(curpath, 'data/sap-epcis.xml'))
        parser.parse()

    def test_test_file(self):
        curpath = os.path.dirname(__file__)
        parser = TestParser(
            os.path.join(curpath, 'data/test.xml'))
        parser.parse()


class TestRule(TestCase):
    def test_sap_step(self):
        rule = self._create_rule()
        self._create_sap_step(rule)
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/sap-epcis.xml')
        db_task = self._create_task(rule)
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)

    def test_sap_test_step(self):
        rule = self._create_rule()
        self._create_sap_step(rule)
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/test.xml')
        db_task = self._create_task(rule)
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)

    def _create_rule(self):
        rule = Rule()
        rule.name = 'EPCIS'
        rule.description = 'test rule'
        rule.save()
        return rule

    def _create_sap_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 3
        step.name = 'Parse SAP EPCIS'
        step.step_class = 'quartet_integrations.sap.steps.SAPParsingStep'
        step.description = 'sap unit test parsing step'
        step.save()

    def _create_task(self, rule):
        task = Task()
        task.rule = rule
        task.name = 'unit test task'
        task.save()
        return task


class TestDivinciRule(TestCase):
    def setUp(self) -> None:
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/divinci-preload.xml')
        BusinessEPCISParser(data_path).parse()
        self._create_trade_item()

    def _test_divinci_step(self, file='data/divinci-inbound.json'):


        self._create_company_from_sgln('urn:epc:id:sgln:309999.111111.0')
        self._create_company_from_sgln('urn:epc:id:sgln:809999.111111.1')

        self._create_good_output_criterion()
        rule = self._create_rule()
        self._create_divinci_parsing_step(rule)
        self._create_render_tracelink_step(rule)
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, file)
        db_task = self._create_task(rule)
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
            event = (context.context[ContextKeys.FILTERED_EVENTS_KEY.value])[0]
            print(event.render())
            self.assertEqual(BusinessSteps.shipping.value, event.biz_step)

        print(context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value])

    def _create_good_output_criterion(self):
        criteria = EPCISOutputCriteria.objects.create(
            name='unit test criteria',
            biz_step=BusinessSteps.shipping.value,
            end_point=self._create_endpoint()
        )
        return criteria

    def _create_endpoint(self):
        ep = EndPoint()
        ep.urn = getattr(settings, 'TEST_SERVER', 'http://testhost')
        ep.name = 'Test EndPoint'
        ep.save()
        return ep

    def test_divinci_step(self):
        self._test_divinci_step()
        evs = events.Event.objects.filter(type='ob')
        self.assertEqual(evs.count(), 2)
        evs = events.Event.objects.filter(type='ag')
        self.assertEqual(evs.count(), 4)

    def test_divinci_auto_commisssion(self):
        self._test_divinci_step('data/divinci-auto-commission.json')
        evs = events.Event.objects.filter(type='ob')
        self.assertEqual(evs.count(), 3)

    def _create_rule(self):
        rule = Rule()
        rule.name = 'Divinci'
        rule.description = 'test rule'
        rule.save()
        return rule

    def _create_divinci_parsing_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 3
        step.name = 'Parse Divinci JSON'
        step.step_class = 'quartet_integrations.divinci.steps.JSONParsingStep'
        step.description = 'divinci unit test parsing step'
        step.save()
        param = StepParameter(
            name='EPCIS Output Criteria',
            value='unit test criteria',
            step=step
        )
        param.save()

    def _create_task(self, rule):
        task = Task()
        task.rule = rule
        task.name = 'unit test task'
        task.save()
        return task

    def _create_trade_item(self):
        company = models.Company.objects.create(
            name='test pharma',
            gs1_company_prefix='0331722'
        )
        models.TradeItem.objects.create(
            GTIN14='10331722192016',
            manufacturer_name='Test',
            company=company
        )
        models.Company.objects.create(
            name='test pharma',
            gs1_company_prefix='0343602'
        )

    def _create_render_tracelink_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 4
        step.name = 'Render Tracelink EPCIS XML'
        step.step_class = 'quartet_tracelink.steps.TracelinkFilteredEventOutputStep'
        step.description = 'Creates TraceLink compliant EPCIS'
        step.save()

        StepParameter.objects.create(step=step,
                                     name='Append Filtered Events',
                                     value='True')

    def _create_sftp_endpoint(self):
        ep = models.EndPoint()
        ep.urn = 'sftp://testsftphost:22/upload'
        ep.name = 'Test SFTP EndPoint'
        ep.save()
        return ep

    def _create_sftp_auth(self):
        auth = models.AuthenticationInfo()
        auth.description = 'Unit test auth.'
        auth.username = 'foo'
        auth.password = 'pass'
        auth.save()
        return auth

    def _create_company_from_sgln(self, sgln, type=Company):
        from gs123.check_digit import calculate_check_digit
        gln13 = sgln.split(':')[-1]
        gln13 = gln13.split('.')
        gln13 = '%s%s' % (gln13[0], gln13[1])
        gln13 = calculate_check_digit(gln13)
        print('gln = %s', gln13)
        type.objects.create(
            name='unit test company %s' % gln13,
            GLN13=gln13,
            SGLN=sgln,
            address1='123 Unit Test Street',
            address2='Unit 2028',
            postal_code='12345',
            city='Unit Testville',
            state_province='PA',
            country='US'
        )
