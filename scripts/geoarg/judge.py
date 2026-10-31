"""Deterministic verdict for a GeoArg contract.

The verdict is a rule-lattice result computed from the contract alone:
DEFEATED > SUSPENDED > UNTESTED > UNDETERMINED > SUPPORTED. Every step that
produced the verdict is recorded as a reason line, so the verdict can be
recomputed and challenged without the model that wrote the contract.
"""

from __future__ import annotations

from typing import Any

from .contract import Case

RULE_VERSION = "geoarg/0.2"

VERDICTS = ("DEFEATED", "SUSPENDED", "UNTESTED", "UNDETERMINED", "SUPPORTED")

_EVIDENCE_SUPPORT = {
    "accepted": "supported",
    "disputed": "disputed",
    "retracted": "unsupported",
    "superseded": "unsupported",
}


def _test_power(case: Case, test_ref: Any) -> str | None:
    refs = test_ref if isinstance(test_ref, list) else [test_ref]
    powers = []
    for ref in refs:
        if isinstance(ref, str) and ref in case.tests_by_id:
            powers.append(case.tests_by_id[ref].get("discriminating_power"))
    if not powers:
        return None
    order = {"none": 0, "low": 1, "medium": 2, "high": 3}
    best = max(powers, key=lambda p: order.get(p, -1))
    return best


def judge(case: Case, overrides: dict[tuple[str, str], str] | None = None) -> dict[str, Any]:
    """Return verdict, reason lines, per-item states, and gating tests."""
    ov = overrides or {}

    def state(kind: str, ident: str, default: str) -> str:
        return ov.get((kind, ident), default)

    hard: list[str] = []
    soft: list[str] = []
    pending: list[str] = []

    premises = []
    for p in case.argument.get("premises", []):
        pid = p.get("id")
        status = "supported"
        if p.get("kind") == "derived":
            status = "undetermined"  # v0.1 does not chain argument references
        else:
            for ref in p.get("evidence_refs") or []:
                rec = case.evidence_by_id.get(ref)
                if rec is None:
                    status = "missing-evidence"
                elif _EVIDENCE_SUPPORT.get(rec.get("status"), "undetermined") == "unsupported":
                    status = "unsupported"
        status = state("premise", pid, status)
        premises.append({"id": pid, "status": status, "statement": p.get("statement", "")})
        if status in ("unsupported", "missing-evidence"):
            hard.append(f"premise {pid} is {status}")
        elif status != "supported":
            pending.append(f"premise {pid} is {status}")

    cps = []
    for c in case.argument.get("inference", {}).get("cp", []):
        cid = c.get("id")
        st = state("cp", cid, c.get("state", "unknown"))
        cps.append({"id": cid, "state": st, "test": c.get("test_ref")})
        if st == "fails":
            hard.append(f"ceteris paribus condition {cid} fails")
        elif st != "holds":
            pending.append(f"ceteris paribus condition {cid} is {st}")

    defeaters = []
    for d in case.argument.get("inference", {}).get("defeaters", []):
        did = d.get("id")
        st = state("defeater", did, d.get("state", "unknown"))
        defeaters.append({"id": did, "state": st, "severity": d.get("severity"), "test": d.get("test_ref")})
        if st == "established":
            target = hard if d.get("severity") == "fatal" else soft
            target.append(f"defeater {did} established ({d.get('severity')})")
        elif st != "refuted":
            pending.append(f"defeater {did} is {st}")

    entailments = []
    for e in case.argument.get("entailments", []):
        eid = e.get("id")
        st = state("entailment", eid, e.get("status", "untested"))
        entailments.append({"id": eid, "status": st, "risk": e.get("risk"), "test": e.get("test_ref")})
        if st == "failed":
            target = hard if e.get("risk") == "high" else soft
            target.append(f"entailment {eid} failed (risk {e.get('risk')})")
        elif st != "passed":
            pending.append(f"entailment {eid} is {st}")

    any_run = any(t.get("status") in ("passed", "failed") for t in case.tests.get("records", []))
    if hard:
        verdict = "DEFEATED"
    elif soft:
        verdict = "SUSPENDED"
    elif not any_run:
        verdict = "UNTESTED"
    elif pending:
        verdict = "UNDETERMINED"
    else:
        verdict = "SUPPORTED"

    gating_refs: list[object] = []
    for p in case.argument.get("premises", []):
        gating_refs.extend(p.get("test_refs") or [])
    for c in case.argument.get("inference", {}).get("cp", []):
        gating_refs.append(c.get("test_ref"))
    for d in case.argument.get("inference", {}).get("defeaters", []):
        gating_refs.append(d.get("test_ref"))
    for e in case.argument.get("entailments", []):
        gating_refs.append(e.get("test_ref"))

    gating_tests = []
    for ref in dict.fromkeys(r for r in gating_refs if isinstance(r, str) and r):
        rec = case.tests_by_id.get(ref, {})
        gating_tests.append(
            {
                "id": ref,
                "power": rec.get("discriminating_power"),
                "status": rec.get("status"),
                "name": rec.get("name", ""),
            }
        )

    flags = []
    weak = [t for t in gating_tests if t["power"] in (None, "none", "low")]
    if verdict == "SUPPORTED" and weak:
        flags.append(
            "support rests on tests with no or low discriminating power: "
            + ", ".join(t["id"] for t in weak)
        )
    if verdict in ("SUPPORTED", "UNDETERMINED") and not gating_tests:
        flags.append("no test gates the verdict; the verdict is unaccounted for")
    blocking_gaps = [
        g for g in case.argument.get("gaps", []) if g.get("severity") == "blocking"
    ]
    for gap in blocking_gaps:
        flags.append(f"blocking gap registered: {gap.get('description', '')[:120]}")

    return {
        "rule_version": RULE_VERSION,
        "claim_id": case.claim.get("id"),
        "verdict": verdict,
        "reasons": {"hard": hard, "soft": soft, "pending": pending},
        "premises": premises,
        "cps": cps,
        "defeaters": defeaters,
        "entailments": entailments,
        "gating_tests": gating_tests,
        "flags": flags,
        "tests_run": any_run,
    }
