"""Hash-chained registry: commit a verdict, anchor it, verify it later.

A verdict that cannot be recomputed from the recorded inputs is an opinion.
`commit` writes a canonical JSON record containing the input digests, the
engine digest, the rule version, and the verdict; `verify` recomputes all of
them and reports every mismatch. `anchor` adds a checkpoint over the current
ledger head that can be stored where the case author cannot rewrite it (a git
commit, a timestamp service, a preprint deposit).

The record is drift evidence, not a signature: re-running `commit` replaces the
record and clears every mismatch. Keep an anchor, or its digest, outside the
case directory when that matters. `attest` binds the rendered deliverables and
the authored judgment paragraph to the committed record; `verify` checks them.

Each ledger entry carries a self-hash (`sha256`) and links to the previous
entry, so an edited, truncated, or re-rooted ledger is reported instead of
silently accepted. A ledger stored next to the case can still be rewritten by
someone who rewrites every hash; only a checkpoint kept outside the case
(`anchor`, `verify --anchor <file>`) can show that the history was rewritten.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contract import CASE_FILES, ContractError, load_case
from .ground import GroundError, ledger_sha256, load_ledger, validate_grounding
from .judge import RULE_VERSION, judge
from .safeio import LockError, atomic_write_text, case_lock

# Wording lives in the renderers, not in this digest: a translation or label
# edit must not invalidate committed audit records. The trust modules are in
# the digest because their behaviour decides whether a record can be trusted.
_ENGINE_FILES = (
    "contract.py",
    "judge.py",
    "results.py",
    "independence.py",
    "hitting.py",
    "ground.py",
    "chain.py",
    "audit.py",
    "attest.py",
    "safeio.py",
    "schemas.py",
    "domains.py",
)
REGISTRY_SCHEMA_VERSION = "geoarg/registry/0.6"
LEDGER_FILE = "ledger.jsonl"
LEDGER_SCHEMA_VERSION = "geoarg/ledger/0.3"
LEDGER_KINDS = ("commit", "anchor", "attestation")
ANCHOR_FILE = "anchor.json"
ANCHOR_SCHEMA_VERSION = "geoarg/anchor/0.1"
ATTESTATION_FILE = "attestation.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# Files whose bytes may legitimately differ between a Windows CRLF working tree
# and a clean LF checkout. Digests of these files are computed over LF bytes so
# a record committed on one machine still verifies on another.
_TEXT_SUFFIXES = {
    ".md", ".txt", ".yaml", ".yml", ".json", ".html", ".htm", ".csv",
    ".py", ".toml", ".cff", ".cfg", ".ini", ".gitignore", ".gitattributes",
}


def _is_text_path(path: Path) -> bool:
    name = path.name.lower()
    return path.suffix.lower() in _TEXT_SUFFIXES or name in {".gitignore", ".gitattributes"}


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    data = path.read_bytes()
    if _is_text_path(Path(path)):
        data = data.replace(b"\r\n", b"\n")
    return _sha256_bytes(data)


def case_digest(root: Path) -> dict[str, str | None]:
    return {name: file_sha256(root / name) for name in CASE_FILES}


def engine_digest() -> str:
    package = Path(__file__).resolve().parent
    parts = []
    for name in _ENGINE_FILES:
        parts.append(file_sha256(package / name) or "")
    return _sha256_bytes("".join(parts).encode("ascii"))


def registry_dir(case_root: Path, override: str | Path | None = None) -> Path:
    return Path(override) if override else case_root / ".geoarg" / "registry"


def _canonical_record(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_sha256(payload: dict[str, Any]) -> str:
    """Stable digest of a JSON-serialisable payload."""
    return _sha256_bytes(_canonical_record(payload).encode("utf-8"))


def record_sha256(record: dict[str, Any]) -> str:
    return canonical_sha256(record)


def _entry_sha256(entry: dict[str, Any]) -> str:
    body = {key: value for key, value in entry.items() if key != "sha256"}
    return canonical_sha256(body)


def _expected_prev(entries: list[dict[str, Any]]) -> str | None:
    if not entries:
        return None
    last = entries[-1]
    return last.get("sha256") or last.get("record_sha256")


def _ledger_path(root: Path) -> Path:
    return root / ".geoarg" / LEDGER_FILE


def _parse_ledger(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"ledger line {number}: unreadable entry ({exc})")
            return entries, problems
        if not isinstance(entry, dict):
            problems.append(f"ledger line {number}: entry is not a mapping")
            return entries, problems
        kind = entry.get("kind", "commit")
        if kind not in LEDGER_KINDS:
            problems.append(f"ledger line {number}: unknown entry kind {kind!r}")
        if entry.get("prev") != _expected_prev(entries):
            problems.append(f"ledger chain broken at line {number}")
        stored = entry.get("sha256")
        if stored is None:
            if entry.get("schema_version") == LEDGER_SCHEMA_VERSION:
                problems.append(f"ledger line {number}: missing entry self-hash")
        elif stored != _entry_sha256(entry):
            problems.append(f"ledger line {number}: entry was edited (self-hash mismatch)")
        if not isinstance(entry.get("record_sha256"), str):
            problems.append(f"ledger line {number}: missing record_sha256")
        entries.append(entry)
    return entries, problems


def _read_ledger(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = _ledger_path(root)
    if not path.is_file():
        return [], []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:  # pragma: no cover - defensive
        return [], [f"ledger unreadable: {exc}"]
    return _parse_ledger(text)


def ledger_entries(root: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Public read of the ledger entries and chain problems."""
    return _read_ledger(Path(root))


