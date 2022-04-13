import os
from urllib import response
from django.test import TestCase
from quartet_capture.models import Rule, Step, Task
from quartet_capture.tasks import execute_rule
from serialbox.management.commands.load_test_pools import Command \
    as LoadPools
from serialbox.management.commands.create_response_rule import Command \
    as CreateResponseRule
from serialbox.models import Pool, ResponseRule


class TestResponseRuleUpdateStep(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self._create_update_rule()

    def _create_update_rule(self):
        self.rule = Rule.objects.create(
            name='Update Response Rules',
            description='unittest'
        )
        Step.objects.create(
            name='Prase CSV',
            description='unittest',
            rule=self.rule,
            step_class='quartet_integrations.serialbox'
                       '.steps.ResponseRulesUpdateStep',
            order=1
        )
        return self.rule

    def _get_data(self, filename='update_response_rules.csv'):
        curdir = os.path.dirname(__file__)
        file_path = os.path.join(curdir,
                                 'data',
                                 'serialbox',
                                 filename)
        with open(file_path, 'r') as f:
            data = f.read()
        return data

    def _create_task(self, rule):
        return Task.objects.create(
            rule=rule,
            name='unittest task'
        )

    def test_update_respone_rules(self):
        # create number pool
        LoadPools().handle()
        pool = Pool.objects.first()
        # create response rules
        CreateResponseRule().handle()
        rule = Rule.objects.get(name='SB Response Rule')
        # assign response rule
        response_rule = ResponseRule.objects.create(
            pool=pool,
            rule=rule,
            content_type='xml'
        )
        # create another response rule
        rule_2 = Rule.objects.create(
            name='Response Rule 2',
            description='unittest')
        db_task = self._create_task(self.rule)
        data = self._get_data()
        result = execute_rule(data.encode(), db_task)
        response_rule.refresh_from_db()
        self.assertEquals(response_rule.rule, rule_2)

    def test_add_respone_rules(self):
        # create number pool
        LoadPools().handle()
        pool = Pool.objects.first()
        # create another response rule
        rule_2 = Rule.objects.create(
            name='Response Rule 2',
            description='unittest')

        db_task = self._create_task(self.rule)
        data = self._get_data()
        result = execute_rule(data.encode(), db_task)

        response_rule = ResponseRule.objects.get(pool=pool,
                                                 content_type='xml')
        self.assertEquals(response_rule.rule, rule_2)

    def test_response_rule_for_non_existing_pool(self):
        rule_2 = Rule.objects.create(
            name='Response Rule 2',
            description='unittest')
        db_task = self._create_task(self.rule)
        data = self._get_data()
        with self.assertRaises(Pool.DoesNotExist):
            execute_rule(data.encode(), db_task)

    def test_no_rule_test(self):
        LoadPools().handle()
        pool = Pool.objects.first()
        # create response rules
        CreateResponseRule().handle()
        rule = Rule.objects.get(name='SB Response Rule')
        # assign response rule
        response_rule = ResponseRule.objects.create(
            pool=pool,
            rule=rule,
            content_type='xml'
        )
        db_task = self._create_task(self.rule)
        data = self._get_data()
        with self.assertRaises(Rule.DoesNotExist):
            execute_rule(data.encode(), db_task)
