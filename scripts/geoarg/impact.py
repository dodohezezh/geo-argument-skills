"""Decision value: what would change the verdict, and what is redundant.

``impact`` is deliberately a corollary engine, not a probability engine. It
recomputes the same deterministic judge with one assumption changed, so every
number it prints is traceable to a rule and to the contract. It never scores
data quality and never estimates how likely a claim is: it answers "if this
were true or known, would the verdict move, and by how much".

Three questions are supported:

* ablation: leave one evidence record or one test out and see whether the
  verdict or its reason lists move (decisive / backing / redundant / unused);
* what-if: apply explicit assumptions (a test outcome, an evidence status, a
  declared state) and report the verdict delta;
* prospective evidence: append not-yet-collected evidence records and see which
  committed claims they would affect.

A workspace run applies the same prospective evidence to every case in a
workspace, which shows which hypotheses a planned measurement would touch.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from .chain import scan_cases
from .contract import Case, ContractError, load_case, referenced_counter_evidence
from .independence import report as independence_report
from .judge import judge

VERDICT_RANK = {"DEFEATED": 0, "SUSPENDED": 1, "UNTESTED": 2, "UNDETERMINED": 3, "SUPPORTED": 4}

_ASSUME_KINDS = ("test", "evidence", "premise", "cp", "defeater", "entailment")

_LABELS = {
    "en": {
        "title": "# Decision value",
        "case": "Case",
        "claim": "Claim",
        "rule": "Rule version",
        "verdict": "Verdict",
        "value": "Value of the change",
        "none": "no assumption or prospective evidence given",
        "decisive": "decisive (the verdict moves)",
        "backing": "backing (the verdict stays, the reasons move)",
        "redundant": "redundant (nothing moves)",
        "no-change": "no change",
        "remaining": "What still stands between this contract and SUPPORTED",
        "hard": "hard blockers",
        "soft": "soft blockers",
        "pending": "pending questions",
        "unbacked": "unbacked states",
        "gating": "gating tests not yet run",
        "none-blockers": "no blockers recorded",
        "independence": "Independence",
        "n-eff": "effective evidence count",
        "records": "records",
        "delta": "delta",
        "ablation-evidence": "Leave-one-out: evidence",
        "ablation-tests": "Leave-one-out: tests",
        "column-id": "id",
        "column-class": "class",
        "column-verdict": "verdict without it",
        "prospective": "Prospective evidence",
        "workspace": "Workspace discriminating potential",
        "changed": "cases affected",
        "limits": "Limits",
        "limit-1": "no probability is estimated and no claim is scored for plausibility",
        "limit-2": "the declared states are taken as interpreted judgments, not checked against data",
        "limit-3": "ablation changes one record at a time; interactions between records are not measured",
        "assumptions": "Assumptions",
    },
    "zh": {
        "title": "# 决策价值",
        "case": "案例",
        "claim": "主张",
        "rule": "规则版本",
        "verdict": "结论",
        "value": "这次变化的价值",
        "none": "还没有给假设或待采证据",
        "decisive": "决定性（结论会变）",
        "backing": "支撑性（结论不变，理由会变）",
        "redundant": "冗余（什么也没变）",
        "no-change": "没有变化",
        "remaining": "离成立还差什么",
        "hard": "足以推翻的问题",
        "soft": "会削弱结论的问题",
        "pending": "还没有结果的问题",
        "unbacked": "没有测试支撑的状态",
        "gating": "尚未运行的关键测试",
        "none-blockers": "没有记录在案的阻塞",
        "independence": "独立性",
        "n-eff": "有效证据数",
        "records": "条记录",
        "delta": "变化量",
        "ablation-evidence": "留一法：证据",
        "ablation-tests": "留一法：测试",
        "column-id": "id",
        "column-class": "类别",
        "column-verdict": "拿掉后的结论",
        "prospective": "待采证据",
        "workspace": "工作区区分能力",
        "changed": "受影响的案例",
        "limits": "限制",
        "limit-1": "不估计概率，也不给主张的可信度打分",
        "limit-2": "声明的状态被当作解读后的判断，不核查数据本身",
        "limit-3": "留一法一次只动一条记录，不衡量记录之间的相互作用",
        "assumptions": "假设",
    },
}


def _pick(lang: str) -> dict[str, str]:
    return _LABELS["zh"] if str(lang).lower().startswith("zh") else _LABELS["en"]


def _as_case(case_or_root: Case | str | Path) -> Case:
    if isinstance(case_or_root, Case):
        return case_or_root
    return load_case(case_or_root)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": result["verdict"],
        "hard": list(result["reasons"]["hard"]),
        "soft": list(result["reasons"]["soft"]),
        "pending": list(result["reasons"]["pending"]),
        "unbacked": list(result["unbacked"]),
        "flags": list(result["flags"]),
    }


def _classify(before: dict[str, Any], after: dict[str, Any]) -> tuple[str, int]:
    """Return (class, verdict rank delta). Positive delta means improvement."""
    if before["verdict"] != after["verdict"]:
        delta = VERDICT_RANK[after["verdict"]] - VERDICT_RANK[before["verdict"]]
        return "decisive", delta
    for bucket in ("hard", "soft", "pending", "unbacked", "flags"):
        if sorted(before[bucket]) != sorted(after[bucket]):
            return "backing", 0
    return "redundant", 0


def _test_outcome(case: Case, test_id: str, status: str) -> None:
    for record in case.tests.get("records", []):
        if record.get("id") == test_id:
            record["status"] = status
            record.pop("result", None)
            record.pop("pass_rule", None)
            return
    raise ContractError(f"unknown test id: {test_id!r}")


def _evidence_status(case: Case, evidence_id: str, status: str) -> None:
    for record in case.evidence.get("records", []):
        if record.get("id") == evidence_id:
            record["status"] = status
            return
    raise ContractError(f"unknown evidence id: {evidence_id!r}")


def _without_evidence(case: Case, evidence_id: str) -> Case:
    clone = copy.deepcopy(case)
    clone.evidence["records"] = [r for r in clone.evidence.get("records", []) if r.get("id") != evidence_id]
    return clone


def _without_test(case: Case, test_id: str) -> Case:
    clone = copy.deepcopy(case)
    clone.tests["records"] = [r for r in clone.tests.get("records", []) if r.get("id") != test_id]
    return clone


def _state_rules(case: Case) -> dict[str, list[dict[str, Any]]]:
    inference = case.argument.get("inference") or {}
    return {
        "cp": inference.get("cp") or [],
        "defeater": inference.get("defeaters") or [],
        "entailment": case.argument.get("entailments") or [],
        "premise": case.argument.get("premises") or [],
    }


def _assume(case: Case, assumptions: list[str]) -> tuple[Case, dict[tuple[str, str], str], list[str]]:
    """Apply ``kind:id=value`` assumptions to a copy of the case.

    Test and evidence assumptions are written into the case; declared-state
    assumptions are judge overrides. Returns (case copy, overrides, used list).
    """
    clone = copy.deepcopy(case)
    overrides: dict[tuple[str, str], str] = {}
    used: list[str] = []
    for item in assumptions:
        spec = str(item).strip()
        if not spec:
            continue
        if "=" not in spec or ":" not in spec.split("=", 1)[0]:
            raise ContractError(f"assumption must look like kind:id=value, got {item!r}")
        kind_id, value = spec.split("=", 1)
        kind, ident = kind_id.split(":", 1)
        kind = kind.strip()
        ident = ident.strip()
        value = value.strip()
        if kind not in _ASSUME_KINDS:
            raise ContractError(f"unknown assumption kind {kind!r}; use one of {', '.join(_ASSUME_KINDS)}")
        if kind == "test":
            _test_outcome(clone, ident, value)
        elif kind == "evidence":
            _evidence_status(clone, ident, value)
        else:
            overrides[(kind, ident)] = value
        used.append(spec)
    return clone, overrides, used


def _independence(case: Case) -> dict[str, Any]:
    payload = independence_report(case)
    return {"n_eff": payload.get("n_eff"), "n_records": payload.get("n_records"), "warnings": payload.get("warnings", [])}


def _state_supports(test_id: str, case: Case) -> bool:
    """True when some condition that claims a state is backed by this test."""
    for kind, rows in _state_rules(case).items():
        for row in rows:
            if row.get("test_ref") != test_id:
                continue
            if kind == "cp" and row.get("state") == "holds":
                return True
            if kind == "defeater" and row.get("state") == "refuted":
                return True
            if kind == "entailment" and row.get("status") == "passed":
                return True
    return False


def ablation(case: Case) -> dict[str, list[dict[str, Any]]]:
    base = _summary(judge(case))

    counter_ids = set(referenced_counter_evidence(case))
    referenced = {
        ref
        for premise in case.argument.get("premises", [])
        for ref in premise.get("evidence_refs") or []
    } | counter_ids
    evidence_rows: list[dict[str, Any]] = []
    for record in case.evidence.get("records", []):
        evidence_id = record.get("id")
        if evidence_id is None:
            continue
        after = _summary(judge(_without_evidence(case, evidence_id)))
        klass, delta = _classify(base, after)
        if klass == "redundant" and evidence_id not in referenced:
            klass = "unused"
        evidence_rows.append(
            {
                "id": evidence_id,
                "class": klass,
                "delta": delta,
                "referenced": evidence_id in referenced,
                "counter": evidence_id in counter_ids,
                "verdict_without": after["verdict"],
            }
        )
    test_rows: list[dict[str, Any]] = []
    for record in case.tests.get("records", []):
        test_id = record.get("id")
        if test_id is None:
            continue
        after = _summary(judge(_without_test(case, test_id)))
        klass, delta = _classify(base, after)
        if klass == "redundant":
            klass = "backing" if _state_supports(test_id, case) else "untapped"
        test_rows.append(
            {
                "id": test_id,
                "class": klass,
                "delta": delta,
                "verdict_without": after["verdict"],
            }
        )
    return {"evidence": evidence_rows, "tests": test_rows}


def _remaining(result: dict[str, Any], case: Case) -> dict[str, Any]:
    gating: list[str] = []
    for record in case.tests.get("records", []):
        if record.get("status") not in (None, "passed", "failed"):
            gating.append(str(record.get("id")))
    return {
        "hard": list(result["reasons"]["hard"]),
        "soft": list(result["reasons"]["soft"]),
        "pending": list(result["reasons"]["pending"]),
        "unbacked": list(result["unbacked"]),
        "gating": gating,
    }


def load_evidence_file(path: str | Path) -> list[dict[str, Any]]:
    """Load prospective evidence from YAML: a record list or ``{records: [...]}``."""
    source = Path(path)
    if not source.exists():
        raise ContractError(f"evidence file not found: {source}")
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContractError(f"cannot read evidence file {source}: {exc}") from exc
    if isinstance(payload, dict):
        records = payload.get("records")
    elif isinstance(payload, list):
        records = payload
    else:
        records = None
    if not isinstance(records, list) or not records:
        raise ContractError(f"evidence file {source} must hold a non-empty record list")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ContractError(f"evidence file {source}: every record must be a mapping")
        evidence_id = record.get("id")
        if not isinstance(evidence_id, str) or not evidence_id:
            raise ContractError(f"evidence file {source}: every record needs a non-empty id")
        if evidence_id in seen:
            raise ContractError(f"evidence file {source}: duplicate id {evidence_id!r}")
        if "statement" not in record or not str(record.get("statement") or "").strip():
            raise ContractError(f"evidence file {source}: record {evidence_id!r} needs a statement")
        record.setdefault("kind", "observation")
        record.setdefault("layer", "L1")
        record.setdefault("status", "undetermined")
        seen.add(evidence_id)
        out.append(record)
    return out


def _with_evidence(case: Case, records: list[dict[str, Any]]) -> Case:
    clone = copy.deepcopy(case)
    clone.evidence.setdefault("records", [])
    clone.evidence["records"].extend(copy.deepcopy(records))
    return clone


def impact_report(
    case_or_root: Case | str | Path,
    assumptions: list[str] | None = None,
    add_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute the decision value of assumptions and prospective evidence."""
    case = _as_case(case_or_root)
    base_result = judge(case)
    base = _summary(base_result)
    before_independence = _independence(case)

    working = case
    used_assumptions: list[str] = []
    if add_evidence:
        working = _with_evidence(working, add_evidence)
    if assumptions:
        working, overrides, used_assumptions = _assume(working, assumptions)
        after_result = judge(working, overrides)
    elif add_evidence:
        after_result = judge(working)
    else:
        after_result = base_result

    after = _summary(after_result)
    klass, delta = _classify(base, after) if (add_evidence or used_assumptions) else ("none", 0)
    after_independence = _independence(working)
    n_before = before_independence.get("n_eff")
    n_after = after_independence.get("n_eff")
    n_delta = None
    if isinstance(n_before, (int, float)) and isinstance(n_after, (int, float)):
        n_delta = round(float(n_after) - float(n_before), 4)

    return {
        "case": str(case.root),
        "claim_id": str((case.claim or {}).get("id", "")),
        "rule_version": str(base_result.get("rule_version", "")),
        "before": {
            "verdict": base["verdict"],
            "hard": base["hard"],
            "soft": base["soft"],
            "pending": base["pending"],
        },
        "after": {
            "verdict": after["verdict"],
            "hard": after["hard"],
            "soft": after["soft"],
            "pending": after["pending"],
        },
        "value": {"class": klass, "verdict_delta": delta, "assumptions": used_assumptions},
        "prospective_evidence": [str(record.get("id")) for record in (add_evidence or [])],
        "remaining": _remaining(after_result, working),
        "independence": {"before": before_independence, "after": after_independence, "n_eff_delta": n_delta},
        "counter_evidence": sorted(set(referenced_counter_evidence(case))),
        "ablation": ablation(case),
        "limits": [
            "no probability is estimated and no claim is scored for plausibility",
            "declared states are interpreted judgments, not checks on the underlying data",
            "ablation changes one record at a time; interactions are not measured",
        ],
    }


