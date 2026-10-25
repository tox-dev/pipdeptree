Remove the module import fallback for dependency versions. Dependencies without distribution metadata
now report an unknown version and are treated as missing across environment scans, lock inputs and the Python API.
