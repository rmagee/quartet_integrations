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

from quartet_capture.rules import Step

class OPSMNumberResponseStep(Step):
    """
    The OPSMNumberResponseStep sends back a message that a system requesting
    messages from an OPSM system would understand. This allows QU4RTET to
    appear to be an OPSM system to external systems.  This response step
    utilizes two templates located in the templates/opsm directory to achieve
    an OPSM style return.
    """
