import os
from django.db.utils import IntegrityError
from django.utils.translation import gettext as _

from quartet_capture.models import Rule, StepParameter, Step
from quartet_masterdata.models import TradeItem, Company
from quartet_output.models import EndPoint, EPCISOutputCriteria, \
    AuthenticationInfo
from quartet_templates.models import Template
from random_flavorpack import models
from serialbox.models import Pool, ResponseRule
from serialbox.models import SequentialRegion


def create_gtin_response_rule():
    rule, created = Rule.objects.get_or_create(
        name='OPSM GTIN Response Rule',
        description='OPSM Response Rule (Auto Created)',
    )

    conversion_step, created = Step.objects.get_or_create(
        rule=rule,
        name='List Conversion',
        step_class='quartet_integrations.opsm.steps.ListToUrnConversionStep',
        order=1
    )
    if not created:
        conversion_step.description = 'Convert the list of numbers to ' \
                                      'GTINs or SSCCs for use by OPSM.',

    format_step, created = Step.objects.get_or_create(
        rule=rule,
        name='Format Message',
        description='A message template step.',
        step_class='quartet_templates.steps.TemplateStep',
        order=2
    )
    StepParameter.objects.get_or_create(
        step=format_step,
        name='Template Name',
        value='OPSM GTIN Response Template'
    )

    # create_template()
    # pool = Pool.objects.get(machine_name='00313000007772')
    # response_rule = ResponseRule.objects.get_or_create(
    #     rule=rule,
    #     pool=pool,
    #     content_type='xml'
    # )


def create_SSCC_response_rule():
    rule, created = Rule.objects.get_or_create(
        name='OPSM SSCC Response Rule',
        description='OPSM SSCC Response Rule (Auto Created)',
    )

    conversion_step, created = Step.objects.get_or_create(
        rule=rule,
        name='List Conversion',
        step_class='quartet_integrations.serialbox.steps.ListToBarcodeConversionStep',
        order=1
    )
    if not created:
        conversion_step.description = 'Convert the list of numbers to ' \
                                      'SSCCs for use by OPSM.',

    cp = StepParameter.objects.create(
        name='Company Prefix',
        value='031300',
        description='Unit test prefix.',
        step=conversion_step
    )

    ed = StepParameter.objects.create(
        name='Extension Digit',
        value='0',
        description='Unit test indicator',
        step=conversion_step
    )

    format_step, created = Step.objects.get_or_create(
        rule=rule,
        name='Format Message',
        description='A message template step.',
        step_class='quartet_templates.steps.TemplateStep',
        order=2
    )
    StepParameter.objects.get_or_create(
        step=format_step,
        name='Template Name',
        value='OPSM SSCC Response Template'
    )

    create_sscc_template()
    pool = Pool.objects.get(machine_name='031300000770000001-SSCC')
    return ResponseRule.objects.get_or_create(
        rule=rule,
        pool=pool,
        content_type='xml'
    )[0]


def create_trade_item():
    company = Company.objects.create(
        name='Pharma Co',
        GLN13='0313000000011',
        SGLN='urn:epc:id:sgln:031300.1.0',
        gs1_company_prefix='031300',
    )
    TradeItem.objects.create(
        company=company,
        GTIN14='00313000007772',
        NDC_pattern='4-4-2',
        NDC='1300-0007-77',
        package_uom='EA'
    )


def create_template():
    print('Creating the OPSM GTIN response template...')
    curpath = os.path.dirname(__file__)
    file_path = os.path.join(curpath,
                             '../../templates/opsm/sgtin_response.xml')
    with open(file_path, 'r') as f:
        response_template = Template.objects.get_or_create(
            name='OPSM GTIN Response Template',
            content=f.read()
        )


def create_sscc_template():
    print('Creating the OPSM SSCC response template...')
    curpath = os.path.dirname(__file__)
    file_path = os.path.join(curpath,
                             '../../templates/opsm/sscc_response.xml')
    with open(file_path, 'r') as f:
        response_template = Template.objects.get_or_create(
            name='OPSM SSCC Response Template',
            content=f.read()
        )


