"""Deterministic verdict for a GeoArg contract.

The verdict is a rule-lattice result computed from the contract alone:
DEFEATED > SUSPENDED > UNTESTED > UNDETERMINED > SUPPORTED. Every step that
produced the verdict is recorded as a reason line, so the verdict can be
recomputed and challenged without the model that wrote the contract.

A satisfied state (a premise is backed, a ceteris paribus condition holds, a
defeater is refuted, an entailment passes) only counts when a referenced test
has actually passed. A state field alone never lifts the verdict.
"""

from __future__ import annotations

from typing import Any

from .contract import Case
from .results import effective_status, test_status_summary

RULE_VERSION = "geoarg/0.6"

VERDICTS = ("DEFEATED", "SUSPENDED", "UNTESTED", "UNDETERMINED", "SUPPORTED")

_POWER_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, None: -1}

_EVIDENCE_SUPPORT = {
    "accepted": "supported",
    "disputed": "disputed",
    "retracted": "unsupported",
    "superseded": "unsupported",
}
_EVIDENCE_RANK = {
    "supported": 0,
    "undetermined": 1,
    "disputed": 2,
    "unsupported": 3,
    "missing-evidence": 4,
}

# A derived premise takes the state of the argument it points at. The verdict
# words of that argument map onto chain states; anything that is not a clean
# SUPPORTED/DEFEATED result leaves the premise pending, not satisfied.
_CHAIN_STATE = {
    "SUPPORTED": "chain-supported",
    "SUSPENDED": "chain-disputed",
    "DEFEATED": "chain-unsupported",
    "UNTESTED": "chain-undetermined",
    "UNDETERMINED": "chain-undetermined",
}


def _test_records(case: Case, test_ref: Any) -> list[dict[str, Any]]:
    refs = test_ref if isinstance(test_ref, list) else [test_ref]
    return [case.tests_by_id[ref] for ref in refs if isinstance(ref, str) and ref in case.tests_by_id]


def _backing(case: Case, test_ref: Any) -> tuple[bool, str]:
    """Can a satisfied state claim be backed by a passed test?

    A passed test with discriminating power "none" cannot move a claim to
    supported: it is the "passing changes nothing" case the skills describe.
    """
    records = _test_records(case, test_ref)
    states = [(record, effective_status(record)) for record in records]
    passed = [record for record, state in states if state["status"] == "passed"]
    if any(r.get("discriminating_power") in ("low", "medium", "high") for r in passed):
        return True, ""
    if passed:
        return False, "only a passed test with discriminating power none backs it"
    if any(state["status"] == "failed" for _, state in states):
        return False, "a referenced test failed"
    return False, "no referenced test has passed"


def _detail_code(detail: str) -> str:
    """Turn a backing failure into a stable code the renderers can raise."""
    if "discriminating power none" in detail:
        return "none-power"
    if "test failed" in detail:
        return "failed"
    return "no-pass"


