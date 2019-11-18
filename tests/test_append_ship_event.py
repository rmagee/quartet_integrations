import os
from django.test import TestCase
from django.utils.translation import gettext as _
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.events import BusinessTransaction
from EPCPyYes.core.v1_2.events import Action
from quartet_integrations.extended.events import AppendedShippingObjectEvent
from quartet_integrations.extended.parsers import SSCCParser
from quartet_capture import models as capture
from quartet_capture.tasks import execute_rule
from quartet_output.steps import ContextKeys


class TestAddShipping(TestCase):

    def test_sscc_parser(self):
        curpath = os.path.dirname(__file__)
        with open(os.path.join(curpath, 'data/comm_agg_epcis.xml'), 'rb') as file:
            parser = SSCCParser(file.read())
            parser.parse()

        list = parser.sscc_list


    def test_render_template(self):
        """
        1.) Create Template from Unit Test Data File
        2.) Create Object Event EPCIS Template Event with SSCCs
        3.) Override Object Event's default template by reading the template from DB and supplying that string to the object event ctor
        4.) Call render Object Event and assert that it is what XGEN Needs.
        """
        bt1 = BusinessTransaction("urn:epcglobal:cbv:bt:0345555000050:16", "urn:epcglobal:cbv:btt:po")

        bt2 = BusinessTransaction("urn:epcglobal:cbv:bt:0345555000050:1234568978675748474839", "urn:epcglobal:cbv:btt:desadv")

        obj_event = AppendedShippingObjectEvent(
                epc_list=['urn:epc:id:sscc:0355555.1000001345','urn:epc:id:sscc:0355555.1000001346'],
                action=Action.observe.value,
                biz_step=BusinessSteps.shipping.value,
                disposition=Disposition.in_transit.value,
                business_transaction_list=[bt1, bt2],
                read_point='urn:epc:id:sgln:0355555.00000.0',
        )


        s = obj_event.render()
        s = s

    def test_step(self):
        # 1 Standard Parsing
        # My Step
        # EPCIS Output Step
        #
        epcis_rule = capture.Rule.objects.create(
            name=_('Add Shipping'),
            description=_('Will capture and parse all properly formed inbound '
                          'EPCIS messagess.  Loose or strict enforcement can '
                          'be controlled via step parameters.'),
        )
        epcis_rule_parse_xml_step = capture.Step.objects.create(
            name=_('Parse XML'),
            description=_('Parse EPCIS data and save to database. To set loose '
                          'enforcement (capture all messages) change the '
                          '"LooseEnforcement" step parameter to have a '
                          'value of True.'),
            step_class='quartet_epcis.parsing.steps.EPCISParsingStep',
            order=1,
            rule=epcis_rule
        )
        capture.StepParameter.objects.create(
            step=epcis_rule_parse_xml_step,
            name='LooseEnforcement',
            value='False',
            description=_('If set to true, QU4RTET will capture all properly '
                          'formed EPCIS messages regardless of business context.')
        )

        add_shipment_step = capture.Step.objects.create(
            name='Add Shipping Event',
            description='Adds a Shipping Event to the Incoming EPCIS',
            order=2,
            step_class='quartet_integrations.extended.steps.AppendShippingStep',
            rule=epcis_rule
        )

        capture.StepParameter.objects.create(
            step=add_shipment_step,
            name='TemplateName',
            value='extended/appended_shipment.xml',
            description=_('The name and relative path of the template to use.')
        )

        render_step = capture.Step.objects.create(
            name='Render XML',
            description='Renders XML',
            order=3,
            step_class='quartet_output.steps.EPCPyYesOutputStep',
            rule=epcis_rule
        )

        # outbound_step = capture.Step.objects.create(
        #     name='Create Outbound',
        #     description='Creates a Task for sending any outbound data',
        #     order=4,
        #     step_class='quartet_output.steps.CreateOutputTaskStep',
        #     rule=epcis_rule
        # )
        # capture.StepParameter.objects.create(
        #     step=outbound_step,
        #     name='Output Rule',
        #     value='Transport Rule'
        #
        # )
        #
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath, 'data/comm_agg_epcis.xml')
        db_task = self._create_task(epcis_rule)
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)

        message = context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value]
        self.assertTrue(str(message).index("ObjectEvent") > 0)
        self.assertTrue(str(message).index("shipping") > 0)
        self.assertTrue(str(message).index("in_transit") > 0)

    def _create_task(self, rule):
        task = capture.Task()
        task.rule = rule
        task.name = 'unit test task'
        task.save()
        return task
