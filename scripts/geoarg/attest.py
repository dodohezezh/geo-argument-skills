"""Bind rendered deliverables and the authored judgment to the committed record.

`commit` fixes the verdict at a point in time; `attest` fixes the bytes the
reader actually receives. A report that was regenerated after the commit, or a
judgment paragraph that was edited by hand, then trips `verify` instead of
silently passing as the committed conclusion.

Attestation covers the deliverables the case ships (`report.*`, `card.*`) and
any judgment file passed explicitly. It records file digests, the record digest
it was built for, the engine digest, and the environment (`python`, platform,
geoarg version), and appends an `attestation` entry to the ledger. It does not
prove the report is good prose; it proves these bytes correspond to that record.
"""

from __future__ import annotations

import glob
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import (
    ATTESTATION_FILE,
    append_ledger,
    canonical_sha256,
    committed_record,
    engine_digest,
    ledger_entries,
    record_sha256,
)
from .contract import ContractError
from .safeio import LockError, atomic_write_text, case_lock

ATTESTATION_SCHEMA_VERSION = "geoarg/attestation/0.1"

DEFAULT_PATTERNS = (
    "report.md",
    "report.*.md",
    "report.docx",
    "report.*.docx",
    "report.html",
    "report.*.html",
    "card.md",
    "card.*.md",
    "card.docx",
    "card.*.docx",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _geoarg_version() -> str:
    try:
        from . import __version__

        return __version__
    except Exception:  # pragma: no cover - defensive
        return "unknown"


def environment() -> dict[str, Any]:
    """Record enough about the run to reproduce it roughly."""
    return {
        "geoarg": _geoarg_version(),
        "python": platform.python_version(),
        "platform": sys.platform,
    }


def _collect(root: Path, patterns: list[str] | tuple[str, ...], *, strict: bool) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        spec = Path(pattern)
        if spec.is_absolute():
            candidates = [spec] if spec.is_file() else []
        else:
            candidates = [Path(match) for match in sorted(glob.glob(str(root / pattern)))]
        if not candidates and strict:
            raise ContractError(f"include pattern matched no file: {pattern}")
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen or not candidate.is_file():
                continue
            seen.add(resolved)
            found.append(candidate)
    return found


def _entry(root: Path, path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        recorded = resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        recorded = resolved.as_posix()
    data = path.read_bytes()
    return {
        "path": recorded,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def _entries(root: Path, paths: list[Path]) -> list[dict[str, Any]]:
    return sorted((_entry(root, path) for path in paths), key=lambda item: item["path"])


def _read_attestation_payload(root: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = root / ".geoarg" / ATTESTATION_FILE
    if not path.exists():
        return None, None
    if not path.is_file():
        return None, f"attestation path is not a regular file: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"attestation file is unreadable: {exc}"
    if not isinstance(payload, dict):
        return None, "attestation file is not a JSON object"
    return payload, None


def read_attestation(case_root: str | Path) -> dict[str, Any] | None:
    payload, _ = _read_attestation_payload(Path(case_root))
    return payload


def attestation_sha(payload: dict[str, Any]) -> str:
    return canonical_sha256(payload)


def attest(
    case_root: str | Path,
    include: list[str] | None = None,
    judgment_files: list[str] | None = None,
    note: str | None = None,
    registry: str | Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """Write .geoarg/attestation.json for the current committed record."""
    root = Path(case_root)
    record, _ = committed_record(root, registry)
    try:
        with case_lock(root):
            return _attest_locked(root, record, include, judgment_files, note)
    except LockError as exc:
        raise ContractError(str(exc)) from exc


def _attest_locked(
    root: Path,
    record: dict[str, Any],
    include: list[str] | None,
    judgment_files: list[str] | None,
    note: str | None,
) -> tuple[dict[str, Any], Path]:
    entries, problems = ledger_entries(root)
    if problems:
        raise ContractError("; ".join(problems))
    latest_commit = None
    for entry in reversed(entries):
        if entry.get("kind", "commit") == "commit":
            latest_commit = entry
            break
    if latest_commit is None or latest_commit.get("record_sha256") != record_sha256(record):
        raise ContractError(
            "commit the current state before attesting (the latest ledger commit differs from the registry record)"
        )
    deliverables = _entries(root, _collect(root, include or DEFAULT_PATTERNS, strict=bool(include)))
    if not deliverables:
        raise ContractError(
            "no deliverable matched (report.*, card.*); generate the report or card first, or pass --include <glob>"
        )
    if judgment_files is None:
        previous, _ = _read_attestation_payload(root)
        previous_entries = (previous or {}).get("judgment") or []
        judgment_paths: list[Path] = []
        for entry in previous_entries:
            recorded = str(entry.get("path") or "")
            if not recorded:
                continue
            candidate = Path(recorded)
            if not candidate.is_absolute():
                candidate = root / candidate
            if not candidate.is_file():
                raise ContractError(
                    f"judgment file listed in the previous attestation is missing: {recorded}; "
                    "pass --judgment-file to rebind the judgment"
                )
            judgment_paths.append(candidate)
        judgments = _entries(root, judgment_paths)
    else:
        judgments = _entries(root, _collect(root, judgment_files, strict=bool(judgment_files)))
    payload: dict[str, Any] = {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "claim_id": record.get("claim_id"),
        "record_sha256": record_sha256(record),
        "rule_version": record.get("rule_version"),
        "engine_sha256": engine_digest(),
        "created_at": _now(),
        "note": note,
        "environment": environment(),
        "deliverables": deliverables,
        "judgment": judgments,
    }
    path = root / ".geoarg" / ATTESTATION_FILE
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    append_ledger(
        root,
        kind="attestation",
        claim_id=payload["claim_id"],
        created_at=payload["created_at"],
        record_sha256=attestation_sha(payload),
        extra={"deliverables": len(deliverables), "judgment": len(judgments)},
    )
    return payload, path


def attestation_problems(root: Path, record: dict[str, Any], require: bool = False) -> list[str]:
    """Check the attested bytes still match the committed record."""
    payload, read_problem = _read_attestation_payload(root)
    if read_problem:
        return [read_problem]
    if payload is None:
        if require:
            return [
                "attestation recorded in the ledger but .geoarg/attestation.json is missing "
                "(re-run geoarg attest)"
            ]
        return []
    problems: list[str] = []
    entries, ledger_problems = ledger_entries(root)
    if ledger_problems:
        problems.extend(ledger_problems)
    else:
        digest = attestation_sha(payload)
        recorded = any(
            entry.get("kind") == "attestation" and entry.get("record_sha256") == digest for entry in entries
        )
        if not recorded:
            problems.append("attestation is not recorded in the ledger")
    if payload.get("record_sha256") != record_sha256(record):
        problems.append("attestation predates the current commit (re-run geoarg attest)")
    if payload.get("engine_sha256") != engine_digest():
        problems.append("engine changed since attestation (re-attest after reviewing the output)")
    for kind, label in (("deliverables", "deliverable"), ("judgment", "judgment file")):
        for entry in payload.get(kind) or []:
            recorded_path = str(entry.get("path") or "")
            path = Path(recorded_path)
            if not path.is_absolute():
                path = root / path
            if not path.is_file():
                problems.append(f"{label} missing since attestation: {recorded_path}")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != entry.get("sha256"):
                problems.append(f"{label} changed since attestation: {recorded_path}")
    return problems