def judge(
    case: Case,
    overrides: dict[tuple[str, str], str] | None = None,
    chain: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return verdict, reason lines, per-item states, and gating tests."""
    ov = overrides or {}
    chain_map = chain if chain is not None else (getattr(case, "chain", None) or None)

    def state(kind: str, ident: str, default: str) -> str:
        return ov.get((kind, ident), default)

    hard: list[str] = []
    soft: list[str] = []
    pending: list[str] = []
    unbacked: list[str] = []
    reason_items: list[dict[str, Any]] = []

    premises = []
    for p in case.argument.get("premises", []):
        pid = p.get("id")
        status = "supported"
        chain_entry = None
        if p.get("kind") == "derived":
            ref = str(p.get("argument_ref") or "")
            if not chain_map:
                status = "undetermined"  # no workspace: the chain cannot be followed
            else:
                chain_entry = chain_map.get(ref) if isinstance(chain_map, dict) else None
                if not isinstance(chain_entry, dict):
                    status = "chain-unresolved"
                elif chain_entry.get("status") == "cycle":
                    status = "chain-cycle"
                elif chain_entry.get("status") == "resolved":
                    status = _CHAIN_STATE.get(chain_entry.get("verdict"), "chain-undetermined")
                else:
                    status = "chain-unresolved"
        else:
            for ref in p.get("evidence_refs") or []:
                rec = case.evidence_by_id.get(ref)
                if rec is None:
                    current = "missing-evidence"
                else:
                    current = _EVIDENCE_SUPPORT.get(rec.get("status"), "undetermined")
                if _EVIDENCE_RANK[current] > _EVIDENCE_RANK[status]:
                    status = current
        status = state("premise", pid, status)
        entry = {
            "id": pid,
            "status": status,
            "statement": p.get("statement", ""),
        }
        if chain_entry is not None:
            entry["chain"] = {
                "ref": chain_entry.get("ref"),
                "case": chain_entry.get("case"),
                "argument_id": chain_entry.get("argument_id"),
                "claim_id": chain_entry.get("claim_id"),
                "verdict": chain_entry.get("verdict"),
                "status": chain_entry.get("status"),
                "cycle": chain_entry.get("cycle"),
            }
        premises.append(entry)
        if status in ("unsupported", "missing-evidence", "chain-unsupported"):
            hard.append(f"premise {pid} is {status}")
            item = {"kind": "premise", "id": pid, "state": status, "bucket": "hard"}
            if p.get("kind") == "derived":
                item["derived"] = True
            if entry.get("chain"):
                item["chain"] = entry["chain"]
            reason_items.append(item)
        elif status in ("supported", "chain-supported"):
            # A premise is supported by its evidence record, not by a test
            # outcome: the tests listed on a premise probe its robustness. A
            # derived premise is supported by the verdict of the argument it
            # points at.
            pass
        else:
            pending.append(f"premise {pid} is {status}")
            item = {
                "kind": "premise",
                "id": pid,
                "state": status,
                "bucket": "pending",
                "derived": p.get("kind") == "derived",
            }
            if entry.get("chain"):
                item["chain"] = entry["chain"]
            reason_items.append(item)

    cps = []
    for c in case.argument.get("inference", {}).get("cp", []):
        cid = c.get("id")
        st = state("cp", cid, c.get("state", "unknown"))
        cps.append({"id": cid, "state": st, "test": c.get("test_ref")})
        if st == "fails":
            hard.append(f"ceteris paribus condition {cid} fails")
            reason_items.append({"kind": "cp", "id": cid, "state": st, "bucket": "hard"})
        elif st == "holds":
            backed, detail = _backing(case, c.get("test_ref"))
            if not backed:
                unbacked.append(f"cp {cid}: {detail}")
                pending.append(f"ceteris paribus condition {cid} claims holds but {detail}")
                reason_items.append(
                    {"kind": "cp", "id": cid, "state": st, "bucket": "pending", "detail": _detail_code(detail)}
                )
        else:
            pending.append(f"ceteris paribus condition {cid} is {st}")
            reason_items.append({"kind": "cp", "id": cid, "state": st, "bucket": "pending"})

    defeaters = []
    for d in case.argument.get("inference", {}).get("defeaters", []):
        did = d.get("id")
        st = state("defeater", did, d.get("state", "unknown"))
        defeaters.append({"id": did, "state": st, "severity": d.get("severity"), "test": d.get("test_ref")})
        if st == "established":
            target = hard if d.get("severity") == "fatal" else soft
            target.append(f"defeater {did} established ({d.get('severity')})")
            reason_items.append(
                {
                    "kind": "defeater",
                    "id": did,
                    "state": st,
                    "severity": d.get("severity"),
                    "bucket": "hard" if d.get("severity") == "fatal" else "soft",
                }
            )
        elif st == "refuted":
            backed, detail = _backing(case, d.get("test_ref"))
            if not backed:
                unbacked.append(f"defeater {did}: {detail}")
                pending.append(f"defeater {did} claims refuted but {detail}")
                reason_items.append(
                    {"kind": "defeater", "id": did, "state": st, "bucket": "pending", "detail": _detail_code(detail)}
                )
        else:
            pending.append(f"defeater {did} is {st}")
            reason_items.append({"kind": "defeater", "id": did, "state": st, "bucket": "pending"})

    entailments = []
    for e in case.argument.get("entailments", []):
        eid = e.get("id")
        st = state("entailment", eid, e.get("status", "untested"))
        entailments.append({"id": eid, "status": st, "risk": e.get("risk"), "test": e.get("test_ref")})
        if st == "failed":
            target = hard if e.get("risk") == "high" else soft
            target.append(f"entailment {eid} failed (risk {e.get('risk')})")
            reason_items.append(
                {
                    "kind": "entailment",
                    "id": eid,
                    "state": st,
                    "risk": e.get("risk"),
                    "bucket": "hard" if e.get("risk") == "high" else "soft",
                }
            )
        elif st == "passed":
            backed, detail = _backing(case, e.get("test_ref"))
            if not backed:
                unbacked.append(f"entailment {eid}: {detail}")
                pending.append(f"entailment {eid} claims passed but {detail}")
                reason_items.append(
                    {"kind": "entailment", "id": eid, "state": st, "bucket": "pending", "detail": _detail_code(detail)}
                )
        else:
            pending.append(f"entailment {eid} is {st}")
            reason_items.append({"kind": "entailment", "id": eid, "state": st, "bucket": "pending"})

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
        effective = effective_status(rec) if rec else {"status": None, "source": "declared", "declared": None}
        item = {
            "id": ref,
            "power": rec.get("discriminating_power"),
            "status": effective["status"],
            "name": rec.get("name", ""),
            "source": effective["source"],
        }
        if effective["source"] == "computed":
            item["computed"] = effective["status"]
            if effective.get("declared") != effective["status"]:
                item["declared"] = effective.get("declared")
        gating_tests.append(item)

    any_run = any(t["status"] in ("passed", "failed") for t in gating_tests)
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

    flags = []
    for test in case.tests.get("records", []):
        tid = test.get("id")
        effective = effective_status(test)
        if effective["source"] == "computed":
            declared = effective.get("declared")
            if declared is not None and declared != effective["status"]:
                flags.append(
                    f"test {tid} declares {declared} but its recorded result computes {effective['status']}; the computed status is used"
                )
            if effective["status"] == "inconclusive":
                flags.append(
                    f"test {tid} records a result but its pass rule is inconclusive ({effective.get('reason', 'no reason')})"
                )
        elif test.get("result") is not None and test.get("pass_rule") is None:
            flags.append(f"test {tid} records a result but has no pass_rule; its status is still declared")
    weak = [t for t in gating_tests if t["power"] in (None, "none", "low")]
    if verdict == "SUPPORTED" and weak:
        flags.append(
            "support rests on tests with no or low discriminating power: "
            + ", ".join(t["id"] for t in weak)
        )
    if verdict in ("SUPPORTED", "UNDETERMINED") and not gating_tests:
        flags.append("no test gates the verdict; the verdict is unaccounted for")
    for p in case.argument.get("premises", []):
        if p.get("kind") != "derived":
            continue
        pid = p.get("id")
        ref = str(p.get("argument_ref") or "")
        if not chain_map:
            flags.append(
                f"derived premise {pid} links another argument; chained arguments are not evaluated"
            )
            continue
        entry = chain_map.get(ref) if isinstance(chain_map, dict) else None
        if not isinstance(entry, dict):
            flags.append(
                f"derived premise {pid} refers to {ref!r}, which is not resolved in the workspace"
            )
        elif entry.get("status") == "unresolved":
            flags.append(
                f"derived premise {pid} refers to {ref!r}, which is not resolved in the workspace"
            )
        elif entry.get("status") == "cycle":
            flags.append(f"derived premise {pid} is part of an argument chain cycle")
        elif entry.get("status") == "error":
            flags.append(
                f"derived premise {pid} refers to a broken argument: {entry.get('reason', '')}"
            )
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
        "reason_items": reason_items,
        "premises": premises,
        "cps": cps,
        "defeaters": defeaters,
        "entailments": entailments,
        "gating_tests": gating_tests,
        "flags": flags,
        "unbacked": unbacked,
        "tests_run": any_run,
        "test_status": test_status_summary(case.tests.get("records", [])),
        "chain": chain_map or {},
    }
