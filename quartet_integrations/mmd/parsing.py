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

import csv
import json
import requests
from io import StringIO
import logging
from django.db.utils import IntegrityError
from django.db import transaction
from requests.auth import HTTPBasicAuth
from quartet_templates.models import Template
from quartet_capture.models import Rule, Step, StepParameter
from quartet_integrations.management.commands import utils
from quartet_masterdata.models import TradeItem, TradeItemField, Company
from quartet_output.models import EndPoint, AuthenticationInfo, EPCISOutputCriteria
from serialbox.models import Pool, ResponseRule
from list_based_flavorpack.models import ListBasedRegion, ProcessingParameters
from random_flavorpack.models import RandomizedRegion
from quartet_integrations.mmd.exceptions import (DependencyNotFound)

logger = logging.getLogger(__name__)


class PartnerParser:
    """
    Parses provided customer .csv file and creates QU4RTET
    companies.
    """

    def parse(self, data: bytes):
        file_stream = StringIO(data.decode('utf-8'))
        parsed_data = csv.DictReader(file_stream)
        for datarow in parsed_data:
            row = list(datarow.values())
            try:
                city, state, zip, country = self.parse_location(row)

                Company.objects.get_or_create(
                    name=row[1],
                    address1=row[5],
                    city=city,
                    state_province=state,
                    postal_code=zip,
                    country=country,
                    gs1_company_prefix=row[2],
                    GLN13=row[2],
                    SGLN='urn:epc:id:sgln:%s' % row[4]
                )
            except IntegrityError:
                pass
            except Exception as e:
                raise

    def parse_location(self, row):

        city = row[9]
        state = row[10]
        country_code = row[12]
        zip = row[11]
        return city, state, zip, country_code