def append_ledger(
    root: Path,
    *,
    kind: str,
    claim_id: Any,
    created_at: str,
    record_sha256: str,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Append one canonical ledger entry, refusing a broken chain first.

    The caller is expected to hold the case lock for the whole commit / anchor /
    attest transaction; the new ledger file is written atomically.
    """
    if kind not in LEDGER_KINDS:
        raise ContractError(f"unknown ledger entry kind: {kind}")
    path = _ledger_path(root)
    if path.is_file():
        try:
            existing = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:  # pragma: no cover - defensive
            raise ContractError(f"ledger unreadable: {exc}") from exc
    else:
        existing = ""
    entries, problems = _parse_ledger(existing)
    if problems:
        raise ContractError("; ".join(problems))
    entry: dict[str, Any] = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "kind": kind,
        "claim_id": claim_id,
        "created_at": created_at,
        "record_sha256": record_sha256,
        "prev": _expected_prev(entries),
    }
    for key, value in (extra or {}).items():
        if key not in entry:
            entry[key] = value
    entry["sha256"] = _entry_sha256(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    if existing and not existing.endswith("\n"):
        existing += "\n"
    atomic_write_text(path, existing + line + "\n")
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _records(root: Path, registry: str | Path | None = None) -> tuple[list[dict[str, Any]], list[Path], list[str]]:
    out_dir = registry_dir(root, registry)
    paths = sorted(out_dir.glob("*.json")) if out_dir.is_dir() else []
    records: list[dict[str, Any]] = []
    problems: list[str] = []
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append(f"{path.name}: unreadable record ({exc})")
            continue
        if not isinstance(record, dict):
            problems.append(f"{path.name}: record is not a mapping")
            continue
        records.append(record)
    return records, paths, problems


def committed_record(root: Path, registry: str | Path | None = None) -> tuple[dict[str, Any], Path]:
    """Return the single committed record for a case, or raise."""
    records, paths, problems = _records(root, registry)
    if problems:
        raise ContractError("; ".join(problems))
    if not records:
        raise ContractError(f"no committed record under {registry_dir(root, registry)}")
    if len(records) > 1:
        raise ContractError(
            f"ambiguous registry: {len(records)} committed records under {registry_dir(root, registry)}; "
            "one case carries one claim"
        )
    return records[0], paths[0]


def _latest_commit(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in reversed(entries):
        if entry.get("kind", "commit") == "commit":
            return entry
    return None


def _domain_record(root: Path) -> dict[str, Any] | None:
    """Reproducible identity of the domain pack that applies to the case."""
    from . import domains

    return domains.domain_digest(root)


def commit(case_root: str | Path, registry: str | Path | None = None) -> tuple[dict[str, Any], Path]:
    """Validate, ground, judge, and write a canonical registry record."""
    root = Path(case_root)
    try:
        with case_lock(root):
            return _commit_locked(root, registry)
    except LockError as exc:
        raise ContractError(str(exc)) from exc


def _commit_locked(root: Path, registry: str | Path | None = None) -> tuple[dict[str, Any], Path]:
    case = load_case(root)
    try:
        ledger = load_ledger(root)
    except GroundError as exc:
        raise ContractError(str(exc)) from exc
    grounding_problems, _ = validate_grounding(case, ledger)
    if grounding_problems:
        raise ContractError("grounding gate: " + "; ".join(grounding_problems))
    result = judge(case)
    if result["unbacked"]:
        raise ContractError(
            "unbacked states: " + "; ".join(result["unbacked"]) + ". A satisfied state needs a passed gating test before it can be committed."
        )
    chain_record: dict[str, Any] | None = None
    try:
        from . import chain as chain_module

        chain_sum = chain_module.chain_summary(root)
        chain_problems = chain_module.chain_problems(root)
        if chain_problems:
            raise ContractError("; ".join(chain_problems))
        chain_record = {"sha256": chain_sum["sha256"], "entries": len(chain_sum["entries"])}
    except ContractError:
        raise
    except Exception as exc:  # a broken chain must not be silently committed
        raise ContractError(f"argument chain: {exc}") from exc
    grounding = None
    if ledger is not None:
        grounding = {
            "sha256": ledger_sha256(root),
            "acceptance_rate": ledger.get("acceptance_rate"),
            "grounded": ledger.get("grounded"),
            "drafted": ledger.get("drafted"),
        }
    declared_profile = case.argument.get("profile")
    if not isinstance(declared_profile, dict):
        declared_profile = {}
    computed_statuses = {
        tid: {"status": item["status"], "source": item["source"]}
        for tid, item in (result.get("test_status") or {}).items()
        if item.get("source") == "computed"
    }
    record = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "claim_id": case.claim.get("id"),
        "title": case.argument.get("title"),
        "profile": {
            "primary": declared_profile.get("primary"),
            "secondary": declared_profile.get("secondary") or [],
        },
        "verdict": result["verdict"],
        "reasons": result["reasons"],
        "flags": result["flags"],
        "unbacked": result["unbacked"],
        "test_status": computed_statuses,
        "chain": chain_record,
        "domain": _domain_record(root),
        "grounding": grounding,
        "input_sha256": case_digest(root),
        "engine_sha256": engine_digest(),
        "committed_at": _now(),
    }
    out_dir = registry_dir(root, registry)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = str(record["claim_id"] or "case").replace("/", "_")
    out_path = out_dir / f"{safe}.json"
    atomic_write_text(
        out_path,
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    append_ledger(
        root,
        kind="commit",
        claim_id=record["claim_id"],
        created_at=record["committed_at"],
        record_sha256=record_sha256(record),
        extra={
            "verdict": record["verdict"],
            "rule_version": record["rule_version"],
            "engine_sha256": record["engine_sha256"],
        },
    )
    return record, out_path


def anchor(
    case_root: str | Path,
    out: str | Path | None = None,
    note: str | None = None,
    registry: str | Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """Write a checkpoint over the current ledger head and record it."""
    root = Path(case_root)
    target = Path(out) if out else root / ".geoarg" / ANCHOR_FILE
    record, _ = committed_record(root, registry)
    try:
        with case_lock(root):
            return _anchor_locked(root, record, target, note)
    except LockError as exc:
        raise ContractError(str(exc)) from exc


def _anchor_locked(root: Path, record: dict[str, Any], target: Path, note: str | None) -> tuple[dict[str, Any], Path]:
    entries, problems = _read_ledger(root)
    if problems:
        raise ContractError("; ".join(problems))
    if not entries:
        raise ContractError("ledger is empty; commit before anchoring")
    payload: dict[str, Any] = {
        "schema_version": ANCHOR_SCHEMA_VERSION,
        "claim_id": record.get("claim_id"),
        "record_sha256": record_sha256(record),
        "ledger_head": entries[-1]["record_sha256"],
        "ledger_count": len(entries),
        "engine_sha256": engine_digest(),
        "created_at": _now(),
        "note": note,
    }
    digest = canonical_sha256(payload)
    payload["anchor_sha256"] = digest
    atomic_write_text(target, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    append_ledger(
        root,
        kind="anchor",
        claim_id=payload["claim_id"],
        created_at=payload["created_at"],
        record_sha256=digest,
        extra={"ledger_head": payload["ledger_head"], "ledger_count": payload["ledger_count"]},
    )
    return payload, target


def _read_anchor_payload(root: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = root / ".geoarg" / ANCHOR_FILE
    if not path.exists():
        return None, None
    if not path.is_file():
        return None, f"anchor path is not a regular file: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"anchor file is unreadable: {exc}"
    if not isinstance(payload, dict):
        return None, "anchor file is not a JSON object"
    return payload, None


def _read_anchor(root: Path) -> dict[str, Any] | None:
    payload, _ = _read_anchor_payload(root)
    return payload


def read_anchor(case_root: str | Path) -> dict[str, Any] | None:
    """Public read of the checkpoint file."""
    return _read_anchor(Path(case_root))


def read_external_anchor(path: str | Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read a checkpoint file the caller stored elsewhere."""
    p = Path(path)
    if not p.is_file():
        return None, f"external anchor file is missing: {p}"
    try:
        payload = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"external anchor file is unreadable: {exc}"
    if not isinstance(payload, dict):
        return None, "external anchor file is not a JSON object"
    return payload, None


def external_anchor_problems(root: Path, record: dict[str, Any], anchor_path: str | Path) -> list[str]:
    """Check that an externally kept anchor still matches this ledger and record."""
    payload, problem = read_external_anchor(anchor_path)
    if problem:
        return [problem]
    problems: list[str] = []
    digest = payload.get("anchor_sha256")
    body = {key: value for key, value in payload.items() if key != "anchor_sha256"}
    if digest != canonical_sha256(body):
        problems.append("external anchor digest does not match its content (file was edited)")
    if payload.get("schema_version") != ANCHOR_SCHEMA_VERSION:
        problems.append("external anchor has an unexpected schema_version")
    if payload.get("record_sha256") != record_sha256(record):
        problems.append("external anchor points at a different record than the committed one")
    entries, ledger_problems = _read_ledger(root)
    if ledger_problems:
        problems.extend(ledger_problems)
        return problems
    head = payload.get("ledger_head")
    digests = {entry.get("record_sha256") for entry in entries}
    if head not in digests:
        problems.append("external anchor ledger head is not in this ledger")
    count = payload.get("ledger_count")
    if isinstance(count, int) and count >= 1:
        if count > len(entries):
            problems.append("external anchor checkpoint is newer than this ledger")
        elif entries[count - 1].get("record_sha256") != head:
            problems.append("external anchor ledger head does not match the checkpointed entry")
    return problems


def anchor_problems(root: Path, record: dict[str, Any], require: bool = False) -> list[str]:
    """Check that the anchor file still points at this record and is in the ledger."""
    payload, read_problem = _read_anchor_payload(root)
    if read_problem:
        return [read_problem]
    if payload is None:
        if require:
            return [
                "anchor recorded in the ledger but .geoarg/anchor.json is missing "
                "(re-run geoarg anchor, or keep the out-of-case copy)"
            ]
        return []
    problems: list[str] = []
    stored = payload.get("anchor_sha256")
    rest = {key: value for key, value in payload.items() if key != "anchor_sha256"}
    if stored != canonical_sha256(rest):
        problems.append("anchor file was edited after it was written")
    if payload.get("record_sha256") != record_sha256(record):
        problems.append("anchor points at a different record (re-run geoarg anchor)")
    entries, ledger_problems = _read_ledger(root)
    if ledger_problems:
        problems.extend(f"anchor: {problem}" for problem in ledger_problems)
    elif stored and not any(
        entry.get("kind") == "anchor" and entry.get("record_sha256") == stored for entry in entries
    ):
        problems.append("anchor is not recorded in the ledger")
    return problems


def _record_problems(root: Path, record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for name, digest in (record.get("input_sha256") or {}).items():
        now = file_sha256(root / name)
        if now != digest:
            problems.append(f"input changed since commit: {name}")
    if record.get("rule_version") != RULE_VERSION:
        problems.append(
            f"rule version changed: committed {record.get('rule_version')}, current {RULE_VERSION}"
        )
    current_engine = engine_digest()
    if record.get("engine_sha256") != current_engine:
        problems.append("engine changed since commit (recompute the verdict before trusting it)")

    current_grounding = ledger_sha256(root)
    stored_grounding = (record.get("grounding") or {}).get("sha256")
    if current_grounding != stored_grounding:
        problems.append("grounding ledger changed since commit (re-ground before trusting the verdict)")

    try:
        current_domain = _domain_record(root)
    except ContractError as exc:
        problems.append(f"domain pack is unreadable: {exc}")
    else:
        stored_domain = record.get("domain")
        if (stored_domain or {}).get("sha256") != (current_domain or {}).get("sha256"):
            problems.append("domain pack changed since commit (re-run geoarg commit)")

    stored_chain = (record.get("chain") or {}).get("sha256")
    try:
        from . import chain as chain_module

        current_chain = chain_module.chain_summary(root)["sha256"]
        if current_chain != stored_chain:
            problems.append("argument chain changed since commit (re-run geoarg commit)")
        problems.extend(chain_module.chain_problems(root))
    except ContractError as exc:
        problems.append(f"cannot resolve argument chain: {exc}")
    except Exception as exc:  # pragma: no cover - defensive
        problems.append(f"cannot resolve argument chain: {exc}")

    try:
        case = load_case(root)
        fresh = judge(case)
        recomputed = fresh["verdict"]
        if recomputed != record.get("verdict"):
            problems.append(f"verdict changed: committed {record.get('verdict')}, recomputed {recomputed}")
        computed_now = {
            tid: {"status": item["status"], "source": item["source"]}
            for tid, item in (fresh.get("test_status") or {}).items()
            if item.get("source") == "computed"
        }
        if record.get("test_status") != computed_now:
            problems.append("computed test statuses changed since commit (result or pass_rule edited)")
    except ContractError as exc:  # pragma: no cover - defensive
        problems.append(f"cannot reload case: {exc}")
    return problems


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def verify(
    case_root: str | Path,
    registry: str | Path | None = None,
    external_anchor: str | Path | None = None,
) -> tuple[bool, list[str], dict[str, Any] | None]:
    """Recompute inputs, engine digest, and verdict for every committed record."""
    root = Path(case_root)
    out_dir = registry_dir(root, registry)
    paths = sorted(out_dir.glob("*.json")) if out_dir.is_dir() else []
    if not paths:
        return False, [f"no committed record under {out_dir}"], None
    problems: list[str] = []
    if len(paths) > 1:
        problems.append(
            f"ambiguous registry: {len(paths)} committed records under {out_dir}; one case carries one claim"
        )
    records: list[dict[str, Any]] = []
    record_by_name: dict[str, dict[str, Any]] = {}
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append(f"{path.name}: unreadable record ({exc})")
            continue
        records.append(record)
        record_by_name[path.name] = record
        found = _record_problems(root, record)
        prefix = f"{path.name}: " if len(paths) > 1 else ""
        problems.extend(prefix + problem for problem in found)
    ledger_entries, ledger_problems = _read_ledger(root)
    if ledger_problems:
        problems.extend(ledger_problems)
    kinds = {entry.get("kind", "commit") for entry in ledger_entries}
    if ledger_entries:
        digests = {entry.get("record_sha256") for entry in ledger_entries}
        for name, record in record_by_name.items():
            if record_sha256(record) not in digests:
                problems.append(f"{name}: ledger has no entry for this record")
        latest_commit = _latest_commit(ledger_entries)
        if records and latest_commit is not None:
            latest_sha = latest_commit.get("record_sha256")
            if record_sha256(records[0]) != latest_sha:
                problems.append("registry record is not the latest commit (re-run geoarg commit)")
    if records:
        record = records[0]
        external_ok = False
        if external_anchor is not None:
            external_problems = external_anchor_problems(root, record, external_anchor)
            problems.extend(external_problems)
            external_ok = not external_problems
        problems.extend(anchor_problems(root, record, require="anchor" in kinds and not external_ok))
        try:
            from .attest import attestation_problems

            problems.extend(attestation_problems(root, record, require="attestation" in kinds))
        except ContractError as exc:
            problems.append(f"cannot read attestation: {exc}")
        except Exception as exc:  # pragma: no cover - defensive
            problems.append(f"cannot read attestation: {exc}")
    return not problems, _dedupe(problems), records[0] if records else None


def ledger_report(root: str | Path) -> dict[str, Any]:
    """Summarise the ledger for the `geoarg ledger` command."""
    entries, problems = _read_ledger(Path(root))
    rows = []
    for number, entry in enumerate(entries, 1):
        rows.append(
            {
                "index": number,
                "kind": entry.get("kind", "commit"),
                "created_at": entry.get("created_at") or entry.get("committed_at"),
                "claim_id": entry.get("claim_id"),
                "verdict": entry.get("verdict"),
                "rule_version": entry.get("rule_version"),
                "sha256": entry.get("record_sha256"),
                "prev": entry.get("prev"),
            }
        )
    return {
        "ok": not problems,
        "entries": rows,
        "problems": problems,
        "head": entries[-1].get("record_sha256") if entries else None,
    }
