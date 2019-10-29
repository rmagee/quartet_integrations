Importing Trade Items from Oracle
---------------------------------

Export CSV from Oracle
======================

To import a dump of trade items from an oracle ERP, first export the trade
items as a spreadsheet and save as a *.csv* file.

Configure the Companies
=======================

Next, in your Q4 under *Master Data/Company* configure each of the companies
you will be importing trade items for and make sure that the **GS1 Company
Prefix** field is configured with an accurate company prefix or the import
will not work.  If the company has multiple company prefixes, you will need
to configure each.

Execute the Management Command
==============================

You must have shell access to your Q4 instance to do this.  If not
you will set up the rule manually (details below).

.. code-block:: text

    # from the qu4rtet root
    python manage.py create_oracle_import_rule

This command will create a rule named *Oracle Master Material Import* which
will contain one step named *Import Spreadsheet Data* with the processing
class of:

.. code-block:: text

    quartet_integrations.oracle.steps.TradeItemImportStep

For each company prefix you configured in the above company configuration,
you will enter in a step parameter with the name *Company Prefix N* where N
is an ascending number.  For example, if you have 10 company prefixes it would
look like *Company Prefix 1, Company Prefix 2, etc...*  For the value of
each parameter, enter in the company prefixes.  Once you have completed this
you are finished and you can upload your spread sheet.


Spreadsheet Columns
===================

The spreadsheet should have the following columns in the EXACT order as below

*   ProductID/Material Number
*   Saleable Unit UOM
*   Saleable Unit GTIN-14
*   Level 2 UOM (case or bundle)
*   Level 2 GTIN-14
*   Level 2 pack count
*   Level 3 UOM
*   Level 3 GTIN-14
*   Level 3 pack count
*   Pallet Pack Count
*   Product description

For a sample file, look for the oracle_mm_export.csv in the *tests/data*
directory of the quartet_integrations package.


