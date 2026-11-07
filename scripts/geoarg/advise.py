"""Field-aware advice from a domain pack.

`geoarg advise` is deterministic and optional: it reads the nearest domain pack
and compares it with what the case already declares. It never changes a verdict
and never commits anything. Its job is to turn a pack's field knowledge into a
short checklist for the author:

- which test methods the pack recommends for this claim kind, and which are
  still missing;
- which evidence families the pack expects, and which families the case already
  has;
- the pack's default profile and grounding hints;
- the pack's argument patterns (usable with ``geoarg new``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contract import Case, load_case


def _labels(lang: str) -> dict[str, str]:
    if str(lang).lower().startswith("zh"):
        return {
            "title": "# 领域建议",
            "pack": "领域包",
            "none": "当前案例没有 domain.yaml；没有可用的领域建议。",
            "claim": "主张",
            "profile": "建议 profile",
            "tests": "建议的检验",
            "families": "期望的证据族",
            "grounding": "接地提示",
            "patterns": "可用模式",
            "note": "建议不改变判决，也不提交记录；它只是作者的检查清单。",
            "present": "已有",
            "missing": "缺少",
            "why": "理由",
            "none_declared": "（无）",
            "create": "用模式起草：geoarg new <dir> --pattern <name>",
        }
    return {
        "title": "# Domain advice",
        "pack": "Domain pack",
        "none": "This case has no domain.yaml, so there is no field advice to give.",
        "claim": "Claim",
        "profile": "Suggested profile",
        "tests": "Suggested tests",
        "families": "Expected evidence families",
        "grounding": "Grounding hints",
        "patterns": "Usable patterns",
        "note": "Advice changes no verdict and commits nothing; it is an author checklist.",
        "present": "present",
        "missing": "missing",
        "why": "why",
        "none_declared": "(none)",
        "create": "scaffold from a pattern: geoarg new <dir> --pattern <name>",
    }


def _test_methods(case: Any) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for record in case.tests.get("records") or []:
        method = ((record.get("method") or {}).get("type")) if isinstance(record.get("method"), dict) else None
        key = str(method or "unknown")
        out.setdefault(key, []).append(str(record.get("id")))
    return out


def _declared_families(case: Any) -> set[str]:
    families: set[str] = set()
    for record in case.evidence.get("records") or []:
        family = ((record.get("independence") or {}).get("family")) if isinstance(record.get("independence"), dict) else None
        if family:
            families.add(str(family))
    return families


def advise(case_or_root: Case | str | Path) -> dict[str, Any]:
    """Return the advice payload for one case."""
    if isinstance(case_or_root, Case):
        case = case_or_root
        root = Path(case.root)
    else:
        root = Path(case_or_root)
        case = load_case(root)
    pack = case.domain_pack
    claim = case.claim or {}
    claim_kind = str(claim.get("kind") or "")
    payload: dict[str, Any] = {
        "case": str(root),
        "claim_id": claim.get("id"),
        "claim_kind": claim_kind,
        "pack": None,
        "default_profile": None,
        "recommended_tests": [],
        "evidence_families": [],
        "grounding": None,
        "patterns": [],
        "notes": [],
    }
    if pack is None:
        payload["notes"].append("no domain pack")
        return payload
    payload["pack"] = {"name": pack["name"], "path": str(pack["path"]), "title": pack["title"]}
    payload["default_profile"] = pack.get("default_profile")
    methods = _test_methods(case)
    for row in (pack.get("test_suggestions") or {}).get(claim_kind, []):
        payload["recommended_tests"].append(
            {
                "method": row["method"],
                "why": row.get("why") or "",
                "present": row["method"] in methods,
                "test_ids": methods.get(row["method"], []),
            }
        )
    declared = _declared_families(case)
    for row in pack.get("evidence_families") or []:
        payload["evidence_families"].append(
            {
                "name": row["name"],
                "independence_class": row.get("independence_class") or "",
                "why": row.get("why") or "",
                "present": row["name"] in declared,
            }
        )
    payload["grounding"] = pack.get("grounding")
    payload["patterns"] = [
        {"name": row["name"], "title": row["title"], "description": row["description"]}
        for row in pack.get("patterns") or []
    ]
    return payload


def _mark(present: bool, labels: dict[str, str]) -> str:
    return labels["present"] if present else labels["missing"]


def render_advise(payload: dict[str, Any], lang: str = "en") -> str:
    labels = _labels(lang)
    lines = [labels["title"], ""]
    if payload.get("pack") is None:
        lines.append(labels["none"])
        lines.append("")
        lines.append(labels["note"])
        return "\n".join(lines) + "\n"
    lines.append(f"## {labels['pack']}: {payload['pack']['name']}")
    lines.append(f"- {payload['pack']['path']}")
    lines.append("")
    lines.append(f"## {labels['claim']}")
    lines.append(f"- {payload['claim_id']}: {payload['claim_kind']}")
    if payload.get("default_profile"):
        profile = payload["default_profile"]
        secondary = ", ".join(profile["secondary"]) if profile["secondary"] else labels["none_declared"]
        lines.append("")
        lines.append(f"## {labels['profile']}")
        lines.append(f"- primary: {profile['primary']}; secondary: {secondary}")
        if profile["rationale"]:
            lines.append(f"- {profile['rationale']}")
    lines.append("")
    lines.append(f"## {labels['tests']}")
    if not payload["recommended_tests"]:
        lines.append(f"- {labels['none_declared']}")
    for row in payload["recommended_tests"]:
        mark = _mark(row["present"], labels)
        ids = f" ({', '.join(row['test_ids'])})" if row["test_ids"] else ""
        why = f" - {row['why']}" if row["why"] else ""
        lines.append(f"- `{row['method']}`: {mark}{ids}{why}")
    lines.append("")
    lines.append(f"## {labels['families']}")
    if not payload["evidence_families"]:
        lines.append(f"- {labels['none_declared']}")
    for row in payload["evidence_families"]:
        mark = _mark(row["present"], labels)
        independence = f" ({row['independence_class']})" if row["independence_class"] else ""
        why = f" - {row['why']}" if row["why"] else ""
        lines.append(f"- {row['name']}{independence}: {mark}{why}")
    if payload.get("grounding"):
        lines.append("")
        lines.append(f"## {labels['grounding']}")
        formats = ", ".join(payload["grounding"]["formats"]) or "-"
        lines.append(f"- formats: {formats}")
        for note in payload["grounding"]["notes"]:
            lines.append(f"- {note}")
    if payload.get("patterns"):
        lines.append("")
        lines.append(f"## {labels['patterns']}")
        for row in payload["patterns"]:
            lines.append(f"- `{row['name']}`: {row['title']}")
        lines.append("")
        lines.append(f"  {labels['create']}")
    lines.append("")
    lines.append(labels["note"])
    return "\n".join(lines) + "\n"


def advise_problems(payload: dict[str, Any]) -> list[str]:
    """Turn missing suggestions into plain checklist lines (for check --advise)."""
    problems: list[str] = []
    for row in payload.get("recommended_tests") or []:
        if not row["present"]:
            tail = f": {row['why']}" if row["why"] else ""
            problems.append(f"suggested test method {row['method']!r}{tail}")
    for row in payload.get("evidence_families") or []:
        if not row["present"]:
            tail = f": {row['why']}" if row["why"] else ""
            problems.append(f"no evidence from the suggested family {row['name']!r}{tail}")
    return problems
