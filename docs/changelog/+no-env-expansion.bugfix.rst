Stop substituting ``${NAME}`` with the value of environment variables in direct references (``name @ url``) read from
installed metadata and lock files. pipdeptree now compares and validates those URLs as written.
