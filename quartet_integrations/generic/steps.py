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
from quartet_capture import models, errors as capture_errors
from quartet_capture.rules import Step, RuleContext
from quartet_epcis.parsing.steps import EPCISParsingStep
from quartet_epcis.parsing.errors import EntryException
from quartet_integrations.generic.parsing import FailedMessageParser
from quartet_output.steps import ContextKeys, CreateOutputTaskStep as COTS
from io import BytesIO
from quartet_output.steps import TransportStep
from quartet_output.models import EPCISOutputCriteria, EndPoint
from django.utils.translation import gettext as _

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
                models.TaskParameter.objects.create(
                    name='EPCIS Output Criteria',
                    value=self.output_criteria,
                    description='Contains Endpoint infomation about'
                                'where to send the error message to.',
                    task=self.task)
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


class ErrorReportTransportStep(TransportStep):
    """
    In case of EntryException in  EPCISNotifcationStep (parsing step)
    notification is sent with error report to the specified end point in
    EPCIS Output Criteria (by default this should be an email - mailto).
    If no EntryException then this step is skipped.
    """

    def execute(self, data, rule_context: RuleContext):
        if rule_context.context.get(
                ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value, None):
            # Error msg found
            self.info('Performing error message routine.')
            super().execute(data, rule_context)
            self.info('Error message sent successfully.')
            raise self.FailedShipmentException(
                rule_context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value])
        else:
            self.info('There was no entry error so this step is skipped.')


    def send_email(self, data: str, rule_context: RuleContext,
                   output_criteria: EPCISOutputCriteria,
                   info_func,
                   file_extension='txt',
                   mimetype='text/plain'):
        '''
        Inserts/Changes body param into the mailto email and then
        runs original send_email method. 

        :param data: The data to send.
        :param rule_context: The quartet capture rules.RuleContext instance
            from the currently running rule.
        :param output_criteria: The models.OutputCriteria instance from the
            current TransportStep being executed.
        :param info_func: The info logging function from the calling step
            class.
        :param file_extension: This is the file extension for the attachement
            being sent.  It is best to leave it as txt even if the "real" data is
            JSON or XML since many email filters will block those formats.
        :param mimetype: The mimetype of the attachment.  Default is text/plain.
        :return: None.
        '''
        # Get message body text from rule_context
        msg_body = rule_context.context[
                    ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value
                ]
        # temporarily change output_criteria.end_point.urn so it 
        # contains correct message inside body paramerer
        self.info('Assembling body from the message email message.')
        output_criteria.end_point.urn = self.set_email_fields(
            output_criteria.end_point.urn, msg_body
        )
        self.info('Email message assembled.')
        # Execute original send_email method to send thr email
        super().send_email(
            data,
            rule_context,
            output_criteria,
            self.info,
            file_extension,
            mimetype
        )

    def set_email_fields(self, mailto: str,
                         body: str,
                         ):
        """
        Inserts or changes body praam in an email in mailto format

        :param mailto: email urn in mailto format

        :param body: message which will be inserted into body
        
        :return: new mailto urn with body param inserted
        """
        # Separate email address from parameters
        try:
            email_address, parameters = mailto.split('?')
        except ValueError:
            # in case of no params join body and return
            return '?'.join([mailto, 'body=%s' % body])
        # Separate parameters
        parameters = parameters.split('&')
        # Find body parameter
        # If there is no body param then "index_of" will be -1
        index_of = -1
        try:
            for param in parameters:
                if param.lower().startswith('body='):
                    index_of = parameters.index(param)
                    break
        except ValueError:
            pass
        # Add/Set body param
        if index_of == -1:
            parameters.append('body=%s' % body)
        else:
            parameters[index_of] = 'body=%s' % body
        # reassemble email address with params
        parameters = '&'.join(parameters)
        ret = '?'.join([email_address, parameters])
        # and then return it
        return ret

    class FailedShipmentException(Exception):
        pass
