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
# Copyright 2018 SerialLab Corp.  All rights reserved.
import abc
import os
import sqlite3
import time
from lxml import etree
from list_based_flavorpack.models import ListBasedRegion
from quartet_capture.rules import RuleContext, Step
from quartet_integrations.rfxcel.environment import get_default_environment
from quartet_output.steps import ContextKeys, EPCPyYesOutputStep
from EPCPyYes.core.v1_2 import template_events
from quartet_capture import models
from list_based_flavorpack.processing_classes.third_party_processing.rules import \
    get_region_table
from quartet_capture.models import Task, TaskParameter
from serialbox.models import Pool, SequentialRegion


class RFExcelOutputStep(EPCPyYesOutputStep):

    def _get_new_template(self):
        """
        Grabs the jinja environment and creates a jinja template object and
        returns
        :return: A new Jinja template.
        """
        env = get_default_environment()
        template = env.get_template('rfxcel/rfxcel_commissioning_event.xml')
        return template

    def _get_shipping_template(self):
        """
        Returns a shipping event template for use by the filtered event.
        :return: A jinja template object.
        """
        env = get_default_environment()
        template = env.get_template('rfxcel/rfxcel_shipping_event.xml')
        return template

    def _get_aggregation_template(self):
        """
        Returns an aggregation event template for use by the filtered event.
        :return: A jinja template object.
        """
        env = get_default_environment()
        template = env.get_template('rfxcel/rfxcel_aggregation_event.xml')
        return template

    def execute(self, data, rule_context: RuleContext):
        # two events need new templates - object and shipping
        # the overall document needs a new template get that below
        # if filtered events has more than one event then you know
        # the event in filtered events is a shipping event so grab that
        # and give it a new template
        filtered_events = rule_context.context.get(
            ContextKeys.FILTERED_EVENTS_KEY.value)
        if len(filtered_events) > 0:
            template = self._get_shipping_template()
            filtered_events[0]._template = template
            # get the object events from the context - these are added by
            # the AddCommissioningDataStep step in the rule.
            object_events = rule_context.context.get(
                ContextKeys.OBJECT_EVENTS_KEY.value, [])
            if len(object_events) > 0:
                # here you are changing the object event templates
                template = self._get_new_template()
                for event in object_events:
                    event._template = template

            aggregation_events = rule_context.context.get(
                ContextKeys.AGGREGATION_EVENTS_KEY.value, [])

            if len(aggregation_events) > 0:
                template = self._get_aggregation_template()
                for event in aggregation_events:
                    event._template = template

        super().execute(data, rule_context)

    def get_epcis_document_class(self,
                                 all_events) -> template_events.EPCISEventListDocument:
        """
        This function will provide a template with EPCISDocument and EPCISHeader
        template
        :param all_events: The events to add to the document
        :return: The EPCPyYes event list document to render
        """
        doc_class = super().get_epcis_document_class(all_events)
        env = get_default_environment()
        template = env.get_template('rfxcel/rfxcel_epcis_document.xml')
        doc_class._template = template
        return doc_class

    @property
    def declared_parameters(self):
        return super().declared_parameters


class NumberResponseStep(Step):
    '''
    Parses the Number Response and writes them to a file in list-based format.
    '''
    __metaclass__ = abc.ABCMeta

    def execute(self, data, rule_context: RuleContext):
        '''
        Attempts to parse XML response and writes items to a file.
        '''
        param = models.TaskParameter.objects.get(
            task__name=rule_context.task_name,
            name='List-based Region'
        )

        region = ListBasedRegion.objects.get(machine_name=param.value)
        try:
            root = etree.fromstring(rule_context.context["NUMBER_RESPONSE"])
            id_list = root.find(
                './/{http://xmlns.rfxcel.com/traceability/identifier/3}idList')
            self.write_list(id_list, region)
        except TypeError:
            self.error('The rfXcel system failed to return a list of numbers.'
                       ' Response:', rule_context.context["NUMBER_RESPONSE"])
            raise

    @abc.abstractmethod
    def write_list(self, id_list, region):
        pass

    @abc.abstractmethod
    def write_range(self, id_list, region):
        pass

    def on_failure(self):
        super().on_failure()

    @property
    def declared_parameters(self):
        return {}


class FlatFileResponseStep(NumberResponseStep):
    """
    Takes responses from rfexcel systems and writes them to a flat file
    for later use.
    """

    def write_list(self, number_elements, region):
        with open(region.directory_path, "a") as f:
            for id in number_elements:
                f.write("%s\n" % id.text)


