``from-index`` now resolves a local project given as a bare ``file:`` URL, such as ``file:///abs/path`` or
``-e file:///abs/path``, on the command line or in a requirements file. Before, it read the URL as a relative path and
failed with ``No such file or directory (os error 2)``. A relative ``file:`` URL, bare or as ``name @ file:./pkg``, now
resolves against the working directory as pip does, where the named form used to read ``file:pkg`` as ``/pkg``. A local
source that cannot be read now fails with an error that names its path.
