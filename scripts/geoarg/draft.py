"""Detect draft placeholders before a case is treated as finished.

`geoarg new` and `geoarg adopt` write contracts with explicit ``TODO`` markers so
the author can find every guessed value. Those markers are valid YAML and pass
structural validation, so without this check a scaffold could be committed and
verified as if it were a finished argument. This module is deliberately outside
the engine digest: it does not change a verdict, it only gates `check` and
`commit`.
"""

from __future__ import annotations

from typing import Any

from .contract import Case

MARKER = "TODO"
LIMIT = 3


def _walk(value: Any, where: str, found: list[str]) -> None:
    if isinstance(value, str):
        if MARKER in value:
            text = " ".join(value.split())
            if len(text) > 96:
                text = text[:93] + "..."
            found.append(f"{where}: {text}")
    elif isinstance(value, dict):
        for key, item in value.items():
            child = f"{where}.{key}" if where else str(key)
            _walk(item, child, found)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk(item, f"{where}[{index}]", found)


def draft_markers(case: Case) -> list[str]:
    """Return every string in the contract that still contains a TODO marker."""
    found: list[str] = []
    _walk(case.argument, "argument", found)
    _walk(case.evidence, "evidence", found)
    _walk(case.tests, "test", found)
    return found


def draft_summary(case: Case) -> str | None:
    """One-line summary for CLI output, or None when the contract is clean."""
    found = draft_markers(case)
    if not found:
        return None
    shown = found[:LIMIT]
    extra = len(found) - len(shown)
    text = "; ".join(shown)
    if extra > 0:
        text += f" (+{extra} more)"
    return text
