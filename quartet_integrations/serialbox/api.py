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
import requests

from logging import getLogger


logger = getLogger(__name__)

def get_number_response(host: str, port: int, machine_name: str, count: int,
                        response_format: str = 'xml', scheme='https'):
    """
    Will call a SerialBox instance and, using the input parameters, will
    return a serial number reply from that instance using the format specified.
    This calls the allocate API on the SB instance.
    :param host: The host to send the request to.
    :param port: The port which SerialBox is listening on.
    :param machine_name: The machine name of the SerialBox Pool to retrieve
    numbers from.
    :param count: The number of serial numbers to return.
    :param response_format: The format of the message...should be xml, json or csv.
    :return: Returns the raw serial number response from the SerialBox
    instance.
    """
    if not port:
        url = url = "%s://%s/serialbox/allocate/%s/%d/?format=%s" % (
            scheme, host, machine_name, count, response_format
        )
    else:
        url = url = "%s://%s:%s/serialbox/allocate/%s/%d/?format=%s" % (
            scheme, host, port, machine_name, count, response_format
        )
    logger.debug('Url for serialbox is %s', url)
    logger.debug('Getting the response...')
    requests.get(url, )
