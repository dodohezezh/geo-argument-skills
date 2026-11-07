"""Argument chains and workspaces.

A derived premise may point at another argument. This module resolves such
references, detects cycles, scans a workspace for duplicate argument ids and
for evidence records shared across cases, and reports committed-record drift.
It never reruns experiments: a chain contributes the referenced argument's
computed verdict as the premise's support state.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from .contract import CASE_FILES, Case, ContractError, load_case, validate
from .judge import judge
from . import terms

WORKSPACE_FILE = "workspace.yaml"
WORKSPACE_SCHEMA_VERSION = "geoarg/workspace/0.1"

_PATHY = re.compile(r"[\\/]")
_SKIP_DIRS = {".git", ".geoarg", "build", "dist", "__pycache__", "node_modules"}

_VERDICT_TO_CHAIN_STATE = {
    "SUPPORTED": "chain-supported",
    "SUSPENDED": "chain-disputed",
    "DEFEATED": "chain-unsupported",
    "UNTESTED": "chain-undetermined",
    "UNDETERMINED": "chain-undetermined",
}


# ---------------------------------------------------------------- helpers


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def case_inputs(root: Path) -> dict[str, str]:
    """sha256 of every contract file present in a case directory."""
    root = Path(root)
    out: dict[str, str] = {}
    for name in CASE_FILES:
        path = root / name
        if path.is_file():
            out[name] = _file_sha(path)
    return out


def _rel(path: Path, base: Path) -> str:
    try:
        return Path(os.path.relpath(path, base)).as_posix()
    except ValueError:  # different drives on Windows
        return path.as_posix()


def _case_label(root: Path) -> str:
    try:
        case = load_case(root, attach_chain=False)
        return str(case.argument.get("id") or root.name)
    except ContractError:
        return root.name


def _looks_like_path(ref: str) -> bool:
    return bool(_PATHY.search(ref)) or ref.startswith(".")


# ---------------------------------------------------------------- workspace


def load_workspace(root: str | Path) -> dict[str, Any] | None:
    """Return the nearest workspace document walking up from a case root."""
    current = Path(root).resolve()
    for candidate in (current, *current.parents):
        path = candidate / WORKSPACE_FILE
        if path.is_file():
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                return None
            if not isinstance(data, dict):
                return None
            data.setdefault("_root", str(candidate))
            return data
    return None


def workspace_index(root: str | Path) -> dict[str, Path]:
    """Map argument id -> case directory using the nearest workspace.yaml."""
    data = load_workspace(root)
    if not data:
        return {}
    base = Path(data.get("_root"))
    index: dict[str, Path] = {}
    for entry in data.get("arguments") or []:
        if not isinstance(entry, dict):
            continue
        argument_id = entry.get("id")
        case = entry.get("case")
        if not argument_id or not case:
            continue
        path = Path(case)
        index[str(argument_id)] = path if path.is_absolute() else (base / path)
    return index


def resolve_target(root: Path, ref: str, index: dict[str, Path]) -> Path | None:
    """Resolve an argument_ref to a case directory, or None."""
    if not ref:
        return None
    if ref in index:
        target = index[ref]
        return target if (target / "argument.yaml").is_file() else None
    if _looks_like_path(ref):
        target = Path(ref)
        target = target if target.is_absolute() else (root / target)
        if (target / "argument.yaml").is_file():
            return target.resolve()
        return None
    relative = root / ref
    if (relative / "argument.yaml").is_file():
        return relative.resolve()
    return None


# ---------------------------------------------------------------- chains


def _resolve_entry(
    root: Path,
    ref: str,
    index: dict[str, Path],
    memo: dict[str, dict[str, Any]],
    stack: list[str],
    cases: dict[str, Case] | None = None,
) -> dict[str, Any]:
    target = resolve_target(root, ref, index)
    if target is None:
        return {
            "status": "unresolved",
            "ref": ref,
            "reason": "no workspace entry and no case directory at this path",
        }
    key = str(target.resolve())
    target_name = _rel(target, Path(index_root(root)))
    if key in stack:
        chain = stack[stack.index(key):] + [key]
        names = [Path(item).name for item in chain]
        return {
            "status": "cycle",
            "ref": ref,
            "case": target_name,
            "cycle": names,
        }
    if key in memo:
        cached = memo[key]
        return {
            "status": "resolved",
            "ref": ref,
            "case": cached["case"],
            "argument_id": cached["argument_id"],
            "claim_id": cached["claim_id"],
            "verdict": cached["verdict"],
            "input_sha256": cached["input_sha256"],
            "chain_sha256": cached["chain_sha256"],
        }
    try:
        if cases is not None and key not in cases:
            cases[key] = load_case(target, attach_chain=False)
        target_case = cases[key] if cases is not None else load_case(target, attach_chain=False)
        target_chain = _load_chain(target, index, memo, stack + [key], cases)
        target_verdict = judge(target_case, chain=target_chain)["verdict"]
    except ContractError as exc:
        return {
            "status": "error",
            "ref": ref,
            "case": target_name,
            "reason": str(exc),
        }
    nested = [
        item
        for item in target_chain.values()
        if isinstance(item, dict) and item.get("status") in ("cycle", "unresolved", "error")
    ]
    if nested:
        first = nested[0]
        if first.get("status") == "cycle":
            return {
                "status": "cycle",
                "ref": ref,
                "case": target_name,
                "cycle": first.get("cycle") or [],
            }
        return {
            "status": "error",
            "ref": ref,
            "case": target_name,
            "reason": (
                "the referenced argument has an "
                f"{first.get('status')} premise reference: {first.get('ref')!r}"
            ),
        }
    cached = {
        "case": target_name,
        "argument_id": str(target_case.argument.get("id") or target.name),
        "claim_id": str((target_case.argument.get("claim") or {}).get("id") or ""),
        "verdict": target_verdict,
        "input_sha256": case_inputs(target),
        "chain_sha256": chain_digest_from(target_chain),
    }
    memo[key] = cached
    entry = {"status": "resolved", "ref": ref, **cached}
    return entry


def index_root(root: str | Path) -> Path:
    data = load_workspace(root)
    if data:
        return Path(data.get("_root"))
    return Path(root).resolve()


def _load_chain(
    root: Path,
    index: dict[str, Path],
    memo: dict[str, dict[str, Any]],
    stack: list[str],
    cases: dict[str, Case] | None = None,
) -> dict[str, Any]:
    key = str(root.resolve())
    case = cases.get(key) if cases is not None else None
    if case is None:
        case = load_case(root, attach_chain=False)
        if cases is not None:
            cases[key] = case
    chain: dict[str, Any] = {}
    for premise in case.argument.get("premises") or []:
        if not isinstance(premise, dict) or premise.get("kind") != "derived":
            continue
        ref = str(premise.get("argument_ref") or "")
        chain[ref] = _resolve_entry(root, ref, index, memo, stack, cases)
    return chain


def load_chain(root: str | Path, cases: dict[str, Case] | None = None) -> dict[str, Any]:
    """Resolve every derived-premise reference reachable from one case."""
    root = Path(root).resolve()
    index = workspace_index(root)
    return _load_chain(root, index, {}, [str(root)], cases)


def chain_digest_from(chain: dict[str, Any]) -> str:
    return _sha_text(_canonical(chain))


def chain_digest(root: str | Path) -> str:
    return chain_digest_from(load_chain(root))


def chain_summary(root: str | Path) -> dict[str, Any]:
    """Compact chain description for the registry record."""
    chain = load_chain(root)
    entries = []
    for ref, entry in sorted(chain.items()):
        row = {"ref": ref, "status": entry.get("status")}
        for key in ("case", "argument_id", "claim_id", "verdict", "reason", "cycle"):
            if entry.get(key) is not None:
                row[key] = entry[key]
        entries.append(row)
    return {"sha256": chain_digest_from(chain), "entries": entries}


def _chain_problems_from(chain: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for ref, entry in sorted(chain.items()):
        status = entry.get("status")
        if status == "resolved":
            continue
        if status == "unresolved":
            problems.append(
                f"argument chain: premise reference {ref!r} cannot be resolved "
                "(add it to the nearest workspace.yaml or use a case path)"
            )
        elif status == "cycle":
            names = " -> ".join(entry.get("cycle") or [])
            problems.append(f"argument chain cycle: {names}")
        elif status == "error":
            problems.append(
                f"argument chain: premise reference {ref!r} points at a broken case: {entry.get('reason')}"
            )
    return problems


def chain_problems(root: str | Path, cases: dict[str, Case] | None = None) -> list[str]:
    """Structural problems in the argument chain of one case."""
    root = Path(root).resolve()
    index = workspace_index(root)
    return _chain_problems_from(_load_chain(root, index, {}, [str(root)], cases))


# ---------------------------------------------------------------- workspace scan


def scan_cases(root: str | Path) -> list[Path]:
    """Find every case directory (a directory with argument.yaml) under root."""
    root = Path(root).resolve()
    if (root / "argument.yaml").is_file():
        return [root]
    found: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS and not d.startswith("."))
        if "argument.yaml" in filenames:
            found.append(Path(current))
            dirnames[:] = []
    return found


def _evidence_digest(record: dict[str, Any]) -> str:
    return _sha_text(_canonical(record))


def _drift_problems(root: Path) -> list[str]:
    return _drift_info(root)["problems"]


def _drift_info(root: Path) -> dict[str, Any]:
    """Verify one case's committed record when the case has one."""
    from . import audit

    registry_dir = root / ".geoarg" / "registry"
    if not registry_dir.is_dir() or not any(registry_dir.glob("*.json")):
        return {"committed": False, "ok": True, "problems": []}
    try:
        ok, problems, record = audit.verify(root)
    except ContractError as exc:  # pragma: no cover - defensive
        return {"committed": True, "ok": False, "problems": [f"cannot verify committed record: {exc}"]}
    return {
        "committed": True,
        "ok": bool(ok),
        "problems": list(problems),
        "verdict": (record or {}).get("verdict"),
    }


