import sys

import pipdeptree

if sys.version_info >= (3, 8):
    import importlib.metadata as importlib_metadata
else:
    import importlib_metadata


def raise_import_error(name):
    raise ImportError(name)


importlib_metadata.version = raise_import_error
print(pipdeptree.guess_version("setuptools"), end="")
