Treat an empty ``VIRTUAL_ENV`` or ``CONDA_PREFIX`` as unset when detecting the environment to inspect, so pipdeptree no
longer runs a ``bin/python`` (``Scripts\python.exe`` on Windows) found relative to the working directory.
