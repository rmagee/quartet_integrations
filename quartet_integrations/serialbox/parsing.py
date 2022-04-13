import logging
import csv

from serialbox.models import Pool, ResponseRule, \
    CONTENT_TYPE_CHOICES
from quartet_capture.models import Rule

logger = logging.getLogger(__name__)


class UpdateResponseRuleParser:
    """

    """

    def __init__(self,
                 raise_exception):
        self.raise_exception = raise_exception
        self.errors = []

    def __str__(self):
        return '%s.%s' % (self.__module__, self.__class__)

    def parse(self, data: str):
        """
        Will parse the data from csv file row by row and try 
        updating or adding a new ResponseRule according to the 
        currently processed data row
        :param data: data that will be parsed by this method.
        :return: None
        """
        parsed_data = csv.DictReader(data)
        for idx, datarow in enumerate(parsed_data):
            self.handle_data_row(datarow, idx)

    def handle_data_row(self, data_row: dict, idx: int):
        """
        Will handle the data row, get the correct number pool, 
        rule and try to verify if the content_type is correct.
        If everything is correct then the ResponseRules will be 
        either added or updated.
        :param data_row: currently processed row from inbound csv data.
        :param idx: data row number
        """
        pool = self.get_number_pool(data_row['api_key'], idx)
        rule = self.get_rule(data_row['rule_name'], idx)
        # handle format
        content_type = self.get_content_type(
            data_row['content_type'], idx)
        if pool and rule and content_type:
            self.handle_response_rule(pool, rule, content_type)

    def get_number_pool(self, api_key: str, idx: int) -> Pool:
        """
        Will try to get the number pool model instance based on
        the api_key (machine_name) parameter. Also will handle 
        the "DoesNotExist" exception.
        :param api_key: machine_name value from Pool model
        :param idx: data row number
        """
        try:
            pool = Pool.objects.get(machine_name=api_key)
        except Pool.DoesNotExist as err:
            self.handle_exception(
                api_key, err, idx,
                exception_class=Pool.DoesNotExist
            )
            pool = None
        return pool

    def get_rule(self, rule_name: str, idx: int) -> Rule:
        """
        Will try to get the rule model instance based on the
        name parameter. Also will handle the "DoesNotExist" 
        exception.
        :param rule_name: name value from Rule model
        :param idx: data row number
        """
        try:
            rule = Rule.objects.get(name=rule_name)
        except Rule.DoesNotExist as err:
            self.handle_exception(
                rule_name, err, idx,
                exception_class=Rule.DoesNotExist
            )
            rule = None
        return rule

    def get_content_type(self, content_type: str, idx: int):
        """
        Will try to get verify if the content_type value is supported.
        Also if the provided data is incorrect the exception will be handled
        exception.
        :param content_type: 
        :param idx: data row number
        """
        if content_type in [choice[0] for choice in CONTENT_TYPE_CHOICES]:
            return content_type
        else:
            error_message = 'Row %d: The provided content type "%s"' \
                            ' is not supported' % (idx, content_type)
            self.handle_exception(
                content_type, error_message, idx,
                exception_class=self.NotSupportedContentType)
            return None

    def handle_response_rule(self,
                             pool: Pool,
                             rule: Rule,
                             content_type: str):
        """
        Will add or update a Response rule based on number pool 
        instance and content type and the provided Rule will be 
        configured to provide the responses.
        :param pool: number pool instance
        :param rule: rule instance
        :param content_type: supported content type
        """
        try:
            response_rule = ResponseRule.objects.get(
                pool=pool,
                content_type=content_type
            )
            if response_rule.rule != rule:
                response_rule.rule = rule
                response_rule.save()
        except ResponseRule.DoesNotExist as err:
            response_rule = ResponseRule.objects.create(
                pool=pool,
                rule=rule,
                content_type=content_type
            )
        return response_rule

    def handle_exception(self,
                         value,
                         err,
                         idx,
                         exception_class=None):
        """
        This method will handle exceptions and properly 
        formulate any error messages to include data row number 
        and the incorrect data from the currently processed row.
        Also if the parameter "Raise Exceptions" is set to False then 
        the exceptions won't be raised but the information about any 
        failed data row will be saved to the errors list.
        :param value: the value that is causing this error to appear.
        :param err: error message from the handled exception.
        :param idx: row number where the exception appeared.
        :param exception_class: class of the handled exception.
        """
        error_message = 'Row %d - "%s": %s' % (idx + 2, value, err)
        if self.raise_exception:
            if exception_class:
                raise exception_class(error_message)
            else:
                raise
        else:
            self.errors.append(error_message)

    class NotSupportedContentType(Exception):
        pass
