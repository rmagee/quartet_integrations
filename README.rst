=============================
quartet_integrations
=============================

.. image:: https://gitlab.com/serial-lab/quartet_integrations/badges/master/coverage.svg
   :target: https://gitlab.com/serial-lab/quartet_integrations/pipelines
.. image:: https://gitlab.com/serial-lab/quartet_integrations/badges/master/pipeline.svg
   :target: https://gitlab.com/serial-lab/quartet_integrations/commits/master
.. image:: https://badge.fury.io/py/quartet_integrations.svg
    :target: https://badge.fury.io/py/quartet_integrations
    
Third party integrations for the QU4RTET open-source EPCIS platform.  For
more on QU4RTET and SerialLab, see `the SerialLab website`_

_`the SerialLab website`: http://serial-lab.com

Documentation
-------------

The full documentation is at https://serial-lab.gitlab.io/quartet_integrations/

Quickstart
----------

Install quartet_integrations::

    pip install quartet_integrations

Add it to your `INSTALLED_APPS`:

.. code-block:: python

    INSTALLED_APPS = (
        ...
        'quartet_integrations.apps.QuartetIntegrationsConfig',
        ...
    )

Add quartet_integrations's URL patterns:

.. code-block:: python

    from quartet_integrations import urls as quartet_integrations_urls


    urlpatterns = [
        ...
        url(r'^', include(quartet_integrations_urls)),
        ...
    ]

Features
--------

* TODO

Running Tests
-------------

Does the code actually work?

::

    source <YOURVIRTUALENV>/bin/activate
    (myenv) $ pip install tox
    (myenv) $ tox

Credits
-------

Tools used in rendering this package:

*  Cookiecutter_
*  `cookiecutter-djangopackage`_

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`cookiecutter-djangopackage`: https://github.com/pydanny/cookiecutter-djangopackage
