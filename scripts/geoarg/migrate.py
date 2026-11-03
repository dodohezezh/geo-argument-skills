"""Rewrite the schema_version lines of a case or bundle to the current schema.

The migration touches only the `schema_version:` line and preserves every other
byte, so comments, ordering and quoting survive. It is idempotent.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .bundle import BUNDLE_FILE, BUNDLE_SCHEMA_VERSION
from .chain import WORKSPACE_FILE, WORKSPACE_SCHEMA_VERSION
from .contract import CASE_FILES, ContractError, SCHEMA_VERSION

_LINE = re.compile(r"(?m)^schema_version:\s*(\S+)\s*$")


def _rewrite(path: Path, target: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = _LINE.search(text)
    if match is None:
        raise ContractError(f"{path.name}: no schema_version line")
    old = match.group(1)
    if old == target:
        return {"file": str(path), "old": old, "new": target, "changed": False}
    updated = text[: match.start(1)] + target + text[match.end(1) :]
    path.write_text(updated, encoding="utf-8")
    return {"file": str(path), "old": old, "new": target, "changed": True}


def _targets(root: Path) -> list[tuple[Path, str]]:
    if (root / "argument.yaml").is_file():
        return [(root / name, SCHEMA_VERSION) for name in CASE_FILES]
    if (root / BUNDLE_FILE).is_file():
        return [(root / BUNDLE_FILE, BUNDLE_SCHEMA_VERSION)]
    if (root / WORKSPACE_FILE).is_file():
        return [(root / WORKSPACE_FILE, WORKSPACE_SCHEMA_VERSION)]
    raise ContractError(f"no case, bundle or workspace under {root}")


def migrate(root: str | Path, dry_run: bool = False) -> list[dict[str, Any]]:
    """Return one row per file; write unless dry_run is true."""
    root = Path(root)
    rows: list[dict[str, Any]] = []
    for path, target in _targets(root):
        if not path.is_file():
            raise ContractError(f"missing {path.name}")
        if dry_run:
            text = path.read_text(encoding="utf-8")
            match = _LINE.search(text)
            if match is None:
                raise ContractError(f"{path.name}: no schema_version line")
            old = match.group(1)
            rows.append({"file": str(path), "old": old, "new": target, "changed": old != target})
        else:
            rows.append(_rewrite(path, target))
    return rows