class DBResponseStep(NumberResponseStep):
    """
    Takes response data from rfexcel systems and writes to the sqlite db
    database file if the region supports that.
    """

    def write_range(self, end, region, sb_start, start):
        raise NotImplementedError('This number response step does not handle '
                                  'range based information.')

    def write_list(self, number_elements, region: ListBasedRegion):
        start = time.time()
        connection = sqlite3.connect(region.db_file_path)
        cursor = connection.cursor()
        cursor.execute('begin transaction')
        self.info('storing the numbers.')
        for id in number_elements:
            cursor.execute('insert into %s (serial_number, used) values '
                           '(?, ?)' % region.machine_name, (id, 0))
        cursor.execute('commit')
        self.info("Execution time: %.3f seconds." % (time.time() - start))


class RFXCELNumberResponseParserStep(Step):
    '''
    Parses the Number Response and writes them to a file in list-based format.
    '''

    def execute(self, data, rule_context: RuleContext):
        '''
        Attempts to parse XML response and writes items to a file.
        '''
        param = models.TaskParameter.objects.get(
            task__name=rule_context.task_name,
            name='List-based Region'
        )

        region = ListBasedRegion.objects.get(machine_name=param.value)
        try:
            root = etree.fromstring(rule_context.context["NUMBER_RESPONSE"])
            id_list = root.find(
                './/{http://xmlns.rfxcel.com/traceability/identifier/3}idList')

            numbers = []

            for urn in id_list:
                # store the serial numbers in the array
                if "sgtin" in urn.text:
                    numbers.append(urn.text.split('.')[2])
                if "sscc" in urn.text:
                    sn = urn.text.split(":")[4].split('.')[1][1:]
                    numbers.append(sn)

            if not os.path.exists(region.db_file_path):
                connection = sqlite3.connect(region.db_file_path)
                connection.execute(
                    "create table if not exists %s "
                    "(serial_number text not null unique, used integer not null)"
                    % get_region_table(region)
                )
            else:
                connection = sqlite3.connect(region.db_file_path)

            start = time.time()
            cursor = connection.cursor()
            cursor.execute('begin transaction')
            self.info('storing the numbers. {0}'.format(region.db_file_path))
            for id in numbers:
                cursor.execute('insert into %s (serial_number, used) values '
                               '(?, ?)' % get_region_table(region), (id, 0))
            connection.commit()
            self.info("Execution time: %.3f seconds." % (time.time() - start))
        except:
            self.info("Error while processing response: %s",
                      rule_context.context["NUMBER_RESPONSE"])
            raise

    def on_failure(self):
        super().on_failure()

    @property
    def declared_parameters(self):
        return {}


class SerialboxSSCCConversionStep(Step):
    """
    Converts serial box sequential or random numbers to the right format
    for an SSCC response for an rfXcel request.

    The machine name for any pool using this in a response rule must be in
    the format of the extension digit plus the company prefix as one set
    of digits, for example 00355555- where the first zero is the extension
    digit and the 0355555 would be the company prefix.
    """

    def execute(self, data, rule_context: RuleContext):
        # get the task
        create_urns = self.get_or_create_parameter(
            'Create URNs', 'True',
            'If set to true URNs will be created, if false '
            'the "packaging line" format will be used'
        ).lower() == 'true'
        db_task = Task.objects.get(name=rule_context.task_name)
        self.info('Executing against pool ')
        machine_name = db_task.taskparameter_set.get(name='pool').value
        self.info('Executing against pool %s.', machine_name)
        # the first digit of the machine name is the extension digit
        is_sequential = Pool.objects.get(
            machine_name=machine_name).sequentialregion_set.count() != 0

        self.info('Is sequential? %s', is_sequential)
        # the length of the company prefix is available
        cp_len = len(machine_name[1:])
        # the length of the serial number is the company prefix len - 16
        num_len = 16 - cp_len
        self.info('Number length = %s', num_len)
        # if sequential you need to create a list
        if is_sequential:
            data = [str(num).zfill(num_len) for num in range(data[0], data[1])]
        else:
            data = [str(num).zfill(num_len) for num in data]
        if create_urns:
            data = self.convert_numbers_to_urn(data, machine_name)
        return data

    def convert_numbers_to_urn(self, data: list, machine_name: str):
        """
        Converts the serial-numbers to URNs if the Create URN step
        parameter is set.
        :param data: The serial numbers
        :param machine_name: The machine name of the pool
        :return: A list of urns.
        """
        # get the company prefix and extension digit from the machine name
        company_prefix = machine_name[1:]
        extension_digit = machine_name[:1]
        return ['urn:epc:id:sscc:%s.%s%s' %
                (company_prefix, extension_digit, d) for d in data]

    def on_failure(self):
        super().on_failure()

    @property
    def declared_parameters(self):
        return {'Create URNs': 'If set to true URNs will be created, if false '
                               'the "packaging line" format will be used'}
