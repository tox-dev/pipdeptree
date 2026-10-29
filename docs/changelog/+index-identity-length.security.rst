Stop ``from-index`` with an error when the resolver pins a package name or version longer than 255 bytes, as
``from-lock`` already does. The text, JSON and freeze outputs copy a version once per edge, so an index could make them
print megabytes from one long version.
