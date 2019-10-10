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
import sqlite3

import time
from lxml import etree

from list_based_flavorpack.models import ListBasedRegion
from quartet_capture import models
from quartet_capture.rules import RuleContext, Step


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
