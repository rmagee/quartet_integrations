import datetime
import io
from django.core.files.base import File
from EPCPyYes.core.v1_2 import template_events
from quartet_capture import models, rules
from quartet_capture.rules import RuleContext
from quartet_integrations.frequentz.environment import get_default_environment

from quartet_integrations.frequentz.parsers import FrequentzOutputParser

from quartet_output.steps import ContextKeys

"""
 Creates output EPCIS for Frequentz which is EPCIS 1.0
"""

class FrequentzOutputStep(rules.Step):

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)


    def execute(self, data, rule_context: RuleContext):

        # Parse EPCIS
        if isinstance(data, File):
            parser = FrequentzOutputParser(data)
        elif isinstance(data, str):
            parser = FrequentzOutputParser(io.BytesIO(str.encode(data)))
        else:
            parser = FrequentzOutputParser(io.BytesIO(data))

        # parse
        parser.parse()

        rule_context.context[
            ContextKeys.OBJECT_EVENTS_KEY.value] = parser.object_events
        rule_context.context[
            ContextKeys.AGGREGATION_EVENTS_KEY.value] = parser.aggregation_events

        # put the parser in the context so the data isn't parsed again in the next step
        rule_context.context['PARSER'] = parser

        env = get_default_environment()

        created_date = str(datetime.datetime.utcnow().isoformat())
        additional_context = {'created_date': created_date}

        all_events = parser.object_events + parser.aggregation_events
        epcis_document = template_events.EPCISEventListDocument(
            all_events,
            None,
            template=env.get_template(
                'frequentz/frequentz_epcis_document.xml'
            ),
            additional_context=additional_context
        )
        if self.get_boolean_parameter('JSON', False):
            data = epcis_document.render_json()
        else:
            data = epcis_document.render()
        rule_context.context[
            ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value
        ] = data
        # For testing so the comm/agg doc can be viewed/evaluated in unit test
        rule_context.context['COMM_AGG_DOCUMENT'] = data

    def declared_parameters(self):
        return {}

    def on_failure(self):
        pass