def workspace_report(root: str | Path, *, judge_cases: bool = True) -> dict[str, Any]:
    """Scan a workspace: cases, verdicts, chains, evidence reuse and drift.

    ``judge_cases=False`` is the fast mode: contracts are loaded and validated,
    but no case is judged, no chain is resolved and committed-record drift is
    skipped.
    """
    root = Path(root).resolve()
    cases: list[dict[str, Any]] = []
    chains: list[dict[str, Any]] = []
    problems: list[str] = []
    drift: list[dict[str, Any]] = []
    evidence: dict[str, list[dict[str, Any]]] = {}
    argument_ids: dict[str, list[str]] = {}
    mode = "full" if judge_cases else "fast"

    roots = scan_cases(root)
    if not roots:
        return {
            "root": str(root),
            "mode": mode,
            "cases": [],
            "chains": [],
            "evidence_shared": [],
            "evidence_conflicts": [],
            "drift": [],
            "cycles": [],
            "problems": ["no case directories with argument.yaml found"],
            "ok": False,
        }

    loaded: dict[str, Case] = {}
    for case_root in roots:
        label = _rel(case_root, root)
        key = str(case_root.resolve())
        try:
            case = load_case(case_root, attach_chain=False)
        except ContractError as exc:
            problems.append(f"{label}: cannot load: {exc}")
            continue
        loaded[key] = case
        argument_id = str(case.argument.get("id") or "")
        if argument_id:
            argument_ids.setdefault(argument_id, []).append(label)
        invalid = validate(case)
        verdict = None
        chain: dict[str, Any] = {}
        if invalid:
            problems.append(f"{label}: invalid contract: {'; '.join(invalid)}")
        elif judge_cases:
            try:
                case_index = workspace_index(case_root)
                chain = _load_chain(Path(key), case_index, {}, [key], loaded)
                verdict = judge(case, chain=chain)["verdict"]
            except ContractError as exc:
                problems.append(f"{label}: cannot judge: {exc}")
        cases.append(
            {
                "case": label,
                "argument_id": argument_id,
                "claim_id": str((case.argument.get("claim") or {}).get("id") or ""),
                "title": str((case.argument.get("claim") or {}).get("statement") or ""),
                "domain": str((case.argument.get("domain") or "")),
                "verdict": verdict,
            }
        )
        for ref, entry in sorted(chain.items()):
            chains.append(
                {
                    "argument_id": argument_id,
                    "premise_ref": ref,
                    "status": entry.get("status"),
                    "target": entry.get("case"),
                    "target_argument": entry.get("argument_id"),
                    "target_verdict": entry.get("verdict"),
                }
            )
        problems.extend(f"{label}: {item}" for item in _chain_problems_from(chain))
        for record in case.evidence.get("records") or []:
            if not isinstance(record, dict) or not record.get("id"):
                continue
            evidence.setdefault(str(record["id"]), []).append(
                {"case": label, "digest": _evidence_digest(record)}
            )
        if judge_cases:
            info = _drift_info(case_root)
            if info.get("committed"):
                drift.append(
                    {
                        "case": label,
                        "ok": bool(info.get("ok")),
                        "verdict": info.get("verdict"),
                        "problems": list(info.get("problems") or []),
                    }
                )
                problems.extend(f"{label}: {item}" for item in info.get("problems") or [])
        else:
            registry_dir = case_root / ".geoarg" / "registry"
            if registry_dir.is_dir() and any(registry_dir.glob("*.json")):
                drift.append(
                    {
                        "case": label,
                        "ok": None,
                        "verdict": None,
                        "problems": [],
                        "skipped": True,
                    }
                )

    if load_workspace(root):
        for argument_id, labels in sorted(argument_ids.items()):
            if len(labels) > 1:
                problems.append(
                    f"duplicate argument id {argument_id!r}: {', '.join(sorted(labels))}"
                )

    evidence_shared: list[dict[str, Any]] = []
    evidence_conflicts: list[dict[str, Any]] = []
    for record_id, uses in sorted(evidence.items()):
        case_names = sorted({use["case"] for use in uses})
        digests = {use["digest"] for use in uses}
        if len(digests) > 1:
            evidence_conflicts.append(
                {"evidence_id": record_id, "cases": case_names}
            )
            problems.append(
                f"evidence id {record_id!r} is reused with different content in: {', '.join(case_names)}"
            )
        elif len(case_names) > 1:
            evidence_shared.append({"evidence_id": record_id, "cases": case_names})

    cycles = [problem for problem in problems if problem.startswith("argument chain cycle:")]
    return {
        "root": str(root),
        "mode": mode,
        "cases": cases,
        "chains": chains,
        "evidence_shared": evidence_shared,
        "evidence_conflicts": evidence_conflicts,
        "drift": drift,
        "cycles": sorted(set(cycles)),
        "problems": problems,
        "ok": not problems,
    }