def create_random_range():
    sp1 = Pool.objects.create(
        readable_name='Pharmaprod 20mcg Pills',
        machine_name='00313000007772',
        active=True,
        request_threshold=1000
    )
    models.RandomizedRegion.objects.create(
        readable_name='Pharmaprod 20mcg Pills',
        machine_name='00313000007772',
        start=239380,
        active=True,
        order=1,
        pool=sp1,
        min=1,
        max=999999999999
    )


def create_random_sscc_range():
    sp1 = Pool.objects.create(
        readable_name='Pharmaprod SSCC',
        machine_name='031300000770000001-SSCC',
        active=True,
        request_threshold=1000
    )
    # 031300 + 00000000000 + 1 = 18
    # the max length of the serial number is 99999999999
    models.RandomizedRegion.objects.create(
        readable_name='Pharmaprod 20mcg Pills',
        machine_name='031300000770000001-SSCC',
        start=239380,
        active=True,
        order=1,
        pool=sp1,
        min=1,
        max=99999999999
    )


def create_sequential_sscc_range():
    sp1 = Pool.objects.create(
        readable_name='Pharmaprod SSCC',
        machine_name='031300000770000001-SSCC',
        active=True,
        request_threshold=1000
    )
    # 031300 + 00000000000 + 1 = 18
    # the max length of the serial number is 99999999999
    SequentialRegion.objects.create(
        readable_name='Pharmaprod 20mcg Pills',
        machine_name='031300000770000001-SSCC',
        start=1,
        active=True,
        order=1,
        pool=sp1,
        state=1,
        end=99999999999
    )


def create_external_GTIN_response_rule():
    """
    Gets or creates the external gtin response rule.
    :return: A tuple with the rule and a boolean 'created'.
    """
    rule, created = Rule.objects.get_or_create(
        name='OPSM External GTIN Response Rule',
        description='OPSM Response Rule (Auto Created) for use by list-based'
                    ' range data sourced from external systems.',
    )

    conversion_step, created = Step.objects.get_or_create(
        rule=rule,
        name='List Conversion',
        step_class='quartet_integrations.opsm.steps.ListBasedRegionConversionStep',
        order=1
    )
    if not created:
        conversion_step.description = 'Convert the list of numbers to ' \
                                      'GTIN URNs or SSCCs for use by OPSM.',

    format_step, created = Step.objects.get_or_create(
        rule=rule,
        name='Format Message',
        description='A message template step.',
        step_class='quartet_templates.steps.TemplateStep',
        order=2
    )
    StepParameter.objects.get_or_create(
        step=format_step,
        name='Template Name',
        value='OPSM GTIN Response Template'
    )
    create_template()
    return rule, created


