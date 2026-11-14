``--reverse`` now applies ``--packages`` and ``--exclude`` to missing requirements, as it did before the Rust engine.
Before, every requirement missing from a shown package was listed as a root even when no pattern matched it, and
``--exclude`` could not hide one.
