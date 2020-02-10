import os

from quartet_capture.models import Rule, StepParameter, Step
from quartet_masterdata.models import TradeItem, Company
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

    create_template()
    pool = Pool.objects.get(machine_name='00313000007772')
    response_rule = ResponseRule.objects.get_or_create(
        rule=rule,
        pool=pool,
        content_type='xml'
    )


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
    pool = Pool.objects.get(machine_name='031300000770000001')
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
        machine_name='031300000770000001',
        active=True,
        request_threshold=1000
    )
    # 031300 + 00000000000 + 1 = 18
    # the max length of the serial number is 99999999999
    models.RandomizedRegion.objects.create(
        readable_name='Pharmaprod 20mcg Pills',
        machine_name='031300000770000001',
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
        machine_name='031300000770000001',
        active=True,
        request_threshold=1000
    )
    # 031300 + 00000000000 + 1 = 18
    # the max length of the serial number is 99999999999
    SequentialRegion.objects.create(
        readable_name='Pharmaprod 20mcg Pills',
        machine_name='031300000770000001',
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
