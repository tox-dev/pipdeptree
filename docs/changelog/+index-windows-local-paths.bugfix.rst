``from-index`` on Windows now treats ``C:\path\to\project`` and ``.\project`` as local sources, on the command line and
as requirements file lines, as pip does. It used to pass them to the PEP 508 parser, which rejected them for lacking a
package name.
