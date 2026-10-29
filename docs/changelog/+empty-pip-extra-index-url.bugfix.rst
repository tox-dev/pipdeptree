``from-index`` now treats an empty ``PIP_EXTRA_INDEX_URL`` as unset and reads the extra indexes from
``UV_EXTRA_INDEX_URL``, as it already did for ``PIP_INDEX_URL`` and ``UV_INDEX_URL``. Before, the empty value left the
resolve with no extra index, so a package that only the ``UV_EXTRA_INDEX_URL`` index served failed to resolve.
