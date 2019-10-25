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

import os, sys
from django.test import TestCase
from quartet_tracelink.utils import TraceLinkHelper
from quartet_capture import models as capture_models
from quartet_capture.tasks import create_and_queue_task
from list_based_flavorpack.models import ListBasedRegion
from serialbox import models as sb_models


class ResponseParsingTestCase(TestCase):

    def __init__(self, methodName: str = ...) -> None:
        super().__init__(methodName)
        self.curpath = os.path.dirname(__file__)
        self.nr_response_parser = (
            'quartet_integrations.tracelink.steps.DiscreteDBResponseStep')

    def create_list_based_region(self):
        # create pool
        test_pool = sb_models.Pool()
        test_pool.readable_name = "Test Pool"
        test_pool.machine_name = "00300077789102"
        test_pool.active = True
        test_pool.request_threshold = 1000
        test_pool.save()

        list_based_region = ListBasedRegion()
        list_based_region.pool = test_pool
        list_based_region.processing_class_path = (
            "list_based_flavorpack."
            "processing_classes.third_party_processing."
            "processing.ThirdPartyProcessingClass"
        )
        list_based_region.directory_path = "/tmp"
        list_based_region.number_replenishment_size = 20
        list_based_region.save()

        self.assertEqual("/tmp/" + str(list_based_region.file_id),
                         list_based_region.file_path)
        return list_based_region

    def create_rule(self, create_step_param=False):
        rule, created = capture_models.Rule.objects.get_or_create(
            name="Tracelink Number Response"
        )
        if created:
            rule.description = 'Requests numbers from Tracelink - To be used ' \
                               'from Number Range module (Allocate)'
            rule.save()
            step_1 = capture_models.Step()
            step_1.name = 'Tracelink Number Reponse Parser'
            step_1.description = ('Parses numbers from Tracelink and writes '
                                  'them persistently for use in Number '
                                  'Range module.')
            step_1.step_class = self.nr_response_parser
            step_1.order = 1
            step_1.rule = rule
            step_1.save()

            if create_step_param:
                step_param = capture_models.StepParameter.objects.create(
                    name='Serial Number Path',
                    value='.//SerialNumber',
                    step=step_1
                )
                step_param = capture_models.StepParameter.objects.create(
                    name='Strip Namespaces',
                    value='True',
                    step=step_1
                )
                step_param = capture_models.StepParameter.objects.create(
                    name='Machine Name Path',
                    value='./MessageBody/ObjectIdentifier/GTIN-14',
                    description='Unit test...',
                    step=step_1
                )

        return rule

    def delete_db_file(self, region):
        os.remove(region.db_file_path)

    def setUp(self) -> None:
        region = self.create_list_based_region()
        try:
            self.delete_db_file(region)
        except FileNotFoundError:
            pass

    def test_response_parsing(self):
        self.create_rule()
        data_path = os.path.join(self.curpath,
                                 'data/standard_tl_response.xml')

        with open(data_path) as f:
            data = f.read()
            create_and_queue_task(data, 'Tracelink Number Response',
                                  run_immediately=True)

    def test_namespaced_response_parsing(self):
        self.create_rule(create_step_param=True)
        data_path = os.path.join(self.curpath,
                                 'data/namespaced_response.xml')

        with open(data_path) as f:
            data = f.read()
            create_and_queue_task(data, 'Tracelink Number Response',
                                  run_immediately=True)
