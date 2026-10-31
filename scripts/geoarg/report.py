"""Render a human-readable GeoArg report from a case."""

from __future__ import annotations

from typing import Any

from .audit import case_digest
from .contract import Case
from .hitting import decisive_events
from .independence import report as independence_report
from .judge import judge


def _table(rows: list[list[str]], header: list[str]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def render(case: Case) -> str:
    result = judge(case)
    indep = independence_report(case)
    decisive = decisive_events(case)
    claim = case.claim

    out: list[str] = []
    out.append(f"# GeoArg report: {case.argument.get('title', 'untitled')}")
    out.append("")
    out.append(f"- claim: `{claim.get('id')}` ({claim.get('kind')}, {claim.get('layer')})")
    out.append(f"- statement: {claim.get('statement')}")
    out.append(f"- verdict: **{result['verdict']}**")
    out.append(f"- rule version: `{result['rule_version']}`")
    flags = result["flags"]
    if flags:
        out.append("- flags: " + "; ".join(flags))
    out.append("")

    out.append("## Why this verdict")
    for key, title in (("hard", "hard defeat"), ("soft", "suspension"), ("pending", "unresolved")):
        reasons = result["reasons"][key]
        out.append(f"### {title}")
        out.extend(f"- {reason}" for reason in reasons) if reasons else out.append("- none")
        out.append("")

    out.append("## Premises")
    out.append(_table([[p["id"], p["status"], p["statement"]] for p in result["premises"]], ["id", "state", "statement"]))
    out.append("")

    out.append("## Ceteris paribus conditions")
    out.append(_table([[c["id"], c["state"], c["test"]] for c in result["cps"]], ["id", "state", "test"]))
    out.append("")

    out.append("## Defeaters")
    out.append(_table([[d["id"], d["state"], d["severity"], d["test"]] for d in result["defeaters"]], ["id", "state", "severity", "test"]))
    out.append("")

    out.append("## Entailments")
    out.append(_table([[e["id"], e["status"], e["risk"], e["test"]] for e in result["entailments"]], ["id", "status", "risk", "test"]))
    out.append("")

    out.append("## Independence")
    out.append(
        f"- effective independent evidence: **n_eff = {indep['n_eff']}** out of {indep['n_records']} records "
        f"(mean rho = {indep['mean_rho']})"
    )
    out.append(f"- families: {', '.join(indep['families']) or 'none'}")
    for warning in indep["warnings"]:
        out.append(f"- warning: {warning}")
    if indep["declared_calibration_not_attached"]:
        out.append(f"- declared but unattached calibration: {indep['declared_calibration_not_attached']}")
    out.append("")

    out.append("## Decisive tests")
    out.append(f"Base verdict is **{decisive['base_verdict']}**. These single outcomes would retract the claim now:")
    if decisive["events"]:
        out.append(
            _table(
                [[e["label"], e["test"], e["power"], e["resulting_verdict"]] for e in decisive["events"]],
                ["outcome", "test", "power", "result"],
            )
        )
    else:
        out.append("- none found (the claim is already defeated, or the contract has no live unknown items)")
    out.append("")
    out.append(f"_{decisive['note']}_")
    out.append("")

    gaps = case.argument.get("gaps", [])
    if gaps:
        out.append("## Registered gaps")
        out.append(_table([[g.get("kind"), g.get("severity"), g.get("description")] for g in gaps], ["kind", "severity", "description"]))
        out.append("")

    out.append("## Audit")
    for name, digest in case_digest(case.root).items():
        out.append(f"- {name}: `{digest}`")
    out.append("")
    return "\n".join(out)
