"""The main entry point used for CLI."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final

from pipdeptree._cli import get_options, parse_packages

if TYPE_CHECKING:
    from collections.abc import Sequence
    from importlib.metadata import Distribution

    from pipdeptree._cli import Options
    from pipdeptree._models import PackageDAG
    from pipdeptree._models.package import DistributionInfo
    from pipdeptree._warning import WarningPrinter

_OVERLAP_MESSAGE: Final[str] = "Cannot have --packages and --exclude contain the same entries"


class _FilterError(Exception):
    """Raised by build_tree when the include/exclude filter cannot be satisfied."""

    def __init__(self, message: str, *, is_fatal: bool) -> None:
        super().__init__(message)
        self.is_fatal = is_fatal


def main(args: Sequence[str] | None = None) -> int | None:
    """CLI - The main function called as entry point."""
    options = get_options(args)

    from pipdeptree._render import render  # noqa: PLC0415  # Help and version exit before graph imports.
    from pipdeptree._warning import (  # noqa: PLC0415  # Help and version exit before graph imports.
        WarningType,
        get_warning_printer,
    )

    if options.command == "from-index":
        from pipdeptree._from_index import (  # noqa: PLC0415  # The index resolver is optional.
            FromIndexInputError,
            FromIndexUnavailableError,
        )

        build_errors: tuple[type[Exception], ...] = (FromIndexUnavailableError, FromIndexInputError)
        error_prefix = ""
    elif options.command == "from-lock":
        from pipdeptree._from_lock import FromLockError  # noqa: PLC0415  # Lock parsing is optional.

        build_errors = (FromLockError,)
        error_prefix = ""
    else:
        from pipdeptree._discovery import InterpreterQueryError  # noqa: PLC0415  # Environment discovery is optional.

        build_errors = (InterpreterQueryError,)
        error_prefix = "Failed to query custom interpreter: "

    # Warnings are only enabled when using text output.
    if not _is_text_output(options):
        options.warn = "silence"
    warning_printer = get_warning_printer()
    warning_printer.warning_type = WarningType.from_str(options.warn)

    try:
        tree = build_tree(options, log_resolved=True)
    except build_errors as error:
        print(f"{error_prefix}{error}", file=sys.stderr)  # noqa: T201
        return 1
    except _FilterError as error:
        if error.is_fatal:
            print(str(error), file=sys.stderr)  # noqa: T201
            return 1
        if warning_printer.should_warn():
            warning_printer.print_single_line(str(error))
        return _determine_return_code(warning_printer)

    render(options, tree)

    return _determine_return_code(warning_printer)


def build_tree(options: Options, *, log_resolved: bool = False) -> PackageDAG:
    """
    Discover packages and build the (optionally reversed/filtered) dependency tree.

    Shared by the CLI and the programmatic :func:`pipdeptree.render` API.

    :raises InterpreterQueryError: if querying a custom interpreter failed
    :raises FromIndexUnavailableError: if from-index is used but the optional nab resolver is missing
    :raises FromIndexInputError: if a from-index source is missing or a requirements file uses an unsupported directive
    :raises FromLockError: if a from-lock file is missing or is not a valid PEP 751 lock
    :raises _FilterError: if the include/exclude filter cannot be satisfied
    """
    from pipdeptree._models import PackageDAG  # noqa: PLC0415  # Help and version do not build a graph.
    from pipdeptree._models.dag import (  # noqa: PLC0415  # Help and version do not build a graph.
        IncludeExcludeOverlapError,
        IncludePatternNotFoundError,
    )
    from pipdeptree._validate import validate  # noqa: PLC0415  # Help and version do not validate a graph.

    distribution_info = {}
    if options.command == "from-index":
        # from-index resolves requirements by querying the package index instead of inspecting an installed
        # environment, so interpreter resolution is skipped entirely.
        pkgs = resolve_from_index(
            requirements=options.requirement,
            requirement_files=options.requirements or [],
            pyproject_files=options.pyproject or [],
            index_url=options.index_url,
            extra_index_url=options.extra_index_url,
        )
    elif options.command == "from-lock":
        from pathlib import Path  # noqa: PLC0415  # Lock parsing is optional.

        from pipdeptree._from_lock import load_lock  # noqa: PLC0415  # Lock parsing is optional.

        # A PEP 751 lock is already resolved, so it is read straight off disk -- no interpreter, network, or index.
        pkgs = load_lock(Path(options.lock))  # ty: ignore[invalid-argument-type]
    else:
        options.python = _resolve_python(options.python, log_resolved=log_resolved)
        pkgs = get_installed_distributions(
            interpreter=options.python,
            supplied_paths=options.path or None,
            local_only=options.local_only,
            user_only=options.user_only,
            distribution_info=distribution_info,
        )

    include, requested_extras = parse_packages(options.packages)
    tree = PackageDAG.from_pkgs(
        pkgs,
        extras=options.extras,
        requested_extras=requested_extras,
        distribution_info=distribution_info,
    )

    validate(tree)

    if options.context.active:
        options.context.full_tree = tree

    # Reverse the tree (if applicable) before filtering, thus ensuring, that the filter will be applied on ReverseTree
    if options.reverse:
        tree = tree.reverse()

    include = include or None
    exclude = set(options.exclude.split(",")) if options.exclude else None

    if include is not None or exclude is not None:
        try:
            tree = tree.filter_nodes(include, exclude, exclude_deps=options.exclude_dependencies)
        except IncludeExcludeOverlapError as e:
            raise _FilterError(_OVERLAP_MESSAGE, is_fatal=True) from e
        except IncludePatternNotFoundError as e:
            raise _FilterError(str(e), is_fatal=False) from e

    return tree


def _resolve_python(python: str | None, *, log_resolved: bool = False) -> str:
    # Default (None): auto-detect the active virtual environment, silently falling back to the running interpreter so
    # users outside a virtual environment keep the historical behavior. "auto" stays strict and fails if none is found.
    # log_resolved keeps the resolved-path note CLI-only so the programmatic API stays quiet in notebooks.
    if python is None:
        if resolved_path := find_active_interpreter():
            if log_resolved:
                print(f"(resolved python: {resolved_path})", file=sys.stderr)  # noqa: T201
            return resolved_path
        return sys.executable
    if python == "auto":
        resolved_path = detect_active_interpreter()
        if log_resolved:
            print(f"(resolved python: {resolved_path})", file=sys.stderr)  # noqa: T201
        return resolved_path
    return python


def get_installed_distributions(
    interpreter: str = sys.executable or "",
    supplied_paths: list[str] | None = None,
    local_only: bool = False,  # noqa: FBT001, FBT002
    user_only: bool = False,  # noqa: FBT001, FBT002
    distribution_info: dict[int, DistributionInfo] | None = None,
) -> list[Distribution]:
    """Defer environment discovery imports until a command needs an installed tree."""
    from pipdeptree._discovery import (  # noqa: PLC0415  # Environment discovery is optional.
        get_installed_distributions as discover,
    )

    return discover(interpreter, supplied_paths, local_only, user_only, distribution_info)


def resolve_from_index(
    *,
    requirements: list[str],
    requirement_files: list[str],
    pyproject_files: list[str],
    index_url: str | None = None,
    extra_index_url: list[str] | None = None,
) -> list[Distribution]:
    """Defer index resolver imports until the from-index command runs."""
    from pipdeptree._from_index import resolve_from_index as resolve  # noqa: PLC0415  # The index resolver is optional.

    return resolve(
        requirements=requirements,
        requirement_files=requirement_files,
        pyproject_files=pyproject_files,
        index_url=index_url,
        extra_index_url=extra_index_url,
    )


def find_active_interpreter() -> str | None:
    """Defer interpreter detection until an installed environment needs inspection."""
    from pipdeptree._detect_env import (  # noqa: PLC0415  # Resolved sources do not inspect an interpreter.
        find_active_interpreter as find,
    )

    return find()


def detect_active_interpreter() -> str:
    """Defer strict interpreter detection until the user requests it."""
    from pipdeptree._detect_env import (  # noqa: PLC0415  # Resolved sources do not inspect an interpreter.
        detect_active_interpreter as detect,
    )

    return detect()


def _is_text_output(options: Options) -> bool:
    if any((options.json, options.json_tree, options.graphviz_format, options.mermaid)):
        return False
    return options.output_format in {"freeze", "rich", "text"}


def _determine_return_code(warning_printer: WarningPrinter) -> int:
    return 1 if warning_printer.has_warned_with_failure() else 0


if __name__ == "__main__":
    sys.exit(main())
