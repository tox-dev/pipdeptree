"""
Programmatic access to pipdeptree.

Use :func:`render` when stdout is unavailable or when a dependency tree is needed as a string. Text results implement
the notebook rich-display protocol while retaining normal :class:`str` behavior.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from html import escape
from math import inf
from typing import TYPE_CHECKING, Final

from pipdeptree._rust import render as _render
from pipdeptree._rust import render_with_mermaid as _render_with_mermaid

from .version import __version__

if TYPE_CHECKING:
    from collections.abc import Container

    from typing_extensions import Self

_BINARY_GRAPHVIZ_FORMATS: Final[frozenset[str]] = frozenset({"png", "svg", "pdf", "jpeg", "jpg", "gif", "bmp", "ps"})
_FORMAT_FLAGS: Final[dict[str, list[str]]] = {
    "text": [],
    "json": ["--json"],
    "json-tree": ["--json-tree"],
    "mermaid": ["--mermaid"],
    "dot": ["--graph-output", "dot"],
}
_SUMMARY_FORMATS: Final[frozenset[str]] = frozenset({"json", "rich", "text"})


def render(  # noqa: PLR0913  # The public keyword API predates the Rust implementation.
    *,
    packages: str | None = None,
    exclude: str | None = None,
    output_format: str = "text",
    summary: bool = False,
    reverse: bool = False,
    depth: float = inf,
    extras: bool | str = False,
    local_only: bool = False,
    user_only: bool = False,
    python: str | None = None,
    encoding: str = "utf-8",
    warn: str = "silence",
) -> str:
    """
    Render an environment's dependency tree.

    :param packages: Comma-separated package allowlist. Wildcards and ``name[extra]`` are supported.
    :param exclude: Comma-separated package denylist. Wildcards are supported.
    :param output_format: ``text``, ``json``, ``json-tree``, ``mermaid`` or ``dot``. With ``summary=True``, use
        ``text``, ``rich`` or ``json``.
    :param summary: Return an environment health report instead of a dependency tree.
    :param reverse: Show packages beneath the dependencies that require them.
    :param depth: Maximum rendered tree depth.
    :param extras: Extras mode. ``True`` means ``"explicit"``; named modes are ``"none"``, ``"explicit"`` and
        ``"active"``.
    :param local_only: Exclude globally installed packages from a virtual environment.
    :param user_only: Include only packages installed in the user site.
    :param python: Python interpreter whose environment to inspect.
    :param encoding: Encoding used to select text tree characters.
    :param warn: Warning mode: ``silence``, ``suppress`` or ``fail``. ``suppress`` writes warnings to
        :data:`sys.stderr`; ``fail`` raises :exc:`ValueError` when pipdeptree finds a problem.
    :raises ValueError: If an option is invalid, a binary Graphviz format is requested, or ``warn="fail"``
        and the environment has dependency problems.
    :return: The rendered output. Text and text-summary results also provide notebook display hooks.
    """
    if summary and output_format not in _SUMMARY_FORMATS:
        msg = f"summary output_format must be one of {', '.join(sorted(_SUMMARY_FORMATS))}; got {output_format!r}"
        raise ValueError(msg)

    args = _render_args(
        _RenderOptions(
            packages=packages,
            exclude=exclude,
            output_format=output_format,
            summary=summary,
            reverse=reverse,
            depth=depth,
            extras=extras,
            local_only=local_only,
            user_only=user_only,
            python=python,
            encoding=encoding,
            warn=warn,
        )
    )
    if summary or output_format != "text":
        text = _report(*_render(args))
        if not summary:
            return text
        return _SummaryResult(text, html=_summary_html(text)) if output_format == "text" else text
    # One engine run yields both representations; a notebook's mermaid display would otherwise
    # rediscover the whole environment through a second call.
    text, mermaid, warnings, code = _render_with_mermaid(args)
    return _RenderResult(_report(text, warnings, code), mermaid=mermaid)


def _report(text: str, warnings: str, code: int) -> str:
    if code != 0:
        raise ValueError(warnings.strip())
    if warnings:
        sys.stderr.write(warnings)
    return text


def _render_args(options: _RenderOptions) -> list[str]:
    format_args = (
        ["--summary", "--output", options.output_format] if options.summary else _format_args(options.output_format)
    )
    args = ["--warn", options.warn, "--encoding", options.encoding, *format_args]
    for flag, value in (
        ("--packages", options.packages),
        ("--exclude", options.exclude),
        ("--python", options.python),
    ):
        if value is not None:
            args += [flag, value]
    if options.depth != inf:
        args += ["--depth", str(int(options.depth))]
    args += [
        "--extras",
        options.extras if isinstance(options.extras, str) else ("explicit" if options.extras else "none"),
    ]
    for flag, enabled in (
        ("--reverse", options.reverse),
        ("--local-only", options.local_only),
        ("--user-only", options.user_only),
    ):
        if enabled:
            args.append(flag)
    return args


def _format_args(output_format: str) -> list[str]:
    if output_format in _FORMAT_FLAGS:
        return _FORMAT_FLAGS[output_format]
    if output_format in _BINARY_GRAPHVIZ_FORMATS:
        msg = (
            "binary Graphviz formats cannot be returned as a string; use output_format='dot' for the Graphviz source, "
            "or run the pipdeptree CLI for binary output"
        )
        raise ValueError(msg)
    msg = f"unknown output_format {output_format!r}; expected one of {', '.join(_FORMAT_FLAGS)}"
    raise ValueError(msg)


def _summary_html(text: str) -> str:
    rows = "".join(
        f"<tr><td>{escape(label)}</td><td>{escape(value.strip())}</td></tr>"
        for line in text.splitlines()
        for label, _, value in (line.partition(":"),)
    )
    return f"<table>\n<tr><th>metric</th><th>value</th></tr>\n{rows}\n</table>"


@dataclass(frozen=True, slots=True)
class _RenderOptions:
    packages: str | None
    exclude: str | None
    output_format: str
    summary: bool
    reverse: bool
    depth: float
    extras: bool | str
    local_only: bool
    user_only: bool
    python: str | None
    encoding: str
    warn: str


class _RenderResult(str):  # noqa: FURB189  # Notebook results must retain concrete str behavior.
    __slots__ = ("_mermaid",)

    _mermaid: str

    def __new__(cls, text: str, *, mermaid: str) -> Self:
        self = super().__new__(cls, text)
        self._mermaid = mermaid
        return self

    def _repr_mimebundle_(
        self,
        include: Container[str] | None = None,
        exclude: Container[str] | None = None,
    ) -> dict[str, str]:
        bundle = {
            "text/html": f"<pre>{escape(str(self))}</pre>",
            "text/plain": str(self),
            "text/vnd.mermaid": self._mermaid,
        }
        return _filter_bundle(bundle, include, exclude)


class _SummaryResult(str):  # noqa: FURB189  # Notebook results must retain concrete str behavior.
    __slots__ = ("_html",)

    _html: str

    def __new__(cls, text: str, *, html: str) -> Self:
        self = super().__new__(cls, text)
        self._html = html
        return self

    def _repr_mimebundle_(
        self,
        include: Container[str] | None = None,
        exclude: Container[str] | None = None,
    ) -> dict[str, str]:
        return _filter_bundle({"text/html": self._html, "text/plain": str(self)}, include, exclude)


def _filter_bundle(
    bundle: dict[str, str],
    include: Container[str] | None,
    exclude: Container[str] | None,
) -> dict[str, str]:
    if include is not None:
        bundle = {key: value for key, value in bundle.items() if key in include}
    return bundle if exclude is None else {key: value for key, value in bundle.items() if key not in exclude}


__all__ = [
    "__version__",
    "render",
]
