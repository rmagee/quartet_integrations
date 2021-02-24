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
from os import path
from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_xml.renderers import XMLRenderer
from rest_framework.parsers import JSONParser
from quartet_capture.parsers import RawParser
import json
from quartet_capture.models import Task

class TaskXMLRenderer(XMLRenderer):

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data

class LoggingView(APIView):
    #authentication_classes = []
    #permission_classes = [AllowAny]
    renderer_classes = [TaskXMLRenderer]
    parser_classes = [RawParser]
    queryset = Task.objects.all()

    def get(self, request):
        return Response("<echo>OK</echo>")

    def post(self, request: Request, format=None):
        """
        This simply logs the full request including headers
        """
        stream = request.stream
        raw_request = ["%s: %s" % (name, val) for name, val in stream.headers.items()]
        raw_request = '\n'.join(raw_request)
        raw_request = """



**********************
Headers: %s
**********************

Request Body:
%s""" % (raw_request, request.data)
        self.write_file(raw_request)
        return Response(raw_request)

    def write_file(self, raw_request):
        log_file = path.join(settings.LOGGING_PATH, 'requests.txt')
        with open(log_file, "w+") as f:
            f.write(raw_request)
