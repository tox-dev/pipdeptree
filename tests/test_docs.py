from __future__ import annotations

import doctest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path


def test_documented_cli_output(
    entry_point: Callable[[Sequence[str] | None], int | None],
    doctest_document: Path,
    documentation_path: Path,
) -> None:
    def run_pipdeptree(*args: str) -> str:
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            entry_point(["--path", str(documentation_path), "--warn", "silence", *args])
        return output.getvalue()

    test = doctest.DocTestParser().get_doctest(
        doctest_document.read_text(encoding="utf-8"),
        {"run_pipdeptree": run_pipdeptree},
        str(doctest_document),
        str(doctest_document),
        0,
    )

    result = doctest.DocTestRunner().run(test)

    assert result == doctest.TestResults(0, len(test.examples))
