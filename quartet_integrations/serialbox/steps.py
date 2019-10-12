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

from quartet_capture import models
from quartet_capture.rules import Step, RuleContext
from quartet_masterdata.db import DBProxy, TradeItem
from gs123.conversion import BarcodeConverter, URNConverter

logger = logging.getLogger(__name__)


class ListToUrnConversionStep(Step):
    """
    Converts serialbox lists to OPSM URNs using the data in the result.
    """

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.get_or_create_parameter('Company Prefix Length',
                                     '0', 'The lenght of the company prefix '
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

    def handle_gtins(self, cp_length, numbers, return_vals, pool, rule_context):
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