class TradeItemImportParser:
    """
        Parses partner Master Material Data from provided .csv file
    """

    def __init__(self):

        self.replenishment_size = None
        self.threshold = None
        self.minimum = None
        self.maximum = None
        self.sending_system_gln = None
        self.response_rule_name = None
        self.replenishment_size = None
        self.threshold = None
        self.endpoint = ""
        self.authentication_info = 0
        self.level4_name = None
        self.template_name = ""
        self.info_func = None
        self.snm_output_criteria = ""
        self.processing_parameters = {}
        self.mock = False
        self.serialbox_output_criteria = None
        self.step=None

    def parse(self, data: bytes,
              step: object,
              threshold: int,
              response_rule: str,
              snm_output_criteria: str,
              replenishment_size: int,
              template_name: str,
              processing_parameters: str,
              serialbox_output_criteria: str,
              minimum_number: int,
              maximum_number: int
              ):

        self.step = step
        self.threshold = threshold
        self.minimum = minimum_number
        self.maximum = maximum_number
        self.response_rule_name = response_rule
        self.snm_output_criteria = snm_output_criteria
        self.replenishment_size = replenishment_size
        self.info_func = step.info
        self.template_name = template_name
        if processing_parameters: self.processing_parameters = json.loads(processing_parameters)
        self.serialbox_output_criteria = serialbox_output_criteria



        file_stream = StringIO(data.decode('utf-8'))
        parsed_data = csv.DictReader(file_stream)
        """
        -- Field Values
            0 = Item 
            1 =,, (The Header in the file is Empty but it is the UOM for Level 1.)
            2 = GTIN,
            3 = Level2 UOM,
            4 = Level2 GTIN,
            5 = Quantity of L1 in L2,
            6 = Level3 UOM,
            7 = Level3 GTIN,
            8 = Quantity of L2 in L3,
            9 = SSCC Quantity,
            10 = Description,
            11 = Customer,
            12 = L4,
            13 = GLN
            14 = ,, (The value is empty but the header says SGLN)
            15 = Company Prefix,
            16 = NDC
        """
        validated = False
        for datarow in parsed_data:
            # get the fields from datarow
            fields = list(datarow.values())
            # set each field
            item_id = fields[0]
            level1_uom = fields[1]
            level1_gtin = fields[2]
            level2_uom = fields[3]
            level2_gtin = fields[4]
            level2_pack_count = fields[5]
            level3_uom = fields[6]
            level3_gtin = fields[7]
            level3_pack_count = fields[8]
            pallet_pack_count = fields[9]
            description = fields[10]  # Name of the Trade Item
            company_name = fields[11]
            self.level4_name = fields[12]
            gln = fields[13]
            # field 14 is empty
            company_prefix = fields[15]
            ndc = fields[16]

            # validate
            if not validated:
                validated = self.validate_parameters()


            company = self.get_company_by_gln(gln)
            if company is None:
                msg = 'Company {0} not configured in QU4RTET. Trade Item(s) {1}, {2}, {3} will not be created'.format(
                    self.company_name, level1_gtin, level2_gtin, level3_gtin)
                self.info_func(msg);
                # go to next record in the for loop
                continue

            self.create_trade_item(
                company=company,
                material_number=item_id,
                unit_of_measure=level1_uom,
                gtin14=level1_gtin,
                pack_count=0,
                pallet_pack_count=pallet_pack_count,
                product_name=description,
                ndc=ndc
            )
            
            if len(level2_gtin) == 14:
                self.create_trade_item(
                    company=company,
                    material_number=item_id,
                    unit_of_measure=level2_uom,
                    gtin14=level2_gtin,
                    pack_count=level2_pack_count,
                    pallet_pack_count=pallet_pack_count,
                    product_name=description,
                    ndc=ndc
                )

            if len(level3_gtin) == 14:
                self.create_trade_item(
                    company=company,
                    material_number=item_id,
                    unit_of_measure=level3_uom,
                    gtin14=level3_gtin,
                    pack_count=level3_pack_count,
                    pallet_pack_count=pallet_pack_count,
                    product_name=description,
                    ndc=ndc

            )


    def validate_parameters(self):

        ret_val = True

        if self.level4_name.lower() != 'qu4rtet' and self.level4_name.lower() != 'quartet':
            if not self.snm_output_criteria:
                msg = 'List Based imports must supply the SNM Output Criteria Parameter.'
                self.info_func(msg)
                raise Exception(msg)
            if not self.template_name or len(self.template_name) == 0:
                msg = 'List Based imports must supply the Template Name Step Parameter.'
                self.info_func(msg)
                raise Exception(msg)
        if not self.response_rule_name or len(self.response_rule_name) == 0:
            msg = 'Imports must supply the Response Rule Name Step Parameter.'
            self.info_func(msg)
            raise Exception(msg)

        return ret_val


    def get_company_by_gln(self, gln):
        try:
            res = Company.objects.get(GLN13=gln)
        except Company.DoesNotExist:
            raise
        return res

    def create_trade_item(self, company, material_number, unit_of_measure, gtin14,
                          pack_count, pallet_pack_count, product_name, ndc
                          ):

        self.info_func('Importing Trade Item {0} ({1})'.format(gtin14, unit_of_measure))

        try:
            trade_item = TradeItem.objects.get(GTIN14=gtin14)
            self.info_func('Trade Item for GTIN-14, {0} ({1}), is already configured.'.format(gtin14, unit_of_measure))
        except TradeItem.DoesNotExist:
            # TradeItem was not found, create it.
            self.info_func('Creating the TradeItem {0} ({1}). '.format(gtin14, unit_of_measure))
            trade_item = TradeItem.objects.create(
                GTIN14=gtin14,
                company=company,
                additional_id=material_number,
                package_uom=unit_of_measure,
                pack_count=pack_count,
                regulated_product_name=product_name,
                NDC=ndc,
                NDC_pattern=self.get_ndc_pattern(ndc)

            )

        # Create the pallet_pack_count TradeItem Field
        TradeItemField.objects.get_or_create(
            trade_item=trade_item,
            name='pallet_pack_count',
            value=pallet_pack_count
        )

        try:
            if self.level4_name.lower() != "qu4rtet" and self.level4_name.lower() != "quartet":
                # Create the list based pool, managed by an External L4
                self.info_func('Creating a Pool for {0}'.format(gtin14))
                self.create_list_based_pool(trade_item, material_number, company)
            else:
                # Create a Random pool, managed by QU4RTET
                self.create_random_pool(trade_item, material_number)
        except DependencyNotFound as dnf:
            # A dependency was not found like an Output Criteria, Response Rule, Template etc
            # Have to remove the Trade Item
            self._remove_trade_item(gtin14)
            raise dnf

    def _remove_trade_item(self, gtin14):

        try:
            self.info_func('Removing GTIN {0}'.format(gtin14))
            tradeitem = TradeItem.objects.get(GTIN14=gtin14)
            TradeItemField.objects.filter(trade_item=tradeitem).delete()
            TradeItem.objects.filter(GTIN14=gtin14).delete()
            self.info_func('GTIN {0} Removed'.format(gtin14))

        except Exception as e:
            self.info_func('Exception occured removing GTIN {0}. \r\n {1}'.format(gtin14, str(e)))
            raise e

    def create_random_pool(self, trade_item: TradeItem, material_number) -> None:
        """
        Will create a randomized range for the inbound material record.
        :param trade_item: A TradeItem instance
        :param material_number: Material Number from the imported .csv data.
        :return: None
        """
        try:
            rule = Rule.objects.get(name=self.response_rule_name)
            readable_name = "%s (%s) | %s" % (
                trade_item.regulated_product_name, trade_item.package_uom,
                material_number
            )
            pool = Pool.objects.get_or_create(readable_name=readable_name,
                                              machine_name=trade_item.GTIN14,
                                              active=True,
                                              request_threshold=self.threshold
                                              )[0]

            ResponseRule.objects.get_or_create(pool=pool, rule=rule,
                                               content_type='xml')


            RandomizedRegion.objects.get_or_create(
                machine_name=trade_item.GTIN14,
                readable_name=trade_item.GTIN14,
                min=int(self.minimum),
                max=int(self.maximum),
                start=int(self.minimum),
                order=1,
                active=True,
                pool=pool
            )
        except Rule.DoesNotExist:
            # noinspection PyCallByClass
            raise Rule.DoesNotExist('The rule with name %s could not be found'
                                    '. Check the name of the response_rule_name parameter in the import rule ',
                                    self.response_rule_name)
        except IntegrityError:
            pass

    def get_ndc_pattern(self, NDC: str):
        split_vals = NDC.split('-')
        lens = []
        for val in split_vals:
            lens.append(str(len(val)))
        result = ('-').join(lens)
        return result

    def create_list_based_pool(self,
                               trade_item: TradeItem,
                               material_number:str,
                               company: Company
                               ) -> None:
        """
        Creates a list based pool for use in the system.
        :param trade_item: The TradeItem to use for creating the pool.
        :return: None
        """
        replenishment_size = self.replenishment_size
        self.verify_response_rule()
        request_rule = self.verify_request_rule(company)
        output_criteria = self.verify_snm_output_criteria()
        template = self.verify_request_template()

        try:
            pool = Pool.objects.create(
                readable_name='%s | %s | %s' % (
                    trade_item.regulated_product_name, material_number,
                    trade_item.GTIN14),
                machine_name=trade_item.GTIN14,
                request_threshold=self.threshold
            )
            self.info_func('Creating a List Based Region in Pool {0} for {1}'.format(pool.readable_name, trade_item.GTIN14))
            region = ListBasedRegion(
                readable_name=pool.readable_name,
                machine_name=trade_item.GTIN14,
                active=True,
                order=1,
                number_replenishment_size=replenishment_size,
                processing_class_path='list_based_flavorpack.processing_classes.third_party_processing.processing.DBProcessingClass',
                end_point=output_criteria.end_point,
                rule=request_rule,
                authentication_info=output_criteria.authentication_info,
                template=template,
                pool=pool
            )
            region.save()
            self.assign_response_rule(pool)
            self.create_processing_parameters(region)
        except IntegrityError:
            self.info_func('Duplicate number range %s | %s being skipped' %
                           (trade_item.regulated_product_name, material_number))

    def assign_response_rule(self, pool):
        try:
            rule = Rule.objects.get(name=self.response_rule_name)
            ResponseRule.objects.create(
                pool=pool, rule=rule, content_type='xml'
            )
        except Rule.DoesNotExist:
            msg = 'The Response Rule Parameter Value, {0}, was not found.'.format(self.response_rule_name)
            self.info_func(msg)
            raise DependencyNotFound(msg)
        except Exception as e:
            msg = 'An error occured assigning the response rule {0} to the Serial Number Pool {1}'.format(self.response_rule_name, pool.name)
            self.info_func(msg)
            raise DependencyNotFound(msg)


    def validate_serial_number(self, pool, region):

        try:

            output = EPCISOutputCriteria.objects.get(name=self.serialbox_output_criteria)
            endpoint = output.end_point
            auth = output.authentication_info
            msg = 'Retrieving 1 Serial Number for Pool {0} Region {1}.'.format(
                pool.readable_name,
                region.machine_name
            )
            self.info_func(msg)

            url = "{0}/serialbox/allocate/{1}/1/?format=xml".format(endpoint.urn, region.machine_name)
            response = requests.get(url, auth=HTTPBasicAuth(auth.username, auth.password))
            self.info_func(response.content)

        except EPCISOutputCriteria.DoesNotExist:
            self.info_func('Unable to validate Serial Number for Pool {0} Region {1}. \
                            SerialBox Output Criteria {2} was not found'
                           .format(pool.readable_name, region.machine_name, self.serialbox_output_criteria))

        except requests.exceptions.RequestException as e:
            msg = 'Unable to retrieve Serial Number for Pool {0} Region {1}. \r\n \
                                        SerialBox Output Criteria = {2}'.format(
                                        pool.readable_name,
                                        region.machine_name,
                                        self.serialbox_output_criteria
                                        )

            self.info_func(msg)



    def create_processing_parameters(self, region):

        for entry in self.processing_parameters:
            for k, v in entry.items():
                try:
                    ProcessingParameters.objects.get(key=k,
                                                     list_based_region=region)
                except ProcessingParameters.DoesNotExist:

                    if str(v).lower() == '%api_key%':
                       v = v.lower().replace('%api_key%', region.machine_name)

                    ProcessingParameters.objects.create(key=k,
                                                        value=v,
                                                        list_based_region=region)

    def verify_request_rule(self, company):
        """
        Makes sure the Number Request rule exists
        :return: None
        """
        rule_name = "{0} Serial Number Request Rule".format(company.name)

        try:
            rule = Rule.objects.get(name=rule_name)
        except Rule.DoesNotExist:
            # Request Rule doesn't exist so create it
            self.info_func("Creating Rule {0}".format(rule_name))
            rule = Rule.objects.create(
                name=rule_name,
                description="Serial Number Request Rule Generated by QU4RTET",
            )
            if self.level4_name.lower == 'iris' or self.level4_name.lower() == 'frequentz/rfxcel':
                self.add_iris_steps(rule)
            elif self.level4_name.lower() == 'pharmasecure':
                self.add_pharmasecure_steps(rule)
            elif self.level4_name.lower() == 'rfxcel':
                self.add_rfxcel_steps(rule)
            else:
                msg = '{0} is an unsupported Level 4. Please contact your QU4RTET Administrators'.format(self.level4_name)
                self.info_func(msg)
                raise Exception(msg)

        return rule


    def add_rfxcel_steps(self, rule):

        request_step = Step.objects.create(
            name='Request Numbers',
            description='Auto Generated in QU4RTET.',
            step_class='list_based_flavorpack.steps.NumberRequestTransportStep',
            rule=rule,
            order=1
        )
        StepParameter.objects.create(
            name='content-type',
            value='text/xml',
            step=request_step
        )

        Step.objects.create(
            name='Save Numbers',
            description='Auto Generated in QU4RTET.',
            step_class='quartet_integrations.rfxcel.steps.RFXCELNumberResponseParserStep',
            rule=rule,
            order=2
        )


    def add_pharmasecure_steps(self, rule):

        request_step = Step.objects.create(
            name='Request Numbers',
            description='Auto Generated in QU4RTET.',
            step_class='quartet_integrations.pharmasecure.steps.PharmaSecureNumberRequestTransportStep',
            rule=rule,
            order=1
        )
        StepParameter.objects.create(
            name='content-type',
            value='text/xml',
            step=request_step
        )

        Step.objects.create(
            name='Save Numbers',
            description='Auto Generated in QU4RTET.',
            step_class='quartet_integrations.pharmasecure.steps.PharmaSecureNumberRequestProcessStep',
            rule=rule,
            order=2
        )


    def add_iris_steps(self, rule):

        request_step = Step.objects.create(
            name='Request Numbers',
            description='Auto Generated in QU4RTET.',
            step_class='quartet_integrations.frequentz.steps.IRISNumberRequestTransportStep',
            rule=rule,
            order=1
        )
        StepParameter.objects.create(
            name='content-type',
            value='text/xml',
            step=request_step
        )

        Step.objects.create(
            name='Save Numbers',
            description='Auto Generated in QU4RTET.',
            step_class='quartet_integrations.frequentz.steps.IRISNumberRequestProcessStep',
            rule=rule,
            order=2
        )


    def verify_response_rule(self):
        """
        Makes sure the response rule exists.
        :return: None
        """
        try:
            Rule.objects.get(
                name=self.response_rule_name
            )
        except Rule.DoesNotExist:
            msg = 'The Response Rule Parameter Value, {0}, was not found.'.format(self.response_rule_name)
            self.info_func(msg)
            raise DependencyNotFound(msg)

    def verify_request_template(self):

        try:
            ret = Template.objects.get(name=self.template_name)
        except Template.DoesNotExist:
            msg = 'The Template Name Parameter Value, {0}, was not found.'.format(self.template_name)
            self.info_func(msg)
            raise DependencyNotFound(msg)

        return ret

    def verify_snm_output_criteria(self):
        """
        Makes sure Output Criteria Exists for an External SNX Manager.
        :return: None
        """
        try:
            ret = EPCISOutputCriteria.objects.get(
                name=self.snm_output_criteria
            )
        except EPCISOutputCriteria.DoesNotExist:
            msg = 'The SNM Output Criteria Parameter Value, {0}, was not found in QU4RTET'.format(
                self.snm_output_criteria)
            self.info_func(msg)
            raise DependencyNotFound(msg)
        return ret

