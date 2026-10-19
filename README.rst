========================
Django Simple Log Viewer
========================

**Django Simple Log Viewer** is a simple, intuitive web-based log viewer for Django applications. It automatically discovers, parses, and displays your application log files inside a clean Material Dashboard interface with search, sorting, filtering, and pagination.

.. image:: sample_log.jpg
    :width: 600
    :alt: Django Simple Log Viewer Screenshot

Features
========

- **Zero-Fuss Integration**: Discovers log files and formatters directly from your standard Django ``LOGGING`` configuration.
- **Modern Django & Python Support**: Tested and fully compatible with **Python 3.11+** and **Django 4.2+ / 5.0+**.
- **Universal Log Format Support**:
  - Supports ``%``-style (``%(asctime)s``), ``{``-style (``{asctime}``), and ``$``-style (``$asctime``) formatters.
  - Automatically parses bracketed timestamps (``[%(asctime)s]``), hyphen delimiters, colons, and padded levels (``%(levelname)-8s``).
  - Handles Django documentation's recommended formats seamlessly (including ``{process:d}``, ``{thread:d}``).
- **Multiline Traceback Preservation**: Multi-line error stack traces and exceptions are automatically attached to their corresponding log entries and rendered cleanly with preserved formatting.
- **Rotated Logs Support**: Easily browse through rotated log archives (e.g. ``app.log.1``, ``app.log.2``) via the file switcher dropdown.
- **Pathlib & Relative Path Support**: Works seamlessly with ``pathlib.Path`` objects (e.g., ``BASE_DIR / 'logs' / 'app.log'``) and relative paths.
- **DataTables Interactive UI**: Instant client-side search, sorting, and pagination powered by DataTables.
- **Secure by Default**: Restricted to users with Django ``is_superuser`` permissions.
- **Customizable Themes**: Choose from multiple built-in color schemes (purple, azure, green, orange, danger).

Compatibility
=============

- **Python**: 3.11, 3.12, 3.13+
- **Django**: 4.2 (LTS), 5.0, 5.1, 5.2+

Installation
============

Install via pip::

    pip install django-simple-log-viewer

Quick Start
===========

1. Add ``log_viewer`` to your ``INSTALLED_APPS`` in ``settings.py``:

   .. code-block:: python

       INSTALLED_APPS = [
           ...,
           'log_viewer',
       ]

2. Add the log viewer to your project's ``urls.py``:

   .. code-block:: python

       from django.urls import path, include

       urlpatterns = [
           ...,
           path('log-viewer/', include('log_viewer.urls')),
       ]

3. Configure a file-based handler in your ``LOGGING`` setting in ``settings.py`` (if you haven't already):

   .. code-block:: python

       from pathlib import Path
       BASE_DIR = Path(__file__).resolve().parent.parent

       LOGGING = {
           'version': 1,
           'disable_existing_loggers': False,
           'formatters': {
               'verbose': {
                   'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                   'style': '{',
               },
               'standard': {
                   'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
               },
           },
           'handlers': {
               'file': {
                   'level': 'DEBUG',
                   'class': 'logging.FileHandler',
                   'filename': BASE_DIR / 'app.log',
                   'formatter': 'standard',
               },
           },
           'loggers': {
               '': {
                   'handlers': ['file'],
                   'level': 'INFO',
                   'propagate': True,
               },
           },
       }

   *Note: For optimal column layout, it is recommended to place the ``message`` attribute last in your format string.*

4. Log in as a **superuser** and visit ``/log-viewer/`` in your browser.

Settings
========

The following optional settings can be added to your ``settings.py``:

SITE_NAME
---------
Change the application name displayed in the sidebar and navigation bar (default is ``'LogViewer'``):

.. code-block:: python

    SITE_NAME = 'My Awesome Project'

LOG_FILE_EXTENSION
------------------
If your log files use an extension other than ``.log``, specify it here (make sure to include the leading dot):

.. code-block:: python

    LOG_FILE_EXTENSION = '.txt'

Theming
-------
To change the sidebar color theme, override or extend ``log_viewer/log_home.html`` and specify a theme name in the ``theme`` block:

.. code-block:: html+django

    {% extends "log_viewer/log_home.html" %}
    {% block theme %}azure{% endblock %}

Available theme options: ``purple`` (default), ``azure``, ``green``, ``orange``, ``danger``.

Running Tests
=============

To run the test suite:

.. code-block:: bash

    python runtests.py

License
=======

Released under the `MIT License <LICENSE>`_.