def workspace_impact(root: str | Path, add_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply prospective evidence to every case in a workspace and report moves."""
    rows: list[dict[str, Any]] = []
    changed = 0
    for case_root in scan_cases(Path(root)):
        case = load_case(case_root)
        before = judge(case)["verdict"]
        with_new = _with_evidence(case, add_evidence)
        after = judge(with_new)["verdict"]
        if before != after:
            changed += 1
        rows.append(
            {
                "case": str(case_root),
                "claim_id": str((case.claim or {}).get("id", "")),
                "verdict_before": before,
                "verdict_after": after,
                "changed": before != after,
            }
        )
    rows.sort(key=lambda row: row["case"])
    return {
        "root": str(Path(root)),
        "evidence": [str(record.get("id")) for record in add_evidence],
        "rows": rows,
        "changed": changed,
        "conclusion": (
            "the same evidence moves more than one case"
            if changed > 1
            else "the evidence moves one case"
            if changed == 1
            else "the evidence does not change any committed verdict"
        ),
    }


def render_impact(payload: dict[str, Any], lang: str = "en") -> str:
    """Render an impact report as Markdown."""
    lab = _pick(lang)
    zh = lab is _LABELS["zh"]
    lines: list[str] = [lab["title"], "", f"{lab['case']}: {payload['case']}", f"{lab['claim']}: {payload['claim_id']}", ""]
    before = payload["before"]
    after = payload["after"]
    value = payload["value"]
    lines.append(f"{lab['verdict']}: {before['verdict']}")
    if value["class"] != "none":
        lines.append(f"{lab['value']}: {lab.get(value['class'], value['class'])}")
    lines.append("")

    if payload["prospective_evidence"]:
        lines.append(f"## {lab['prospective']}")
        for evidence_id in payload["prospective_evidence"]:
            lines.append(f"- {evidence_id}")
        lines.append(f"- {lab['verdict']}: {after['verdict']}")
        lines.append("")

    remaining = payload["remaining"]
    lines.append(f"## {lab['remaining']}")
    any_blocker = False
    for bucket in ("hard", "soft", "pending", "unbacked", "gating"):
        rows = remaining[bucket]
        if not rows:
            continue
        any_blocker = True
        lines.append(f"- {lab[bucket]}: " + "; ".join(str(row) for row in rows))
    if not any_blocker:
        lines.append(lab["none-blockers"])
    lines.append("")

    lines.append(f"## {lab['independence']}")
    lines.append(
        f"- {lab['n-eff']}: {payload['independence']['before'].get('n_eff')} / "
        f"{payload['independence']['before'].get('n_records')} {lab['records']}"
    )
    if payload["independence"]["n_eff_delta"] is not None:
        lines.append(f"- {lab['delta']}: {payload['independence']['n_eff_delta']}")
    lines.append("")

    lines.append(f"## {lab['ablation-evidence']}")
    lines.append(f"| {lab['column-id']} | {lab['column-class']} | {lab['column-verdict']} |")
    lines.append("| --- | --- | --- |")
    for row in payload["ablation"]["evidence"]:
        lines.append(f"| {row['id']} | {row['class']} | {row['verdict_without']} |")
    lines.append("")

    lines.append(f"## {lab['ablation-tests']}")
    lines.append(f"| {lab['column-id']} | {lab['column-class']} | {lab['column-verdict']} |")
    lines.append("| --- | --- | --- |")
    for row in payload["ablation"]["tests"]:
        lines.append(f"| {row['id']} | {row['class']} | {row['verdict_without']} |")
    lines.append("")

    if value.get("assumptions"):
        lines.append(f"## {lab['assumptions']}")
        for assumption in value["assumptions"]:
            lines.append(f"- `{assumption}`")
        lines.append("")

    lines.append(f"## {lab['limits']}")
    for limit in payload["limits"]:
        lines.append(f"- {limit}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_workspace_impact(payload: dict[str, Any]) -> str:
    """Render a workspace impact table as Markdown."""
    lines = ["# Workspace discriminating potential", "", f"Root: {payload['root']}", ""]
    lines.append("| case | claim | verdict before | verdict after | changed |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in payload["rows"]:
        lines.append(
            f"| {row['case']} | {row['claim_id']} | {row['verdict_before']} | {row['verdict_after']} | "
            f"{'yes' if row['changed'] else 'no'} |"
        )
    lines.append("")
    lines.append(f"Conclusion: {payload['conclusion']}")
    return "\n".join(lines) + "\n"
