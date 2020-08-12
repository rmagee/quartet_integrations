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
import logging

from serialbox.models import Pool, SequentialRegion

from quartet_capture import models
from quartet_capture.rules import Step, RuleContext
from quartet_masterdata.db import DBProxy
from quartet_masterdata.models import TradeItem
from gs123.conversion import BarcodeConverter, URNConverter
from gs123 import check_digit

logger = logging.getLogger(__name__)


class ListToUrnConversionStep(Step):
    """
    Converts serialbox lists to EPCIS URNs using the data in the result.
    """

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.get_or_create_parameter('Company Prefix Length',
                                     '0', 'The length of the company prefix '
                                          'to use during URN conversions.'
                                          'if set to zero, the system will '
                                          'look up the company prefix length '
                                          'in the master data in the company '
                                          'and Trade Item areas.')
        self.get_or_create_parameter('Serial Number Length', '12',
                                     'If padding serial numbers with zeros, '
                                     'supply a length so that the system knows'
                                     ' how to pad the serial number field of '
                                     ' urns accordingly.'
                                     )

    def execute(self, data, rule_context: RuleContext):
        """
        Inbound data should be in list format.
        :param data: The serial number response from serialbox.
        :param rule_context: The rule context.
        """
        task_params = self.get_task_parameters(rule_context)
        pool = task_params['pool']

        self.info('Working against Pool with machine name %s', pool)

        self.info('Looking up the company prefix by using the pool '
                  'machine name / API Key value %s and matching against '
                  'a Trade Item and/or Company in the master data '
                  'configuration', pool)
        cp_length = DBProxy().get_company_prefix_length(pool)
        rule_context.context['company_prefix_length'] = cp_length
        # if we are dealing with gtins we need to make urn values sans the
        # epc declaration
        return_vals = []
        if len(pool) == 14:
            converter = self.handle_gtins(cp_length, data, return_vals, pool,
                                          rule_context)
            # put some of the info on the context in case other steps may need
            rule_context.context['company_prefix'] = converter.company_prefix
            rule_context.context['indicator_digit'] = converter.indicator_digit
            rule_context.context['item_reference'] = converter.item_reference
            rule_context.context[
                'saleable_unit_flag'] = 1 if converter.indicator_digit == '0' else 0
        elif len(pool) == 18:
            self.handle_ssccs(cp_length, data, return_vals, pool)

        return return_vals

    def handle_gtins(self, cp_length, numbers, return_vals, pool,
                     rule_context):
        """
        Override this function to look up trade item information, and to
        handle inbound GTIN requests.  This function adds the TradeItem matching
        the pool.machine_name to the context for downstream Steps (such as
        a template step) to use the trade item information for rendering, etc.

        This cuntion will also determine the company prefix. Indicator digit
        and item reference number for the given request in order to render
        accurate URN values.
        :param cp_length: The company prefix length.
        :param numbers: The list of numbers to convert to SGTIN URNs
        :param return_vals: The list that will hold the converted URNs
        :param pool: The pool.machine name that was used to get the numbers...
            this should correlate to a Trade Item.
        :param rule_context: The rule context to place the Trade Item django
            model instance onto.
        """
        rule_context.context['trade_item'] = TradeItem.objects.get(
            GTIN14=pool
        )
        self.info('Formatting for GTIN response.')
        # provide a dummy serial number so we can just quickly parse the company prefix
        converter = BarcodeConverter(
            '01%s21%s' % (pool, '000000000001'), cp_length)
        for number in numbers:
            return_vals.append(
                self.format_gtin_urn(
                    converter.company_prefix,
                    converter.indicator_digit,
                    converter.item_reference,
                    number
                )
            )
        return converter

    def handle_ssccs(self, cp_length, numbers, return_vals, sb_response):
        raise NotImplementedError('handle_ssccs is not currently implemented.')

    def format_gtin_urn(self, company_prefix: str, indicator: str,
                        item_reference: str, serial_number: str):
        """
        Override to provide an alternate URN format.
        :param company_prefix: The company prefix
        :param indicator: The indicator digit
        :param item_reference: The item reference number
        :param serial_number: The serial number
        :return: Returns an SGTIN URN.
        """
        return '%s%s.%s%s.%s' % (
            'urn:epc:id:sgtin:', company_prefix, indicator, item_reference,
            serial_number
        )

    def on_failure(self):
        pass

    @property
    def declared_parameters(self):
        return {}


