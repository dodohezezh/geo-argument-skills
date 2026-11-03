"""Decisive tests: which single unknown outcome would retract the claim now."""

from __future__ import annotations

from typing import Any

from .contract import Case
from .judge import judge

_POWER_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, None: -1}


def _power_of(case: Case, test_ref: Any) -> str | None:
    refs = test_ref if isinstance(test_ref, list) else [test_ref]
    best: str | None = None
    for ref in refs:
        if isinstance(ref, str) and ref in case.tests_by_id:
            power = case.tests_by_id[ref].get("discriminating_power")
            if best is None or _POWER_ORDER.get(power, -1) > _POWER_ORDER.get(best, -1):
                best = power
    return best


def _cost_of(case: Case, test_ref: Any) -> float | None:
    """Cheapest declared cost among the tests that carry this outcome."""
    refs = test_ref if isinstance(test_ref, list) else [test_ref]
    costs = [
        case.tests_by_id[ref].get("cost")
        for ref in refs
        if isinstance(ref, str) and ref in case.tests_by_id
    ]
    numeric = [float(c) for c in costs if isinstance(c, (int, float)) and not isinstance(c, bool)]
    return min(numeric) if numeric else None


def decisive_events(case: Case) -> dict[str, Any]:
    """Flip each unknown item and keep the flips that defeat the claim.

    Only single-event defeat paths are enumerated: one established fatal
    defeater, one failed high-risk entailment, or one failed ceteris paribus
    condition. Combinations of degrading defeaters can also retract an
    argument; those are reported as a limitation rather than silently
    enumerated. Events are ranked by discriminating power, then by declared
    cost, so a cheap decisive test is not hidden behind an expensive one.
    """
    base = judge(case)
    candidates: list[tuple[str, str, str, str, Any]] = []

    for premise in case.argument.get("premises", []):
        if premise.get("kind") == "evidenced":
            candidates.append(
                ("premise", premise["id"], "unsupported", f"premise {premise['id']} loses its evidence", premise.get("test_refs"))
            )
    for cp in case.argument.get("inference", {}).get("cp", []):
        if cp.get("state", "unknown") != "holds":
            candidates.append(("cp", cp["id"], "fails", f"ceteris paribus condition {cp['id']} fails", cp.get("test_ref")))
    for defeater in case.argument.get("inference", {}).get("defeaters", []):
        if defeater.get("state", "unknown") != "refuted":
            candidates.append(
                ("defeater", defeater["id"], "established", f"defeater {defeater['id']} is established", defeater.get("test_ref"))
            )
    for entailment in case.argument.get("entailments", []):
        if entailment.get("status") != "passed":
            candidates.append(
                ("entailment", entailment["id"], "failed", f"entailment {entailment['id']} fails", entailment.get("test_ref"))
            )

    events = []
    for kind, ident, value, label, test_ref in candidates:
        trial = judge(case, {(kind, ident): value})
        if trial["verdict"] in ("DEFEATED", "SUSPENDED"):
            if isinstance(test_ref, list) and len(test_ref) == 1:
                test_ref = test_ref[0]
            events.append(
                {
                    "kind": kind,
                    "id": ident,
                    "outcome": value,
                    "label": label,
                    "test": test_ref,
                    "power": _power_of(case, test_ref),
                    "cost": _cost_of(case, test_ref),
                    "resulting_verdict": trial["verdict"],
                }
            )

    events.sort(key=lambda e: (-_POWER_ORDER.get(e["power"], -1), e["cost"] if e["cost"] is not None else float("inf"), e["label"]))

    return {
        "base_verdict": base["verdict"],
        "events": events,
        "note": (
            "single-event defeat paths only; combinations of degrading defeaters are not enumerated. "
            "cost is the cheapest declared test cost, in the same unit as test.yaml"
        ),
    }


def changing_events(events: list[dict], base_verdict: str) -> list[dict]:
    """Keep only the outcomes that would move the conclusion away from where it is."""
    return [event for event in events if event.get("resulting_verdict") != base_verdict]
