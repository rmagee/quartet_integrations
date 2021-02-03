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
# Copyright 2020 SerialLab Corp.  All rights reserved.
from quartet_capture import models
from quartet_capture.rules import Step, RuleContext
from quartet_epcis.parsing.steps import EPCISParsingStep
from quartet_epcis.parsing.errors import EntryException
from quartet_integrations.generic.parsing import FailedMessageParser
from quartet_output.steps import ContextKeys, CreateOutputTaskStep as COTS
from io import BytesIO


class MyStep(Step):
    def execute(self, data, rule_context: RuleContext):
        self.debug('Executing task...using data %s', data)
        message = self.get_or_create_parameter('Message',
                                               'There was no message defined')
        self.debug('This is the message: %s', message)
        self.info('Finished')

    @property
    def declared_parameters(self):
        return {
            'Message': 'This is the message to display.'
        }

    def on_failure(self):
        self.error('That was a terrible error.')


class EPCISNotifcationStep(EPCISParsingStep):
    # we need to create a task para
    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.output_criteria = self.get_or_create_parameter(
            'Output Criteria',
            'This is the output criteria that contains the location to '
            'send the message.', None
        )

    def execute(self, data, rule_context: RuleContext):
        try:
            return super().execute(data, rule_context)
        except EntryException as ee:
            self.info('Handling an entry exception.')
            message = self.create_messsage(data)
            if message:
                self.info('A message was found.  Will now attempt to send.')
                if self.output_criteria == None:
                    self.error('There is no output criteria defined as a step '
                               'parameter Output Criteria- please set this value.')
                # put it on the context for the output task
                self.info('Placing the message "%s" on the context.', message)
                rule_context.context[
                    ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value] = message
                rule_context.context[
                    ContextKeys.EPCIS_OUTPUT_CRITERIA_KEY.value
                ] = self.output_criteria
            return data

    def create_messsage(self, data):
        # we need to override the basic non-database parser
        parser = FailedMessageParser(BytesIO(data))
        parser.parse()
        # now we access to the class fields
        if parser.shipping_event:
            return """The following EPCs were shipped but were not
            correlated to any serialized data received from a trading partner:
            {0}
            These EPCs were part of sales order {1}.
            """.format(parser.epc_list, parser.biz_transaction)


class CreateOutputTaskStep(COTS):
    def execute(self, data, rule_context: RuleContext):
        super().execute(data, rule_context)
        if rule_context.context.get(
            ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value) and \
            rule_context.context.get(
                ContextKeys.EPCIS_OUTPUT_CRITERIA_KEY.value):
            raise self.FailedShipmentException(
                rule_context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value])

    class FailedShipmentException(Exception):
        pass
