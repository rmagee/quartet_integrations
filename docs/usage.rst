=====
Usage
=====

To use quartet_integrations in a project, add it to your `INSTALLED_APPS`:

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

