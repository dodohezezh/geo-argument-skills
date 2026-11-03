"""Aggregate several GeoArg cases into one paper bundle.

A paper usually carries more than one claim. The bundle lists the cases and
reports the weakest verdict among the required claims, so a paper cannot look
stronger than its weakest argument.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .contract import ContractError, load_case, validate
from .judge import judge

BUNDLE_FILE = "bundle.yaml"
BUNDLE_SCHEMA_VERSION = "geoarg/bundle/0.1"

_SEVERITY = {"SUPPORTED": 0, "UNDETERMINED": 1, "UNTESTED": 2, "SUSPENDED": 3, "DEFEATED": 4}
_VERDICT_ZH = {
    "SUPPORTED": "成立",
    "UNDETERMINED": "无法判定",
    "UNTESTED": "未检验",
    "SUSPENDED": "被削弱",
    "DEFEATED": "被推翻",
}


def _verdict_text(verdict: str | None, lang: str) -> str:
    if verdict and lang == "zh":
        return _VERDICT_ZH.get(verdict, verdict)
    return verdict or "-"

_LABELS = {
    "en": {
        "title": "GeoArg paper bundle: {title}",
        "intro": "One paper, several claims. The bundle conclusion is the weakest required claim.",
        "claim": "claim",
        "claim_title": "title",
        "verdict": "verdict",
        "case": "case",
        "aggregate": "bundle conclusion: {verdict}",
        "aggregate_none": "bundle conclusion: no required claims",
        "missing": "missing",
        "invalid": "invalid",
        "problems": "problems:",
    },
    "zh": {
        "title": "GeoArg 论文组：{title}",
        "intro": "一篇论文，多条主张。论文结论取所有必需主张里最弱的一条。",
        "claim": "主张",
        "claim_title": "标题",
        "verdict": "结论",
        "case": "案例",
        "aggregate": "论文结论：{verdict}",
        "aggregate_none": "论文结论：没有必需主张",
        "missing": "缺失",
        "invalid": "不合规",
        "problems": "问题：",
    },
}


def _labels(lang: str) -> dict[str, str]:
    return _LABELS["zh" if lang == "zh" else "en"]


def _load(root: Path) -> dict[str, Any]:
    path = root / BUNDLE_FILE
    if not path.is_file():
        raise ContractError(f"no {BUNDLE_FILE} under {root}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContractError(f"{BUNDLE_FILE}: unreadable ({exc})") from exc
    if not isinstance(data, dict):
        raise ContractError(f"{BUNDLE_FILE}: top level must be a mapping")
    claims = data.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ContractError(f"{BUNDLE_FILE}: claims must be a non-empty list")
    return data


def build_bundle(root: str | Path) -> dict[str, Any]:
    """Load a bundle, run each required case, and aggregate the verdicts."""
    root = Path(root)
    labels = _labels("en")
    problems: list[str] = []
    rows: list[dict[str, Any]] = []
    try:
        data = _load(root)
    except ContractError as exc:
        return {
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "id": None,
            "title": None,
            "claims": [],
            "aggregate": None,
            "problems": [str(exc)],
            "ok": False,
        }
    schema = data.get("schema_version")
    if schema != BUNDLE_SCHEMA_VERSION:
        problems.append(f"bundle schema is {schema!r}, expected {BUNDLE_SCHEMA_VERSION}")
    seen: set[str] = set()
    for claim in data.get("claims", []):
        if not isinstance(claim, dict) or not isinstance(claim.get("case"), str) or not claim["case"].strip():
            problems.append("bundle claim must be a mapping with a non-empty case path")
            continue
        case_path = claim["case"].strip()
        if case_path in seen:
            problems.append(f"bundle claim repeats the case path {case_path!r}")
        seen.add(case_path)
        required = bool(claim.get("required", True))
        row: dict[str, Any] = {"case": case_path, "required": required, "label": claim.get("label")}
        case_dir = (root / case_path).resolve()
        if not (case_dir / "argument.yaml").is_file():
            row["verdict"] = labels["missing"]
            problems.append(f"case not found: {case_path}")
            rows.append(row)
            continue
        try:
            case = load_case(case_dir)
        except ContractError as exc:
            row["verdict"] = labels["invalid"]
            problems.append(f"{case_path}: {exc}")
            rows.append(row)
            continue
        invalid = validate(case)
        if invalid:
            row["verdict"] = labels["invalid"]
            problems.extend(f"{case_path}: {problem}" for problem in invalid)
            rows.append(row)
            continue
        result = judge(case)
        row.update(
            {
                "claim": case.claim.get("id"),
                "title": case.claim.get("statement"),
                "verdict": result["verdict"],
            }
        )
        rows.append(row)
    required_verdicts = [row["verdict"] for row in rows if row.get("required") and row.get("verdict") in _SEVERITY]
    aggregate = max(required_verdicts, key=lambda v: _SEVERITY[v]) if required_verdicts else None
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "id": data.get("id"),
        "title": data.get("title"),
        "claims": rows,
        "aggregate": aggregate,
        "problems": problems,
        "ok": not problems,
    }


def render_bundle(root: str | Path, lang: str = "en") -> str:
    """Markdown bundle report in plain language."""
    labels = _labels(lang)
    payload = build_bundle(root)
    title = payload.get("title") or Path(root).name
    lines = [f"# {labels['title'].format(title=title)}", "", labels["intro"], ""]
    lines.append(f"| {labels['claim']} | {labels['claim_title']} | {labels['verdict']} | {labels['case']} |")
    lines.append("|---|---|---|---|")
    for row in payload["claims"]:
        claim = row.get("claim") or "-"
        claim_title = (row.get("title") or "-").replace("|", "\\|")
        verdict = _verdict_text(row.get("verdict"), lang)
        case_path = row.get("case") or "-"
        lines.append(f"| {claim} | {claim_title} | {verdict} | {case_path} |")
    lines.append("")
    if payload["aggregate"]:
        lines.append(labels["aggregate"].format(verdict=_verdict_text(payload["aggregate"], lang)))
    else:
        lines.append(labels["aggregate_none"])
    if payload["problems"]:
        lines.extend(["", labels["problems"]])
        lines.extend(f"- {problem}" for problem in payload["problems"])
    return "\n".join(lines).rstrip() + "\n"
