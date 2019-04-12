Using the SAP Parser and Step
=============================

Using the SAP Parser is a matter of configuring your rule to include
the `quartet_integrations.sap.steps.SAPParsingStep` as one of the steps
to handle inbound parsing.

Processing Class
----------------

.. code-block::

    # set this as the processing class for the parsing step in your rule.
    quartet_integrations.sap.steps.SAPParsingStep

Handled XML Elements
--------------------

Once this is configured, any custom SAP namespaces can be handled. The current
integration handles the following elements that would be found in the following
XML structure:

.. code-block:: xml

    <SAPExtension>
        <ObjAttributes>
            <LOTNO>...lot number is here</LOTNO>
            <DATEX>...expiration date</DATEX>
            <DATMF>...manufacture date</DATMF>
        </ObjAttributes>
        <ObjAttGroupList/>
    </SAPExtension>

.. list-table:: Handled Elements
    :widths: 33 33
    :header-rows: 1

    * - Name
      - Description
    * - LOTNO
      - The lot number.  This is converted to a CBV compliant ILMD lot entry.
    * - DATEX
      - The expiration date.  This is also converted to a CBV value.
    * - DATMF
      - The date of manufacture.  This is imported as a CBV value for lack of a better way to do it.

