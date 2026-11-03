"""Bind a recorded test result to a passed/failed status.

A status typed into `test.yaml` is a claim; a recorded result plus a pass rule
is checkable. This module evaluates the pass rule deterministically, so the
verdict is computed from the recorded numbers instead of from the author's
memory of them.

The pass rule is deliberately small and closed. It is not a statistics
engine: it covers the common cases where a paper states a value, a threshold,
or a confidence interval. Anything more elaborate belongs in the test's
`method.implementation` and in the human review of the recorded result.

Shapes::

    result:
      value: 1.98
      uncertainty: {kind: ci95, low: 1.8, high: 2.15}
      n: 8
      data_ref: doi:10.1000/example
      preregistration: {id: osf-xxxx, hash: <sha256>}
    pass_rule: {op: ge, value: 2.0}
    pass_rule: {op: le, value: 0.05}
    pass_rule: {op: between, low: 1.9, high: 2.1}
    pass_rule: {op: within_ci, target: 2.0}
    pass_rule: {op: ratio, target: 2.0, tolerance: 0.1}
"""

from __future__ import annotations

from typing import Any

PASS_RULE_OPS = ("ge", "le", "between", "within_ci", "ratio")

COMPUTED_STATUSES = ("passed", "failed", "inconclusive")


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def result_block(test: dict[str, Any]) -> dict[str, Any] | None:
    result = test.get("result")
    return result if isinstance(result, dict) else None


def pass_rule(test: dict[str, Any]) -> dict[str, Any] | None:
    rule = test.get("pass_rule")
    return rule if isinstance(rule, dict) else None


def validate_result_block(test: dict[str, Any]) -> list[str]:
    """Structural checks for the optional result/pass_rule pair."""
    where = f"test {test.get('id')}"
    problems: list[str] = []
    result = result_block(test)
    rule = pass_rule(test)
    if test.get("result") is not None and result is None:
        problems.append(f"{where}: result must be a mapping")
    if test.get("pass_rule") is not None and rule is None:
        problems.append(f"{where}: pass_rule must be a mapping")
    if result is None and rule is None:
        return problems
    if result is None:
        problems.append(f"{where}: pass_rule requires a result block")
        return problems
    if not _number(result.get("value")):
        problems.append(f"{where}: result.value must be a number")
    uncertainty = result.get("uncertainty")
    if uncertainty is not None:
        if not isinstance(uncertainty, dict):
            problems.append(f"{where}: result.uncertainty must be a mapping")
        else:
            if not isinstance(uncertainty.get("kind"), str):
                problems.append(f"{where}: result.uncertainty.kind must be a string")
            low, high = uncertainty.get("low"), uncertainty.get("high")
            if low is not None and not _number(low):
                problems.append(f"{where}: result.uncertainty.low must be a number")
            if high is not None and not _number(high):
                problems.append(f"{where}: result.uncertainty.high must be a number")
            if _number(low) and _number(high) and low > high:
                problems.append(f"{where}: result.uncertainty.low must not exceed high")
    if rule is None:
        return problems
    op = rule.get("op")
    if op not in PASS_RULE_OPS:
        problems.append(f"{where}: pass_rule.op must be one of {list(PASS_RULE_OPS)}")
        return problems
    if op in ("ge", "le"):
        if not _number(rule.get("value")):
            problems.append(f"{where}: pass_rule {op} needs a numeric value")
    elif op == "between":
        low, high = rule.get("low"), rule.get("high")
        if not _number(low) or not _number(high):
            problems.append(f"{where}: pass_rule between needs numeric low and high")
        elif low > high:
            problems.append(f"{where}: pass_rule between needs low <= high")
    elif op == "within_ci":
        if not _number(rule.get("target")):
            problems.append(f"{where}: pass_rule within_ci needs a numeric target")
        if not isinstance(uncertainty, dict) or not _number(uncertainty.get("low")) or not _number(
            uncertainty.get("high")
        ):
            problems.append(f"{where}: pass_rule within_ci needs result.uncertainty low and high")
    elif op == "ratio":
        target, tolerance = rule.get("target"), rule.get("tolerance")
        if not _number(target) or target == 0:
            problems.append(f"{where}: pass_rule ratio needs a non-zero numeric target")
        if not _number(tolerance) or tolerance < 0:
            problems.append(f"{where}: pass_rule ratio needs a non-negative numeric tolerance")
    return problems