# ---------------------------------------------------------------- render


def _labels(lang: str) -> dict[str, str]:
    if lang == "zh":
        return {
            "title": "GeoArg 工作区：{root}",
            "intro": "工作区里有 {count} 条论证。下面列出判决、论证链、跨案例共用的证据，以及台账漂移。",
            "cases_heading": "论证",
            "argument": "论证",
            "claim": "主张",
            "verdict": "结论",
            "case": "目录",
            "chains_heading": "论证链",
            "chains_none": "没有跨论证的引用。",
            "premise": "前提",
            "target": "引用论证",
            "target_verdict": "被引用论证的结论",
            "shared_heading": "跨案例共用的证据",
            "shared_none": "没有跨案例复用的证据 id。",
            "evidence": "证据",
            "cases": "出现在",
            "conflicts_heading": "证据冲突",
            "conflicts_none": "没有发现同一证据 id 在不同论证里内容不一致。",
            "drift_heading": "台账漂移",
            "drift_none": "没有已提交的案例；工作区只做结构检查。",
            "drift_none_problems": "无",
            "drift_state": "状态",
            "drift_ok": "通过",
            "drift_bad": "不一致",
            "drift_skipped": "已跳过",
            "problems_heading": "问题",
            "problems_none": "没有发现问题。",
            "ok": "工作区结论：结构一致。",
            "not_ok": "工作区结论：有 {count} 个问题需要处理。",
        }
    return {
        "title": "GeoArg workspace: {root}",
        "intro": "This workspace holds {count} argument(s). Below: verdicts, argument chains, evidence shared across cases, and committed-record drift.",
        "cases_heading": "Arguments",
        "argument": "Argument",
        "claim": "Claim",
        "verdict": "Conclusion",
        "case": "Directory",
        "chains_heading": "Argument chains",
        "chains_none": "No cross-argument references.",
        "premise": "Premise",
        "target": "Referenced argument",
        "target_verdict": "Referenced conclusion",
        "shared_heading": "Evidence shared across cases",
        "shared_none": "No evidence id is reused across cases.",
        "evidence": "Evidence",
        "cases": "Seen in",
        "conflicts_heading": "Evidence conflicts",
        "conflicts_none": "No evidence id is reused with different content.",
        "drift_heading": "Committed-record drift",
        "drift_none": "No committed cases; the workspace only ran structural checks.",
        "drift_none_problems": "none",
        "drift_state": "State",
        "drift_ok": "OK",
        "drift_bad": "MISMATCH",
        "drift_skipped": "skipped",
        "problems_heading": "Problems",
        "problems_none": "No problems found.",
        "ok": "Workspace conclusion: structurally consistent.",
        "not_ok": "Workspace conclusion: {count} problem(s) need attention.",
    }


