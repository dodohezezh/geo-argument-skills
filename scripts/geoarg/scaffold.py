"""Argument-pattern library and case scaffolding.

A pattern is a small, domain-flavoured skeleton: the recurring shape of a
geological argument (an age bracket, a sequence boundary, a slip rate) with
TODO markers where the author supplies the actual claim and evidence. Patterns
are data files under ``_patterns/`` so adding a domain family needs no code
change; a domain pack can also carry its own ``patterns/`` directory, and
``geoarg new`` renders one into the three contract files.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Any

import yaml

from .contract import CASE_FILES, ContractError, load_case, validate
from .safeio import atomic_write_text

PATTERN_DIR = Path(__file__).resolve().parent / "_patterns"
_PLACEHOLDER = re.compile(r"\{\{([a-z_]+)\}\}")


def _read_file(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContractError(f"cannot read pattern {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"pattern {path.name} must be a YAML mapping")
    for key in ("name", "argument", "evidence", "test"):
        if not data.get(key):
            raise ContractError(f"pattern {path.name} is missing {key!r}")
    return data


def _row(data: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "name": str(data["name"]),
        "title": str(data.get("title") or data["name"]),
        "domain": str(data.get("domain") or "other"),
        "description": str(data.get("description") or ""),
        "source": source,
        "argument": str(data["argument"]),
        "evidence": str(data["evidence"]),
        "test": str(data["test"]),
    }


def _builtin_patterns() -> list[dict[str, Any]]:
    if not PATTERN_DIR.is_dir():
        return []
    return [_row(_read_file(path), "builtin") for path in sorted(PATTERN_DIR.glob("*.yaml"))]


def _pack_patterns(pack: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in (pack or {}).get("patterns") or []:
        rows.append(
            {
                "name": row["name"],
                "title": row["title"],
                "domain": row["domain"],
                "description": row["description"],
                "source": f"pack:{pack['name']}",
                "argument": row["argument"],
                "evidence": row["evidence"],
                "test": row["test"],
            }
        )
    return rows


def all_patterns(pack: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return every pattern the case can use (pack patterns win on name clashes)."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in _pack_patterns(pack) + _builtin_patterns():
        if row["name"] in seen:
            continue
        seen.add(row["name"])
        rows.append(row)
    rows.sort(key=lambda row: row["name"])
    return rows


def list_patterns(pack: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return a catalogue (no document bodies) sorted by name."""
    return [
        {key: row[key] for key in ("name", "title", "domain", "description", "source")}
        for row in all_patterns(pack)
    ]


def load_pattern(name: str, pack: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load one pattern by name or file stem (pack patterns first)."""
    rows = all_patterns(pack)
    for row in rows:
        if row["name"] == name:
            return row
    for row in _pack_patterns(pack):
        if str(row["name"]).endswith(name):
            return row
    available = ", ".join(row["name"] for row in rows) or "none"
    raise ContractError(f"unknown pattern {name!r}; available: {available}")


def _render(text: str, values: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda match: values.get(match.group(1), match.group(0)), text)


def render_pattern(
    name: str,
    *,
    case_id: str,
    title: str | None = None,
    claim: str | None = None,
    today: str | None = None,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Render one pattern into the three contract documents."""
    pattern = load_pattern(name, pack)
    today = today or _dt.date.today().isoformat()
    resolved_title = title or str(pattern.get("title") or name)
    resolved_claim = claim or "TODO: state the claim in one sentence (what, where, how old)."
    values = {
        "id": case_id,
        "title": resolved_title,
        "claim": resolved_claim,
        "today": today,
    }
    documents: dict[str, str] = {}
    for key, filename in (("argument", "argument.yaml"), ("evidence", "evidence.yaml"), ("test", "test.yaml")):
        rendered = _render(str(pattern[key]), values)
        try:
            yaml.safe_load(rendered)
        except yaml.YAMLError as exc:
            raise ContractError(f"pattern {name!r} rendered invalid YAML for {filename}: {exc}") from exc
        documents[filename] = rendered
    return {"pattern": name, "documents": documents, "title": resolved_title}


def new_case(
    root: str | Path,
    pattern: str,
    *,
    case_id: str | None = None,
    title: str | None = None,
    claim: str | None = None,
    force: bool = False,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a rendered pattern into ``root`` and validate the result."""
    target_dir = Path(root)
    target_file = target_dir / "argument.yaml"
    if target_file.exists() and not force:
        raise ContractError(f"target already contains a contract: {target_file} (pass --force to overwrite)")
    cleaned_id = re.sub(r"[^A-Za-z0-9._-]+", "-", (case_id or target_dir.name).strip().lower()).strip("-._") or "case"
    rendered = render_pattern(pattern, case_id=cleaned_id, title=title, claim=claim, pack=pack)
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename in CASE_FILES:
        atomic_write_text(target_dir / filename, rendered["documents"][filename])
    documents = rendered["documents"]
    case = load_case(target_dir, attach_chain=False)
    case.domain_pack = pack
    problems = validate(case)
    return {
        "root": str(target_dir),
        "pattern": pattern,
        "pack": (pack or {}).get("name"),
        "case_id": cleaned_id,
        "title": rendered["title"],
        "todos": sum(documents[name].count("TODO") for name in CASE_FILES),
        "problems": problems,
    }


def render_patterns(rows: list[dict[str, Any]]) -> str:
    """Render the pattern catalogue for the CLI."""
    lines = ["# Argument patterns", ""]
    for row in rows:
        lines.append(f"- {row['name']}  ({row['domain']}, {row['source']})")
        lines.append(f"  {row['title']}")
        if row["description"]:
            lines.append(f"  {row['description']}")
    lines.append("")
    lines.append("create a draft case: geoarg new my-case --pattern <name>")
    return "\n".join(lines) + "\n"


def render_new_case(payload: dict[str, Any]) -> str:
    """Render the scaffold summary for the CLI."""
    lines = [
        f"case created: {payload['root']}",
        f"pattern: {payload['pattern']}",
    ]
    if payload.get("pack"):
        lines.append(f"domain pack: {payload['pack']}")
    lines.extend(
        [
            f"case id: {payload['case_id']}",
            f"TODO markers: {payload['todos']}",
            "",
            "next:",
            f"  geoarg check {payload['root']} --profile draft --explain",
            f"  geoarg judge {payload['root']}",
            f"  geoarg advise {payload['root']}",
        ]
    )
    if payload["problems"]:
        lines.append("")
        lines.append("hard problems after generation (please report):")
        for problem in payload["problems"]:
            lines.append(f"  - {problem}")
    return "\n".join(lines) + "\n"