class RequestLoggingStep(Step):
    """
    Just logs inbound request into the task messages and logs to the
    log file as well.  Useful but also just an example of simple Step
    development.
    """

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.log_to_file = self.get_or_create_parameter(
            'Log To File',
            'True',
            'Whether or not to log task data to the log file.'
        )
        self.log_to_task_messages = self.get_or_create_parameter(
            'Log To Task Messages',
            'True',
            'Whether or not to log task data to the Task Messages.'
        )

    def execute(self, data, rule_context: RuleContext):
        self.info('Logging data to the log file...')
        if self.log_to_file.lower() == 'true':
            logger.debug(data)
        if self.log_to_task_messages.lower() == 'true':
            self.debug(data)

    @property
    def declared_parameters(self):
        return {
            'Log To File': 'Whether or not to log task data to the log file.'
                           ' Default = True.  Log level for these messages '
                           'is DEBUG...so you will not see requests in the'
                           ' log until you set the logging level accordingly.',
            'Lot to Task Messages': 'Whether or not to log task data to the '
                                    'Task Messages.  Default is True.'
        }

    def on_failure(self):
        pass


class ListToBarcodeConversionStep(Step):
    """
    Converts a serialbox list to barcodes using the pool.machine_name as
    the GTIN 14 and/or SSCC-18.
    """

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.serial_number_length = int(self.get_or_create_parameter(
            'Serial Number Length', '12',
            'If padding serial numbers with zeros, '
            'supply a length so that the system knows'
            ' how to pad the serial number field of '
            ' urns accordingly.'
        ))

        self.padding = self.get_or_create_parameter(
            'Serial Number Padding', 'True',
            'Whether or not to pad serial numbers for GTINS.'
        ).lower() == 'true'

        self.use_parenthesis = self.get_or_create_parameter(
            'Use Parenthesis', 'False',
            'Whether or not to use parenthesis around app identifiers within'
            'the number output.'
        ).lower() == 'true'

        self.sscc_app_identifier = self.get_or_create_parameter(
            'SSCC App Identifier', 'False',
            'A boolean flag that sets whether or not the SSCC app identifier'
            ' is included in SSCC return values.'
        ).lower() == 'true'

        self.extension_digit = int(self.get_or_create_parameter(
            'Extension Digit', '0',
            'A single numeric value from 0-9 for any SSCC responses.'
        ))

        self.company_prefix = self.get_or_create_parameter(
            'Company Prefix', '',
            'If serving SSCC values using this step in a Response Rule, '
            'you must configure the company prefix for SSCC values '
            'explicitly in the step.  This is Not used for GTINs.'
        )

        if self.extension_digit > 9 or self.extension_digit < 0:
            raise DBProxy.CompanyConfigurationError(
                'The extension for the ListToBarcodeConversionStep must be '
                'from 0-9, current value: %s' % self.extension_digit
            )

    def execute(self, data, rule_context: RuleContext):
        """
        Inbound data should be in JSON format.
        :param data: The serial number response from serialbox.
        :param rule_context: The rule context.
        """
        task_params = self.get_task_parameters(rule_context)
        pool = task_params['pool']

        self.info('Working against Pool with machine name %s', pool)

        self.info('Looking up the company prefix by using the pool '
                  'machine name / API Key value %s and matching against '
                  'a Trade Item and/or Company in the master data '
                  'configuration', pool)
        return_vals = []
        if len(pool) == 14:
            self.handle_gtins(data, return_vals, pool, rule_context)
        else:
            self.handle_ssccs(data, return_vals, pool, rule_context)

        return return_vals

    def handle_gtins(self, numbers, return_vals, pool,
                     rule_context):
        """
        Override this function to look up trade item information, and to
        handle inbound GTIN requests.  This function adds the TradeItem matching
        the pool.machine_name to the context for downstream Steps (such as
        a template step) to use the trade item information for rendering, etc.

        This cuntion will also determine the company prefix. Indicator digit
        and item reference number for the given request in order to render
        accurate URN values.
        :param cp_length: The company prefix length.
        :param numbers: The list of numbers to convert to SGTIN URNs
        :param return_vals: The list that will hold the converted URNs
        :param pool: The pool.machine name that was used to get the numbers...
            this should correlate to a Trade Item.
        :param rule_context: The rule context to place the Trade Item django
            model instance onto.
        """
        rule_context.context['trade_item'] = TradeItem.objects.get(
            GTIN14=pool
        )
        self.info('Formatting for GTIN response.')
        if self.use_parenthesis:
            format = '(01)%s(21)%s'
        else:
            format = '01%s21%s'

        for number in numbers:
            return_vals.append(
                self.format_gtin_barcode(pool, number, format)
            )

    def format_gtin_barcode(self, pool: str, serial_number: int,
                            format: str) -> str:
        """
        Override to provide a different format.  This function formats
        the pool.machine_name (the GTIN) and the serial number according
        to the settings derived via the step parameters.
        :param pool: The machine_name of the current pool being requested from.
        :param serial_number: The serial number returned from the allocate
            api.
        :param format: A python format string.
        :return: A formatted GTIN barcode value.
        """
        if self.padding:
            serial_number = str(serial_number).zfill(self.serial_number_length)
        return format % (pool, serial_number)

    def handle_ssccs(self, data: list, return_vals: list, pool: str,
                     rule_context: RuleContext):
        """
        Handles the formatting of SSCCs from this Step.  The function
        populates the return_vals parameter with formatted numbers.

        :param data: The list of serial numbers returned from serial box.
        :param return_vals: The list to return to the rule.
        :param pool: The machine name of the pool that executed the
        serialbox request.
        :param rule_context: The RuleContext instance for the currently
            executing rule.
        :return: None
        """
        sequential = Pool.objects.prefetch_related('sequentialregion_set').filter(
            machine_name=pool
        ).count()
        if self.company_prefix == '':
            raise self.InvalidCompanyPrefix(
                'The company prefix must be configured in the Response Rule '
                'using the step parameter Company Prefix in the '
                'ListToBarcodeConverstionStep step configuration..'
            )
        padding = 17 - (len(self.company_prefix) + 1)
        for number in data:
            return_vals.append(
                self.format_sscc_barcode(number, padding)
            )

    def format_sscc_barcode(self, number: int, padding: int) -> str:
        """
        Override to provide a different format.  This function formats the
        pool.machine_name and the serial number according to the settings
        derived by the current step parameters.
        :param pool: The pool machine name.
        :param number:
        :param company_prefix:
        :return: A formatted SSCC value
        """
        number = str(number).zfill(padding)
        if self.use_parenthesis:
            sscc_val = '(00)%s%s%s' % (
                self.extension_digit, self.company_prefix, number
            )
        else:
            sscc_val = '%s%s%s' % (self.extension_digit, self.company_prefix,
                                   number)
        return check_digit.calculate_check_digit(sscc_val)

    def on_failure(self):
        pass

    def declared_parameters(self):
        return {
            'Serial Number Length': 'The length of the company prefix '
                                    'to use during URN conversions.'
                                    'if set to zero, the system will '
                                    'look up the company prefix length '
                                    'in the master data in the company '
                                    'and Trade Item areas.',
            'Serial Number Padding': 'Whether or not to pad serial numbers '
                                     'for GTINS.',

            'Use Parenthesis': 'Whether or not to use parenthesis '
                               'around app identifiers within'
                               'the number output.',
            'SSCC App Identifier': 'True or False- whether or not to include '
                                   'the Application Identifier for SSCC values'
                                   ' in the response.',
            'Extension Digit':'The extension digit for SSCCs (does not apply '
                              'to GTINs.',
            'Company Prefix':'The company prefix must be supplied for handling'
                             ' SSCC values.',
        }


    class InvalidCompanyPrefix(Exception):
        pass
