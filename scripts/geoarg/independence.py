"""Independence accounting: families, shared calibration, effective evidence count.

Independence is a property of the calibration chain, not of the field. Two
records that feel like separate evidence are often downstream of the same
model, the same timescale, the same data release, or the same inference step.
This module estimates how much of an argument's "n independent lines" survives
that sharing.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from .contract import Case

_RHO_BY_CLASS = {
    "shared-calibration": 0.75,
    "data": 0.60,
    "method": 0.45,
    "physical": 0.15,
}
_FAMILY_RHO = 0.35
_BASE_RHO = 0.05


def pair_rho(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Estimated correlation between two evidence records' error terms."""
    ind_a = a.get("independence", {}) or {}
    ind_b = b.get("independence", {}) or {}
    shared = set(ind_a.get("shared_sources", [])) & set(ind_b.get("shared_sources", []))
    if shared:
        return _RHO_BY_CLASS["shared-calibration"]
    class_a = ind_a.get("independence_class")
    class_b = ind_b.get("independence_class")
    if class_a and class_a == class_b:
        return _RHO_BY_CLASS.get(class_a, 0.5)
    if ind_a.get("family") and ind_a.get("family") == ind_b.get("family"):
        return _FAMILY_RHO
    return _BASE_RHO


def effective_n(records: list[dict[str, Any]]) -> tuple[float, float]:
    """Return (n_eff, mean pairwise rho) for a set of evidence records."""
    n = len(records)
    if n < 2:
        return float(n), 0.0
    rhos = [pair_rho(a, b) for a, b in combinations(records, 2)]
    rho_bar = sum(rhos) / len(rhos)
    n_eff = n / (1.0 + (n - 1) * rho_bar)
    return n_eff, rho_bar


def _n_eff_at(n: int, rho: float) -> float:
    if n < 2:
        return float(n)
    return n / (1.0 + (n - 1) * rho)


def stress(records: list[dict[str, Any]], rho_bar: float) -> dict[str, Any]:
    """Show how n_eff moves when the assumed correlation is wrong.

    The rho values are inferred from declared fields, not measured, so the
    point estimate alone invites over-confidence. These scenarios keep the
    count fixed and vary the assumed pairwise correlation from 0 (independent)
    to 1 (one line in disguise).
    """
    n = len(records)
    scenarios = []
    for rho in (0.0, 0.25, 0.5, 0.75, 1.0):
        scenarios.append({"assumed_rho": rho, "n_eff": round(_n_eff_at(n, rho), 2)})
    for multiplier in (0.5, 2.0):
        rho = min(1.0, max(0.0, rho_bar * multiplier))
        scenarios.append(
            {
                "assumed_rho": round(rho, 3),
                "n_eff": round(_n_eff_at(n, rho), 2),
                "multiplier": multiplier,
            }
        )
    values = [item["n_eff"] for item in scenarios]
    return {
        "scenarios": scenarios,
        "min": min(values),
        "max": max(values),
        "note": "n_eff if every pair's rho were the assumed value; the reported n_eff sits at "
        "mean_rho, this range shows how sensitive that number is",
    }


def _counter_report(case: Case) -> dict[str, Any]:
    from .contract import referenced_counter_evidence

    mapping = referenced_counter_evidence(case)
    ids = list(dict.fromkeys(mapping))
    referenced = [case.evidence_by_id[item] for item in ids if item in case.evidence_by_id]
    records = [record for record in referenced if record.get("status") == "accepted"]
    excluded = [
        {"id": record.get("id"), "status": record.get("status")}
        for record in referenced
        if record.get("status") != "accepted"
    ]
    n_eff, rho_bar = effective_n(records)
    families = sorted(
        {(record.get("independence", {}) or {}).get("family") for record in records if record.get("independence")}
    )
    return {
        "ids": ids,
        "n_records": len(records),
        "n_eff": round(n_eff, 2),
        "mean_rho": round(rho_bar, 3),
        "families": families,
        "excluded": excluded,
        "note": "counter-evidence is not counted as support; its n_eff measures how independent the counter lines are",
    }


def report(case: Case) -> dict[str, Any]:
    """Build the independence report for the premises' evidence records.

    A record that is disputed, retracted, or superseded cannot support a
    premise, so it does not count as independent evidence either. Records are
    deduplicated: one record cited twice is still one line of evidence.
    """
    refs: list[str] = []
    for premise in case.argument.get("premises", []):
        refs.extend(premise.get("evidence_refs") or [])
    refs = list(dict.fromkeys(refs))
    referenced = [case.evidence_by_id[r] for r in refs if r in case.evidence_by_id]
    records = [r for r in referenced if r.get("status") == "accepted"]
    excluded = [
        {"id": r.get("id"), "status": r.get("status")}
        for r in referenced
        if r.get("status") != "accepted"
    ]
    n_eff, rho_bar = effective_n(records)

    pairs = []
    for a, b in combinations(records, 2):
        ind_a = a.get("independence", {}) or {}
        ind_b = b.get("independence", {}) or {}
        shared = sorted(set(ind_a.get("shared_sources", [])) & set(ind_b.get("shared_sources", [])))
        pairs.append(
            {
                "a": a.get("id"),
                "b": b.get("id"),
                "rho": round(pair_rho(a, b), 3),
                "shared_sources": shared,
                "families": [ind_a.get("family"), ind_b.get("family")],
            }
        )

    warnings = []
    for record in records:
        ind = record.get("independence", {}) or {}
        shared = ind.get("shared_sources") or []
        rec_class = ind.get("independence_class")
        if shared and rec_class != "shared-calibration":
            warnings.append(
                f"{record.get('id')}: shares {shared} with other records but is labelled "
                f"{rec_class!r}; shared calibration must be counted at the calibration level"
            )
        if rec_class == "physical" and ind.get("family"):
            same_family = [
                other.get("id")
                for other in records
                if other is not record
                and (other.get("independence", {}) or {}).get("family") == ind.get("family")
            ]
            if same_family:
                warnings.append(
                    f"{record.get('id')}: labelled physical but shares evidence family "
                    f"{ind.get('family')} with {same_family}"
                )

    families = sorted({(r.get("independence", {}) or {}).get("family") for r in records if r.get("independence")})
    declared = case.argument.get("dependencies", {}).get("shared_calibration", [])
    covered = {src for r in records for src in (r.get("independence", {}) or {}).get("shared_sources", [])}
    undeclared = [cal for cal in declared if cal not in covered]

    return {
        "n_records": len(records),
        "n_eff": round(n_eff, 2),
        "mean_rho": round(rho_bar, 3),
        "families": families,
        "pairs": pairs,
        "warnings": warnings,
        "excluded_records": excluded,
        "declared_calibration_not_attached": undeclared,
        "counter": _counter_report(case),
        "stress": stress(records, rho_bar),
        "note": "n_eff = n / (1 + (n - 1) * mean_rho); rho is inferred from the shared "
        "calibration/method/data claims recorded in evidence.yaml",
    }
