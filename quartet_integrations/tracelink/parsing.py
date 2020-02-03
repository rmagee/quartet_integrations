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
from io import StringIO
from quartet_masterdata.models import Company, CompanyType

class TraceLinkPartnerParser:
    """
    Parses tracelink partner export spreadsheet data and creates QU4RTET
    company instances.
    """
    def parse(self, data: bytes):
        file_stream = StringIO(data.decode('utf-8'))
        parsed_data = csv.DictReader(file_stream)
        for datarow in parsed_data:
            row = list(datarow.values())
            try:
                city, state, zip, country = self.parse_location(row[5])
                company = Company.objects.create(
                    name=row[3],
                    address1=row[4],
                    city=city,
                    state_province=state,
                    postal_code=zip,
                    country=country
                )
                ids = row[7].split(',')
                for type_id in ids:
                    try:
                        type, id = type_id.strip().split(' ')
                        if type == "GLN":
                            company.GLN13 = id
                        if type == "SGLN":
                            company.SGLN = 'urn:epc:id:sgln:%s' % id
                    except ValueError:
                        print('passing on %s', type_id)
                company.save()
            except:
                raise

    def parse_location(self, location_row):
        unpacked = location_row.split(',')
        city = unpacked[0]
        state_zip_country = unpacked[1].strip().split(' ')
        state = state_zip_country[0]
        country_code = state_zip_country[-1]
        state_zip_country.pop(-1)
        state_zip_country.pop(0)
        zip = ' '.join(state_zip_country)
        return city, state, zip, country_code

