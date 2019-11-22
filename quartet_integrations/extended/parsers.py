import io
import re
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

    def __init__(self, data, reg_ex):

        self._ssccs = []  # internal list to hold collected SSCCs
        self._quantity = 0
        self._regEx = re.compile(reg_ex)
        self._lot_number = ""
        self._ndc = ""
        self._exp_date = ""
        self._object_events = []
        self._aggregation_events = []
        # call the base constructor with the stream
        super(SSCCParser, self).__init__(stream=data)


    """
        When the base parser sees an ObjectEvent, this method is called
        The event is passed in as a parameter. The epcis_event's epc_list
        is inspected for all SSCCs and, when an SSCC is found, the SSCC is
        placed into the internal _ssccs list
    """
    def handle_object_event(self, epcis_event: template_events.ObjectEvent):

        if epcis_event.action == "ADD":
            for epc in epcis_event.epc_list:
                if epc.startswith('urn:epc:id:sscc:'):
                    self._ssccs.append(epc)
                else:
                    m = self._regEx.match(epc)
                    if m:
                        self._quantity = self._quantity + 1

            self._object_events.append(epcis_event)

        if epcis_event.ilmd is not None:
            for item in epcis_event.ilmd:
                if item.name == 'lotNumber':
                    self._lot_number = item.value
                elif item.name == "itemExpirationDate":
                    self._exp_date = item.value
                elif item.name == "NDC":
                    self._ndc = item.value

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

    @property
    def lot_number(self):
        return self._lot_number

    @property
    def exp_date(self):
        return self._exp_date

    @property
    def NDC(self):
        return self._ndc
