Import ``platform`` and ``json`` for the running interpreter's query from its standard library and extension module
directory alone, so a ``_wmi.py`` or ``_json.py`` in a directory pipdeptree inspects, or on a ``sys.path`` narrowed
before ``pipdeptree.render()``, no longer runs in the pipdeptree process (:issue:`768`).