def compute_status(test: dict[str, Any]) -> dict[str, Any] | None:
    """Return {status, reason} from the recorded result, or None if not computable."""
    result = result_block(test)
    rule = pass_rule(test)
    if result is None or rule is None:
        return None
    value = result.get("value")
    if not _number(value):
        return {"status": "inconclusive", "reason": "result.value is not a number"}
    op = rule.get("op")
    if op == "ge":
        threshold = rule.get("value")
        if not _number(threshold):
            return {"status": "inconclusive", "reason": "pass rule has no numeric value"}
        passed = value >= threshold
        return {"status": "passed" if passed else "failed", "reason": f"{value:g} {'>=' if passed else '<'} {threshold:g}"}
    if op == "le":
        threshold = rule.get("value")
        if not _number(threshold):
            return {"status": "inconclusive", "reason": "pass rule has no numeric value"}
        passed = value <= threshold
        return {"status": "passed" if passed else "failed", "reason": f"{value:g} {'<=' if passed else '>'} {threshold:g}"}
    if op == "between":
        low, high = rule.get("low"), rule.get("high")
        if not _number(low) or not _number(high):
            return {"status": "inconclusive", "reason": "pass rule has no numeric bounds"}
        passed = low <= value <= high
        return {
            "status": "passed" if passed else "failed",
            "reason": f"{value:g} {'in' if passed else 'outside'} [{low:g}, {high:g}]",
        }
    if op == "within_ci":
        target = rule.get("target")
        uncertainty = result.get("uncertainty")
        if not _number(target) or not isinstance(uncertainty, dict):
            return {"status": "inconclusive", "reason": "pass rule lacks a target or interval"}
        low, high = uncertainty.get("low"), uncertainty.get("high")
        if not _number(low) or not _number(high):
            return {"status": "inconclusive", "reason": "result has no low/high interval"}
        passed = low <= target <= high
        return {
            "status": "passed" if passed else "failed",
            "reason": f"interval [{low:g}, {high:g}] {'contains' if passed else 'excludes'} {target:g}",
        }
    if op == "ratio":
        target, tolerance = rule.get("target"), rule.get("tolerance")
        if not _number(target) or target == 0 or not _number(tolerance):
            return {"status": "inconclusive", "reason": "pass rule lacks a usable target or tolerance"}
        deviation = abs(value / target - 1.0)
        passed = deviation <= tolerance
        return {
            "status": "passed" if passed else "failed",
            "reason": f"|{value:g}/{target:g} - 1| = {deviation:.3f} {'<=' if passed else '>'} {tolerance:g}",
        }
    return {"status": "inconclusive", "reason": f"unknown pass rule op {op!r}"}


def effective_status(test: dict[str, Any]) -> dict[str, Any]:
    """Return {status, source, computed_reason, declared}.

    The recorded result wins when it can be evaluated; otherwise the status
    field is used as declared by the author.
    """
    computed = compute_status(test)
    declared = test.get("status")
    if computed is not None:
        return {
            "status": computed["status"],
            "source": "computed",
            "reason": computed.get("reason", ""),
            "declared": declared,
        }
    return {"status": declared, "source": "declared", "reason": "", "declared": declared}


def test_status_summary(tests: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Compact status/source map for every test in test.yaml."""
    summary: dict[str, dict[str, Any]] = {}
    for test in tests:
        tid = test.get("id")
        if not tid:
            continue
        effective = effective_status(test)
        summary[tid] = {"status": effective["status"], "source": effective["source"]}
    return summary