def create_output_filter_rule(rule_name='GS1USHC Output Filter',
                              delay_rule=False):
    create_criteria()
    if not Rule.objects.filter(name=rule_name).exists():
        rule = Rule.objects.create(
            name=rule_name,
            description=_('Will inspect inbound messages for output '
                          'processing.')
        )
        parse_step = Step.objects.create(
            name=_('Inspect EPCIS'),
            description=_(
                'Parse and insepect EPCIS events using output criteria.'),
            step_class='quartet_integrations.gs1ushc.steps.OutputParsingStep',
            order=1,
            rule=rule
        )
        StepParameter.objects.create(
            name='EPCIS Output Criteria',
            step=parse_step,
            value='Test Transaction Criteria',
            description=_(
                'This is the name of the EPCIS Output Criteria record to use.')

        )
        Step.objects.create(
            name=_('Add Commissioning Data'),
            description=_(
                'Adds commissioning events for filtered EPCs and their children.'),
            step_class='quartet_output.steps.AddCommissioningDataStep',
            order=2,
            rule=rule
        )
        Step.objects.create(
            name=_('Add Aggregation Data'),
            description=_(
                'Adds aggregation events for included EPCs in any filtered events.'),
            step_class='quartet_output.steps.UnpackHierarchyStep',
            order=3,
            rule=rule
        )
        Step.objects.create(
            name=_('Render EPCIS XML'),
            description=_(
                'Pulls any EPCPyYes objects from the context and creates an XML message'),
            step_class='quartet_integrations.gs1ushc.steps.EPCPyYesOutputStep',
            order=4,
            rule=rule
        )
        output_step = Step.objects.create(
            name=_('Queue Outbound Message'),
            description=_('Creates a Task for sending any outbound data'),
            step_class='quartet_output.steps.CreateOutputTaskStep',
            order=5,
            rule=rule
        )
        StepParameter.objects.create(
            step=output_step,
            name='Output Rule',
            value='Transport Rule'
        )
        if delay_rule == True:
            second_parse_step = Step.objects.create(
                name=_('Inspect EPCIS'),
                description='Used to assign an output criteria to the second '
                            'message for forwarding filtered events.',
                step_class='quartet_integrations.gs1ushc.steps.OutputParsingStep',
                order=6,
                rule=rule
            )
            StepParameter.objects.create(
                name='EPCIS Output Criteria',
                step=second_parse_step,
                value='Test Transaction Criteria',
                description=_(
                    'This is the name of the EPCIS Output Criteria record to use.')

            )
            render_events = Step.objects.create(
                name=_('Render Filtered Events'),
                description=_('Takes any events that were filtered by the '
                              'prior step and renders them to XML for '
                              'sending by the next step.'),
                step_class='quartet_output.steps.EPCPyYesFilteredEventOutputStep',
                order=7,
                rule=rule
            )
            queue_outbound_message = Step.objects.create(
                name='Queue Outbound Message',
                description=_('Creates a task and sends it to the delayed '
                              'transport rule or whatever transport rule is '
                              'configured via the Output Rule step parameter.'),
                step_class='quartet_output.steps.CreateOutputTaskStep',
                order=8,
                rule=rule
            )
            output_rule_param = StepParameter.objects.create(
                name='Output Rule',
                description=_('The name of the rule to send the context '
                              'data to.'),
                value='Delayed Transport Rule',
                step=queue_outbound_message
            )
            sdstep = create_transport_rule(rule_name='Delayed Transport Rule',
                                           add_delay=delay_rule)
        sdstep = create_transport_rule()
        return rule


def create_transport_rule(rule_name='Transport Rule', add_delay=False):
    try:
        trule = Rule.objects.create(
            name=rule_name,
            description=_(
                'An output Rule for any data filtered by EPCIS Output Criteria '
                'rules.')
        )
        if add_delay:
            delay_step = Step.objects.create(
                name=_('Wait Three Seconds'),
                description=_(
                    "Wait for three seconds until moving to the next "
                    "step"),
                step_class='quartet_output.steps.DelayStep',
                rule=trule,
                order=1
            )
            delay_step_param = StepParameter.objects.create(
                name='Timeout Interval',
                value='3',
                description=_(
                    'The amount of time in seconds to pause the rule.'),
                step=delay_step
            )

        sdstep = Step.objects.create(
            name=_('Send Data'),
            description=_(
                'This will send the task message using the source EPCIS Output '
                'Critria EndPoint and Authentication Info.'),
            step_class='quartet_output.steps.TransportStep',
            order=2,
            rule=trule
        )
    except IntegrityError:
        trule = Rule.objects.get(name=rule_name)
    return trule


def create_criteria(endpoint_name='Local Echo Server',
                    username=None,
                    criteria_name=None):
    try:
        endpoint = EndPoint.objects.create(
            name=_(endpoint_name),
            urn=_('http://localhost')
        )
    except IntegrityError:
        print('Endpoint already exists.')
        endpoint = EndPoint.objects.get(name=endpoint_name)
    try:
        auth = AuthenticationInfo.objects.create(
            username=_('Test User') or username,
            password=_('Test Password'),
            type='Digest',
            description=_('A test user for the example rule.'))
    except IntegrityError:
        print('Authentication info already exists.')
        auth = AuthenticationInfo.objects.get(username='Test User')
    try:
        output = EPCISOutputCriteria.objects.create(
            name=_('Test Transaction Criteria') or criteria_name,
            action='ADD',
            event_type='Transaction',
            biz_location='urn:epc:id:sgln:305555.123456.0',
            end_point=endpoint,
            authentication_info=auth
        )
    except IntegrityError:
        print('Criteria already exists.')
