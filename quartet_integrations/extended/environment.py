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
from jinja2.environment import Environment
from jinja2.loaders import ChoiceLoader, PackageLoader

def get_default_environment():
    '''
    Loads up the default Jinja2 environment so simple template names can
    be passed in.  This includes the local templates on top of the
    existing EPCPyYes templates.

    :return: The defualt Jinja2 environment for this package.
    '''
    loader = ChoiceLoader(
        [
            PackageLoader('EPCPyYes', 'templates'),
            PackageLoader('quartet_integrations', 'templates'),
            PackageLoader('quartet_tracelink', 'templates')
        ]
    )
    env = Environment(loader=loader,
                      extensions=['jinja2.ext.with_'], trim_blocks=True,
                      lstrip_blocks=True)
    return env
