Query another interpreter from an empty temporary directory and drop the ``''`` entry that ``python -c`` puts on
``sys.path``, so modules and ``.dist-info`` directories in the current directory no longer load during the query or show
up as installed packages.
