"""Turn a Markdown outline into a starter GeoArg contract.

The importer is deliberately deterministic: it reads headings and bullets, maps
them to the three contract files, and marks every invented value with ``TODO``.
It never guesses domain values and never invents evidence: a claim without
evidence becomes a placeholder record so the draft still loads, and the author
replaces it. The result is a working skeleton that ``geoarg check --profile
draft`` can lint, not a finished argument.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Any

import yaml

from .contract import CASE_FILES, ContractError, load_case, validate
from .safeio import atomic_write_text

_SECTION_WORDS = (
    ("claim", "claim"),
    ("conclusion", "claim"),
    ("premise", "premises"),
    ("evidence", "evidence"),
    ("data", "evidence"),
    ("test", "tests"),
    ("check", "tests"),
    ("condition", "conditions"),
    ("defeater", "defeaters"),
    ("counter", "defeaters"),
    ("entailment", "entailments"),
    ("prediction", "entailments"),
)

_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")
_ID_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9._-]*)\s*[:：]\s*(.+)$")
_META_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9 _-]*)\s*[:：]\s*(.+)$")


def _section_key(text: str) -> str | None:
    cleaned = text.strip().strip("#").strip().lower()
    for word, key in _SECTION_WORDS:
        if word in cleaned:
            return key
    return None


def parse_markdown(text: str) -> dict[str, Any]:
    """Parse headings and bullets into section records."""
    sections: dict[str, list[dict[str, Any]]] = {
        "claim": [],
        "premises": [],
        "evidence": [],
        "tests": [],
        "conditions": [],
        "defeaters": [],
        "entailments": [],
    }
    current = "claim"
    last: dict[str, Any] | None = None
    counters = {key: 0 for key in sections}
    for raw in text.splitlines():
        line = raw.rstrip()
        heading = _HEADING.match(line)
        if heading:
            key = _section_key(heading.group(1))
            if key:
                current = key
                last = None
            continue
        bullet = _BULLET.match(line)
        if bullet:
            indent = len(bullet.group(1))
            body = bullet.group(2).strip()
            if indent <= 1 or last is None:
                ident, body_text = None, body
                match = _ID_LINE.match(body)
                if match:
                    ident, body_text = match.group(1), match.group(2).strip()
                counters[current] += 1
                item = {"id": ident or f"{current[:-1].upper() if current != 'premises' else 'P'}{counters[current]}", "text": body_text, "meta": {}}
                sections[current].append(item)
                last = item
            else:
                meta = _META_LINE.match(body)
                if meta and last is not None:
                    last["meta"][meta.group(1).strip().lower()] = meta.group(2).strip()
            continue
        if last is not None and line.strip():
            last["text"] = (last["text"] + " " + line.strip()).strip()
    return sections


def _slug(text: str, fallback: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip().lower()).strip("-._")
    return value or fallback


def _split_refs(value: str) -> list[str]:
    return [part for part in re.split(r"[,\s]+", value) if part]


def _dump(document: dict[str, Any], note: str) -> str:
    body = yaml.safe_dump(document, allow_unicode=True, sort_keys=False, default_flow_style=False, width=100)
    return f"# {note}\n" + body


def build_documents(
    sections: dict[str, Any],
    *,
    case_id: str,
    title: str,
    claim: str | None = None,
    today: str | None = None,
) -> dict[str, str]:
    """Build the three contract YAML documents for a draft case."""
    today = today or _dt.date.today().isoformat()
    claim_text = (claim or "").strip() or " ".join(item["text"] for item in sections["claim"]).strip()
    claim_text = claim_text or "TODO: state the claim in one sentence (what, where, how old)."

    evidence_rows = [row for row in sections["evidence"] if row.get("text")]
    evidence_ids: list[str] = []
    evidence_records: list[dict[str, Any]] = []
    for index, row in enumerate(evidence_rows, start=1):
        evidence_id = _slug(str(row.get("id") or f"ev.{index}"), f"ev.{index}")
        evidence_id = evidence_id if evidence_id.startswith("ev.") else f"ev.{evidence_id}"
        evidence_ids.append(evidence_id)
        locator = None
        quote = str(row["meta"].get("quote") or "").strip()
        if quote:
            page = row["meta"].get("page")
            locator = {"page": int(page) if str(page).isdigit() else 1, "quote": quote}
        record: dict[str, Any] = {
            "id": evidence_id,
            "kind": "observation",
            "layer": "L1",
            "statement": row["text"],
            "source": {"citation": str(row["meta"].get("citation") or row["meta"].get("source") or "TODO: full reference")},
            "coverage": {
                "spatial_extent": "TODO: spatial extent",
                "coverage_fraction": 0.0,
                "detectability": 0.0,
            },
            "independence": {
                "family": "unassigned",
                "independence_class": "data",
                "derived_from": [],
                "shared_sources": [],
            },
            "verification": {"level": "interpretation"},
            "status": "disputed",
        }
        if locator:
            record["source_locator"] = locator
        evidence_records.append(record)

    premise_rows = [row for row in sections["premises"] if row.get("text")]
    premises: list[dict[str, Any]] = []
    if not premise_rows:
        premise_rows = [{"id": "P1", "text": "TODO: write the first premise that carries the claim.", "meta": {}}]
    for index, row in enumerate(premise_rows, start=1):
        pid = str(row.get("id") or f"P{index}")
        refs = _split_refs(str(row["meta"].get("evidence") or row["meta"].get("refs") or ""))
        if not refs:
            refs = [evidence_ids[(index - 1) % len(evidence_ids)]] if evidence_ids else []
        premises.append(
            {
                "id": pid,
                "statement": row["text"],
                "kind": "evidenced",
                "layer": "L1",
                "status": "undetermined",
                "evidence_refs": refs,
            }
        )
    if not evidence_records:
        for index, premise in enumerate(premises, start=1):
            evidence_id = f"ev.todo.{index}"
            evidence_ids.append(evidence_id)
            evidence_records.append(
                {
                    "id": evidence_id,
                    "kind": "observation",
                    "layer": "L1",
                    "statement": "TODO: record the evidence behind premise " + str(premise["id"]) + ".",
                    "source": {"citation": "TODO: full reference"},
                    "coverage": {"spatial_extent": "TODO: spatial extent", "coverage_fraction": 0.0, "detectability": 0.0},
                    "independence": {
                        "family": "unassigned",
                        "independence_class": "data",
                        "derived_from": [],
                        "shared_sources": [],
                    },
                    "verification": {"level": "interpretation"},
                    "status": "disputed",
                }
            )
            premise["evidence_refs"] = [evidence_id]

    condition_rows = [row for row in sections["conditions"] if row.get("text")]
    cp_rows: list[dict[str, Any]] = []
    if not condition_rows:
        condition_rows = [{"id": "CP1", "text": "TODO: name the condition that must hold for the inference to work.", "meta": {}}]
    for index, row in enumerate(condition_rows, start=1):
        cp_rows.append(
            {
                "id": str(row.get("id") or f"CP{index}"),
                "statement": row["text"],
                "cp_type": "methodological",
                "state": "unknown",
                "test_ref": "T1",
            }
        )

    defeater_rows = [row for row in sections["defeaters"] if row.get("text")]
    defeaters: list[dict[str, Any]] = []
    if not defeater_rows:
        defeater_rows = [{"id": "D1", "text": "TODO: name the observation that would refute the claim.", "meta": {}}]
    for index, row in enumerate(defeater_rows, start=1):
        defeaters.append(
            {
                "id": str(row.get("id") or f"D{index}"),
                "type": "rebutting",
                "statement": row["text"],
                "severity": "fatal",
                "state": "unknown",
                "test_ref": "T1",
            }
        )

    entailment_rows = [row for row in sections["entailments"] if row.get("text")]
    entailments: list[dict[str, Any]] = []
    if not entailment_rows:
        entailment_rows = [{"id": "E1", "text": "TODO: write a prediction that fails if the claim is wrong.", "meta": {}}]
    for index, row in enumerate(entailment_rows, start=1):
        entailments.append(
            {
                "id": str(row.get("id") or f"E{index}"),
                "statement": row["text"],
                "kind": "geometric-consistency",
                "risk": "medium",
                "status": "untested",
                "test_ref": "T1",
            }
        )

    test_rows = [row for row in sections["tests"] if row.get("text")]
    tests: list[dict[str, Any]] = []
    if not test_rows:
        test_rows = [{"id": "T1", "text": "TODO: name the test that would settle the conditions above.", "meta": {}}]
    condition_ids = [row["id"] for row in cp_rows] + [row["id"] for row in defeaters] + [row["id"] for row in entailments]
    for index, row in enumerate(test_rows, start=1):
        checks = _split_refs(str(row["meta"].get("checks") or ""))
        if not checks:
            checks = condition_ids
        tests.append(
            {
                "id": str(row.get("id") or f"T{index}"),
                "name": row["text"],
                "checks": checks,
                "method": {"type": "literature-review", "description": "TODO: how the test is run"},
                "blind": {"is_blind": False},
                "discriminating_power": "none",
                "status": "planned",
                "cost": 1,
            }
        )

    argument = {
        "schema_version": "geoarg/0.7",
        "id": case_id,
        "title": title,
        "domain": "other",
        "claim": {
            "id": "C1",
            "statement": claim_text,
            "kind": "reconstruction",
            "layer": "L1",
            "scope": "TODO: spatial and temporal scope of the claim",
        },
        "premises": premises,
        "inference": {
            "rule_id": "W.todo",
            "warrant": "TODO: state the warrant that links the premises to the claim",
            "cp": cp_rows,
            "defeaters": defeaters,
        },
        "entailments": entailments,
        "dependencies": {
            "evidence_families": ["unassigned"],
            "shared_calibration": [],
            "depends_on": [],
        },
        "gaps": [],
        "audit": {
            "author": "TODO: author",
            "created": today,
            "updated": today,
            "version": "0.1-draft",
        },
    }
    evidence = {"schema_version": "geoarg/0.7", "records": evidence_records}
    test = {"schema_version": "geoarg/0.7", "records": tests}
    return {
        "argument.yaml": _dump(argument, "draft skeleton imported by geoarg adopt; every TODO is a question for the author"),
        "evidence.yaml": _dump(evidence, "draft evidence records: status disputed until the author accepts them and grounds the quotes"),
        "test.yaml": _dump(test, "draft tests: planned, power none until the author judges them"),
    }


def adopt_markdown(
    source: str | Path,
    out_dir: str | Path,
    *,
    case_id: str | None = None,
    title: str | None = None,
    claim: str | None = None,
    force: bool = False,
    today: str | None = None,
) -> dict[str, Any]:
    """Parse one Markdown file and write a draft case into ``out_dir``."""
    path = Path(source)
    if not path.exists():
        raise ContractError(f"markdown source not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read markdown source {path}: {exc}") from exc
    sections = parse_markdown(text)
    root = Path(out_dir)
    target = root / "argument.yaml"
    if target.exists() and not force:
        raise ContractError(f"target already contains a contract: {target} (pass --force to overwrite)")
    root.mkdir(parents=True, exist_ok=True)
    cleaned_id = _slug(case_id or root.name, "draft-case")
    if not title:
        first = " ".join(item["text"] for item in sections["claim"]).strip()
        title = first[:88] if first else f"Draft: {cleaned_id}"
    documents = build_documents(sections, case_id=cleaned_id, title=title, claim=claim, today=today)
    for name in CASE_FILES:
        atomic_write_text(root / name, documents[name])
    todos = sum(documents[name].count("TODO") for name in CASE_FILES)
    problems = validate(load_case(root, attach_chain=False))
    return {
        "root": str(root),
        "case_id": cleaned_id,
        "title": title,
        "todos": todos,
        "problems": problems,
        "counts": {
            "premises": len(sections["premises"]) or 1,
            "evidence": len(sections["evidence"]),
            "tests": len(sections["tests"]) or 1,
        },
    }


def render_adoption(payload: dict[str, Any]) -> str:
    """Render the adoption summary for the CLI."""
    lines = [
        f"draft written: {payload['root']}",
        f"case id: {payload['case_id']}",
        f"TODO markers: {payload['todos']}",
        "",
        "next:",
        f"  geoarg check {payload['root']} --profile draft --explain",
        "  fill every TODO, then run:",
        f"  geoarg check {payload['root']}",
        "  geoarg judge " + payload["root"],
    ]
    if payload["problems"]:
        lines.append("")
        lines.append("the draft still has this many hard problems after generation (report upstream):")
        for problem in payload["problems"]:
            lines.append(f"  - {problem}")
    return "\n".join(lines) + "\n"
