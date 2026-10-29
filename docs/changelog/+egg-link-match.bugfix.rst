Freeze a package as ``-e`` with the location from a ``NAME.egg-link`` file only when its metadata is an ``.egg-info``
directory in the directory that link names. That is the layout ``setup.py develop`` leaves. A link with the package's
name used to replace the ``name==version`` pin of any install, such as a ``.dist-info`` package from a wheel.
