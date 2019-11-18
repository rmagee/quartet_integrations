import io
from EPCPyYes.core.v1_2 import template_events
from eparsecis.eparsecis import FlexibleNSParser
"""
    The SSCC Parser collects all SSCCs within Object Events
    It is called in execute method of the AppendShippingStep
"""
class SSCCParser(FlexibleNSParser):
    """
        ctor
    """
    def __init__(self, data):

        self._ssccs = []  # internal list to hold collected SSCCs
        self._quantity = 0
        self._object_events = []
        self._aggregation_events = []
        # convert bytes into stream
        stream = io.BytesIO(data)
        # call the base constructor with the stream
        super(SSCCParser, self).__init__(stream=stream)

    """
        When the base parser sees an ObjectEvent, this method is called
        The event is passed in as a parameter. The epcis_event's epc_list
        is inspected for all SSCCs and, when an SSCC is found, the SSCC is
        placed into the internal _ssccs list
    """
    def handle_object_event(self, epcis_event: template_events.ObjectEvent):
        for epc in epcis_event.epc_list:
            if epc.startswith('urn:epc:id:sscc:'):
                self._ssccs.append(epc)


        if epcis_event.action  == "ADD":
            self._object_events.append(epcis_event)

    def handle_aggregation_event(
        self,
        epcis_event: template_events.AggregationEvent
    ):
        self._aggregation_events.append(epcis_event)

    @property
    def quantity(self):
        return self._quantity

    @property
    def sscc_list(self):
        # Returns the SSCCs collected in self.handle_object_event
        # Only call after parse() is called.
        return self._ssccs
