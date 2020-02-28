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
import os

import abc
import sqlite3
import time
from lxml import etree, objectify

from list_based_flavorpack.models import ListBasedRegion
from list_based_flavorpack.processing_classes.third_party_processing.rules import \
    get_region_table
from quartet_capture import models
from quartet_capture.rules import RuleContext, Step
from quartet_integrations.oracle.steps import TradeItemNumberRangeImportStep
from quartet_integrations.tracelink.parsing import TraceLinkPartnerParser, \
    TracelinkMMParser
from serialbox import models as sb_models


class NumberResponseStep(Step):
    '''
    Abstract base class that parses the Number Response returned from a
    tracelink system and allows subclasses to write/store that data as needed.
    '''
    __metaclass__ = abc.ABCMeta

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.serial_number_path = self.get_or_create_parameter(
            'Serial Number Path', './/SerialNo')
        self.strip = self.get_or_create_parameter(
            'Strip Namespaces',
            'False', 'Whether or not to ignore any '
                     'namespaces in the inbound data.').lower() in ('true',)

    def execute(self, data, rule_context: RuleContext):
        """
        Attempts to parse XML response and writes items to a file.
        """
        try:
            root = etree.fromstring(self.get_data(data, rule_context))
            self.strip_namespaces(root)
            machine_name = self.get_machine_name(root, rule_context)
            region = self.get_list_based_region(machine_name)
            self.check_db_state(region)
            number_elements = root.findall(self.serial_number_path)
            self.write_list(number_elements, region)
        except:
            self.info("Error while processing response: %s",
                      self.get_data(data, rule_context))
            raise

    def strip_namespaces(self, root):
        if self.strip:
            for elem in root.getiterator():
                if not hasattr(elem.tag, 'find'): continue
                i = elem.tag.find('}')
                if i >= 0:
                    elem.tag = elem.tag[i + 1:]
            objectify.deannotate(root, cleanup_namespaces=True)

    def check_db_state(self, region):
        if not os.path.exists(region.db_file_path):
            connection = sqlite3.connect(region.db_file_path)
            connection.execute(
                "create table if not exists %s "
                "(serial_number text not null unique, used integer not null)"
                % get_region_table(region)
            )

    def get_list_based_region(self, machine_name):
        """
        Gets the list based region based on the machine name of the region
        first and, if not available, will look for a pool with the machine
        name and pull the list based region from the pool.
        :param machine_name: The machine name of the region or pool
        :return: A ListBasedRegion instance
        """
        try:
            ret = ListBasedRegion.objects.get(machine_name=machine_name)
        except ListBasedRegion.DoesNotExist:
            pool = sb_models.Pool.objects.get(machine_name=machine_name)
            ret = ListBasedRegion.objects.filter(pool=pool)[0]
            if not isinstance(ret, ListBasedRegion):
                raise ListBasedRegion.DoesNotExist(
                    'A list based region '
                    'is not available within'
                    'pool %s' % pool.machine_name
                )
        return ret

    def get_machine_name(self, root: etree.Element, rule_context: RuleContext):
        """
        Override to look up the machine_name in a different fashion.
        :param rule_context: The RuleContext instance
        :return: Returns the machine name of the pool being replenished.
        """
        param = models.TaskParameter.objects.get(
            task__name=rule_context.task_name,
            name='List-based Region'
        )
        return param.value

    def get_data(self, data, rule_context: RuleContext):
        """
        Will look for number response data in the NUMBER_RESPONSE context
        key first and then in the rule data if none is found in the context.
        :param data: The data being processed by the rule
        :param rule_context: The rule context object
        :return: Will return the info in the rule context NUMBER_RESPONSE key
            and/or the data.
        """
        return rule_context.context.get('NUMBER_RESPONSE', None) or data

    @abc.abstractmethod
    def write_list(self, number_elements, region):
        pass

    def on_failure(self):
        super().on_failure()

    @property
    def declared_parameters(self):
        return {}


class FlatFileResponseStep(NumberResponseStep):
    """
    Takes responses from Tracelink systems and writes them to a flat file
    for later use.
    """

    def write_list(self, number_elements, region):
        with open(region.directory_path, "a") as f:
            for id in number_elements:
                f.write("%s\n" % id.text)


class DBResponseStep(NumberResponseStep):
    """
    Takes response data from tracelink systems and writes to the sqlite db
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
                           '(?, ?)' % get_region_table(region), (id.text, 0))
        connection.commit()
        self.info("Execution time: %.3f seconds." % (time.time() - start))


class DiscreteDBResponseStep(DBResponseStep):
    """
    Can parse numbers without having a step before hand that requested numbers.

    This is good for manual uploading of numbers.
    """

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.machine_name_path = self.get_or_create_parameter(
            'Machine Name Path',
            './/ObjectKey/Value',
            'The XPath location of the machine name '
            'in the inbound XML message.')
        self.is_sscc = self.get_or_create_parameter(
            'SSCC Range', "False",
            "Whether or not this is an "
            "SSCC range.  If so, will "
            "use the extension digit"
            " value found in the 'filter value'"
            "field."
        ).lower() in ('true',)
        self.extension_digit = '0'

    def get_machine_name(self, root: etree.Element, rule_context: RuleContext):
        element = root.find(self.machine_name_path)
        if self.is_sscc:
            self.extension_digit = element.attrib.get('filterValue', 0)
            ret = '%s%s' % (self.extension_digit, element.text)
        else:
            ret = element.text
        return ret


class TraceLinkPartnerParsingStep(Step):

    @property
    def declared_parameters(self):
        return {}

    def execute(self, data, rule_context: RuleContext):
        TraceLinkPartnerParser().parse(data)

    def on_failure(self):
        pass


class ExternalTradeItemNumberRangeImportStep(TradeItemNumberRangeImportStep):

    def execute(self, data, rule_context: RuleContext):
        self.info('Invoking the parser.')
        replenishment_size = self.get_integer_parameter('Replenishment Size',
                                                        2000)
        secondary_replenishment_size = self.get_integer_parameter(
            'Secondary Replenishment Size', int(replenishment_size / 2))

        TracelinkMMParser().parse(
            data,
            info_func=self.info,
            response_rule_name=self.get_parameter('Response Rule Name', None,
                                                  True),
            threshold=75000,
            endpoint=self.get_parameter('Endpoint', None, True),
            authentication_info=self.get_parameter('Authentication Info ID',
                                                   None,
                                                   True),
            sending_system_gln=self.get_parameter('Sending System GLN', None,
                                                  True),
            replenishment_size=replenishment_size,
            secondary_replenishment_size=secondary_replenishment_size
        )

        @property
        def declared_parameters(self):
            params = super().declared_parameters
            params[
                'Authentication Info ID'] = 'The ID of the authentication info ' \
                                            'instance to use to communicate with ' \
                                            'external tracelink system.'
            params[
                'Endpoint'] = 'The name of the Endpoint to use to communicate ' \
                              'with TraceLink.'
            params[
                'Sending System GLN'] = 'The GLN that will be used as the "sending systmem' \
                                        ' during template rendering for tracelink.',
            params[
                'Replenishment Size'] = 'The size of the request to the external ' \
                                        'system.'
            params[
                'Secondary Replenishment Size'] = 'To request a smaller amount ' \
                                                  'for secondary packaging use ' \
                                                  'this.'
            return params
