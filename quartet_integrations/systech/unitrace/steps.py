from jinja2.runtime import Context
from quartet_masterdata.models import TradeItem
from quartet_output.steps import EPCPyYesOutputStep as EYOS, \
    ContextKeys, RuleContext
from quartet_capture.models import Task
from gs123.conversion import URNConverter
from quartet_masterdata.models import TradeItem
from EPCPyYes.core.v1_2 import template_events
from EPCPyYes.core.v1_2 import events
from quartet_integrations.systech.unitrace.evnironment import get_default_environment
from quartet_templates.models import Template

class EPCPyYesOutputStep(EYOS):
    def __init__(self, db_task: Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.template = self.get_parameter(
            parameter_name='Template', 
            default='epcis/epcis_events_document.xml',
        )
        self.obj_event_template = self.get_parameter(
            parameter_name='Object Event Template',
        )
        self.agg_event_template = self.get_parameter(
            parameter_name='Aggregation Event Template',
        )
        self.filtered_event_template = self.get_parameter(
            parameter_name='Filtered Event Template',
        )


    def pre_execute(self, rule_context):
        oevents = rule_context.context.get(ContextKeys.OBJECT_EVENTS_KEY.value)
        oevents = self.process_object_events(oevents)

        aevents = rule_context.context.get(ContextKeys.AGGREGATION_EVENTS_KEY.value)
        aevents = self.process_aggegation_events(aevents)

        fevents = rule_context.context.get(ContextKeys.AGGREGATION_EVENTS_KEY.value)
        fevents = self.process_filtered_events(fevents)

    def process_filtered_events(self, fevents: list):
        template = None
        if self.filtered_event_template:
            template = Template.objects.get(
                name=self.filtered_event_template
            )

        for event in fevents:
            if template:
                env = get_default_environment()
                event.template = env.from_string(template.content)
        return fevents
        
    def process_object_events(self, oevents):
        template = None
        if self.obj_event_template:
            template = Template.objects.get(
                name=self.obj_event_template
            )

        for event in oevents:
            if template:
                env = get_default_environment()
                event.template = env.from_string(template.content)
            epc = event.epc_list[0]
            if ':sscc:' in epc:
                continue
            gtin14 = URNConverter(epc).gtin14

            try:
                trade_item = TradeItem.objects.get(GTIN14=gtin14)
                event.trade_item = trade_item
            except TradeItem.DoesNotExist:
                raise TradeItem.DoesNotExist(
                    'TradeItem masterdata for GTIN %s does not exist. Please '
                    'create a new TradeItem with this value.' % gtin14
                )
        return oevents
            

    def process_aggegation_events(self, aevents):
        template = None
        if self.agg_event_template:
            template = Template.objects.get(
                name=self.agg_event_template
            )

        for event in aevents:
            if template:
                env = get_default_environment()
                event.template = env.from_string(template.content)
        return aevents
    
    def execute(self, data, rule_context: RuleContext):
        """
        Pulls the object, agg, transaction and other events out of the context
        for processing.  See the step parameters
        :param data: The original message (not used by this step).
        :param rule_context: The RuleContext containing any filtered events
        and also any EPCPyYes events that were created by prior steps.
        """
        self.pre_execute(rule_context)
        super().execute(data, rule_context)

    def get_epcis_document_class(self, all_events):

        epcis_document = template_events.EPCISEventListDocument(
            template_events=all_events,
            template=self.template)
        
        return epcis_document