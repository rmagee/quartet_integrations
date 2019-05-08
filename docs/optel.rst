Optel Parsing
=============

This module contians support for parsing optel line master messages in
EPCIS format.  There are two parsers that can be utilized along with two
steps.  For more on steps see the documentation for the `quartet_capture`
module here:

https://serial-lab.gitlab.io/quartet_capture/

Standard EPCIS Step
-------------------

Normally you will only be using the step if you are configuring a
q4 instance.  In place of a normal EPCIS parsing step you will configure
the following *Step* in one of your q4 rules.

    It is highly recommended that you do not use this step if you anticipate
    getting one object event per serial-number from a packaging line.  While
    it will work, your tasks may take much longer to execute.  Use judgement
    combined with adequate testing when deciding which step to use.  The
    consolidation step below is typically the best to use when you have
    one object event per serial number for a large batch.

.. code-block:: text

    quartet_integrations.optel.steps.


Consolidating Step
------------------

In instances where you are getting large batches from a packaging
line system that is configured to send one object event per serial number
and would like your tasks to execute more quickly, use the consolidating
step below.  This step can improve performance by up to 1000% in many cases.

.. code-block:: text

    quartet_integrations.optel.steps.ConsolidationParsingStep

Parsers
-------

The optel parser classes are located in the `quartet_integrations.optel.parsing`
python module.  They are matched one-to-one against the steps above.
There is a single consolidation parser and a single standard parser.
Each of these parsers inherits from the `quartet_epcis.parsing.business_parsing.BusinessEPCISParser`
class which, in turn, ultimately inherits from the standared EParseCIS
parsing class.  For more on each of these see:

https://serial-lab.gitlab.io/quartet_epcis/

https://serial-lab.gitlab.io/EParseCIS/




