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

from .contract import CASE_FILES, ContractError, load_case, validate
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
        target_case = load_case(target, attach_chain=False)
        target_chain = _load_chain(target, index, memo, stack + [key])
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
) -> dict[str, Any]:
    case = load_case(root, attach_chain=False)
    chain: dict[str, Any] = {}
    for premise in case.argument.get("premises") or []:
        if not isinstance(premise, dict) or premise.get("kind") != "derived":
            continue
        ref = str(premise.get("argument_ref") or "")
        chain[ref] = _resolve_entry(root, ref, index, memo, stack)
    return chain


def load_chain(root: str | Path) -> dict[str, Any]:
    """Resolve every derived-premise reference reachable from one case."""
    root = Path(root).resolve()
    index = workspace_index(root)
    return _load_chain(root, index, {}, [str(root)])


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


def chain_problems(root: str | Path) -> list[str]:
    """Structural problems in the argument chain of one case."""
    root = Path(root).resolve()
    index = workspace_index(root)
    chain = _load_chain(root, index, {}, [str(root)])
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
    from . import audit

    registry_dir = root / ".geoarg" / "registry"
    if not registry_dir.is_dir():
        return []
    if not any(registry_dir.glob("*.json")):
        return []
    try:
        ok, problems, _record = audit.verify(root)
    except ContractError as exc:  # pragma: no cover - defensive
        return [f"cannot verify committed record: {exc}"]
    return problems


def workspace_report(root: str | Path) -> dict[str, Any]:
    """Scan a workspace: cases, verdicts, chains, evidence reuse and drift."""
    root = Path(root).resolve()
    cases: list[dict[str, Any]] = []
    chains: list[dict[str, Any]] = []
    problems: list[str] = []
    evidence: dict[str, list[dict[str, Any]]] = {}
    argument_ids: dict[str, list[str]] = {}

    roots = scan_cases(root)
    if not roots:
        return {
            "root": str(root),
            "cases": [],
            "chains": [],
            "evidence_shared": [],
            "evidence_conflicts": [],
            "drift": [],
            "problems": ["no case directories with argument.yaml found"],
            "ok": False,
        }

    for case_root in roots:
        label = _rel(case_root, root)
        try:
            case = load_case(case_root)
        except ContractError as exc:
            problems.append(f"{label}: cannot load: {exc}")
            continue
        argument_id = str(case.argument.get("id") or "")
        if argument_id:
            argument_ids.setdefault(argument_id, []).append(label)
        invalid = validate(case)
        verdict = None
        if invalid:
            problems.append(f"{label}: invalid contract: {'; '.join(invalid)}")
        else:
            verdict = judge(case)["verdict"]
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
        for ref, entry in sorted(getattr(case, "chain", {}).items() or {}):
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
        problems.extend(f"{label}: {item}" for item in chain_problems(case_root))
        for record in case.evidence.get("records") or []:
            if not isinstance(record, dict) or not record.get("id"):
                continue
            evidence.setdefault(str(record["id"]), []).append(
                {"case": label, "digest": _evidence_digest(record)}
            )
        problems.extend(f"{label}: {item}" for item in _drift_problems(case_root))

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
        "cases": cases,
        "chains": chains,
        "evidence_shared": evidence_shared,
        "evidence_conflicts": evidence_conflicts,
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
            "drift_none": "没有已提交台账的案例。",
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
        "drift_none": "No case carries a committed record.",
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
    drift = [p for p in problems if "since commit" in p or "ledger" in p or "verdict changed" in p]
    if drift:
        for item in drift:
            lines.append(f"- {item}")
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
