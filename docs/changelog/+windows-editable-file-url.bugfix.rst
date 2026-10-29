On Windows, freeze output now writes an editable location as ``-e file:///C:/proj`` instead of ``-e C:\proj``, which
pip read as ``C:proj`` and rejected. This covers an editable install with no version control, one with no remote or an
invalid remote, and one whose lookup timed out. On other platforms, a location that holds a backslash also becomes a
``file://`` URL.