def render_workspace(report: dict[str, Any], lang: str = "en") -> str:
    labels = _labels(lang)
    problems = report.get("problems") or []
    lines = [f"# {labels['title'].format(root=report.get('root', ''))}", ""]
    lines.append(labels["intro"].format(count=len(report.get("cases") or [])))
    lines.append("")
    if report.get("mode") == "fast":
        lines.append(
            "Fast mode (--no-judge): verdicts, argument chains and committed-record "
            "drift checks were skipped."
            if lang != "zh"
            else "快速模式（--no-judge）：已跳过判决、论证链和台账漂移检查。"
        )
        lines.append("")
    lines.append(f"## {labels['cases_heading']}")
    lines.append("")
    if report.get("cases"):
        lines.append(f"| {labels['argument']} | {labels['claim']} | {labels['verdict']} | {labels['case']} |")
        lines.append("|---|---|---|---|")
        for row in report["cases"]:
            verdict = (
                terms.status_label(row["verdict"], lang) if row.get("verdict") else "-"
            )
            lines.append(
                f"| {row.get('argument_id') or '-'} | {row.get('title') or row.get('claim_id') or '-'} | {verdict} | {row.get('case')} |"
            )
    else:
        lines.append("-")
    lines.append("")
    lines.append(f"## {labels['chains_heading']}")
    lines.append("")
    if report.get("chains"):
        lines.append(f"| {labels['premise']} | {labels['target']} | {labels['target_verdict']} |")
        lines.append("|---|---|---|")
        for row in report["chains"]:
            target = row.get("target") or row.get("premise_ref") or "-"
            target_verdict = (
                terms.status_label(row["target_verdict"], lang)
                if row.get("target_verdict")
                else "-"
            )
            lines.append(f"| {row.get('premise_ref')} | {target} | {target_verdict} |")
    else:
        lines.append(labels["chains_none"])
    lines.append("")
    lines.append(f"## {labels['shared_heading']}")
    lines.append("")
    if report.get("evidence_shared"):
        lines.append(f"| {labels['evidence']} | {labels['cases']} |")
        lines.append("|---|---|")
        for row in report["evidence_shared"]:
            lines.append(f"| {row['evidence_id']} | {', '.join(row['cases'])} |")
    else:
        lines.append(labels["shared_none"])
    lines.append("")
    lines.append(f"## {labels['conflicts_heading']}")
    lines.append("")
    if report.get("evidence_conflicts"):
        for row in report["evidence_conflicts"]:
            lines.append(f"- {row['evidence_id']}: {', '.join(row['cases'])}")
    else:
        lines.append(labels["conflicts_none"])
    lines.append("")
    lines.append(f"## {labels['drift_heading']}")
    lines.append("")
    drift = report.get("drift") or []
    if drift:
        lines.append(f"| {labels['case']} | {labels['drift_state']} | {labels['problems_heading']} |")
        lines.append("|---|---|---|")
        for row in drift:
            if row.get("skipped"):
                state = labels["drift_skipped"]
            else:
                state = labels["drift_ok"] if row.get("ok") else labels["drift_bad"]
            detail = "; ".join(row.get("problems") or []) or labels["drift_none_problems"]
            lines.append(f"| {row.get('case') or '-'} | {state} | {detail} |")
    else:
        lines.append(labels["drift_none"])
    lines.append("")
    lines.append(f"## {labels['problems_heading']}")
    lines.append("")
    if problems:
        for item in problems:
            lines.append(f"- {item}")
        lines.append("")
        lines.append(labels["not_ok"].format(count=len(problems)))
    else:
        lines.append(labels["problems_none"])
        lines.append("")
        lines.append(labels["ok"])
    return "\n".join(lines)
