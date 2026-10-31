"""Hash-chained registry: commit a verdict, verify it later.

A verdict that cannot be recomputed from the recorded inputs is an opinion.
`commit` writes a canonical JSON record containing the input digests, the
engine digest, the rule version, and the verdict; `verify` recomputes all of
them and reports every mismatch.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contract import CASE_FILES, ContractError, load_case
from .judge import RULE_VERSION, judge

_ENGINE_FILES = ("contract.py", "judge.py", "independence.py", "hitting.py")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return _sha256_bytes(path.read_bytes())


def case_digest(root: Path) -> dict[str, str | None]:
    return {name: file_sha256(root / name) for name in CASE_FILES}


def engine_digest() -> str:
    package = Path(__file__).resolve().parent
    parts = []
    for name in _ENGINE_FILES:
        parts.append(_sha256_bytes((package / name).read_bytes()))
    return _sha256_bytes("".join(parts).encode("ascii"))


def registry_dir(case_root: Path, override: str | Path | None = None) -> Path:
    return Path(override) if override else case_root / ".geoarg" / "registry"


def commit(case_root: str | Path, registry: str | Path | None = None) -> tuple[dict[str, Any], Path]:
    """Validate, judge, and write a canonical registry record."""
    root = Path(case_root)
    case = load_case(root)
    result = judge(case)
    record = {
        "schema_version": "geoarg/registry/0.1",
        "rule_version": RULE_VERSION,
        "claim_id": case.claim.get("id"),
        "title": case.argument.get("title"),
        "verdict": result["verdict"],
        "reasons": result["reasons"],
        "flags": result["flags"],
        "input_sha256": case_digest(root),
        "engine_sha256": engine_digest(),
        "committed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    out_dir = registry_dir(root, registry)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = str(record["claim_id"] or "case").replace("/", "_")
    out_path = out_dir / f"{safe}.json"
    out_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return record, out_path


def verify(case_root: str | Path, registry: str | Path | None = None) -> tuple[bool, list[str], dict[str, Any] | None]:
    """Recompute inputs, engine digest, and verdict; report every mismatch."""
    root = Path(case_root)
    out_dir = registry_dir(root, registry)
    records = sorted(out_dir.glob("*.json")) if out_dir.is_dir() else []
    if not records:
        return False, [f"no committed record under {out_dir}"], None
    record = json.loads(records[0].read_text(encoding="utf-8"))
    problems: list[str] = []

    for name, digest in (record.get("input_sha256") or {}).items():
        now = file_sha256(root / name)
        if now != digest:
            problems.append(f"input changed since commit: {name}")
    current_engine = engine_digest()
    if record.get("engine_sha256") != current_engine:
        problems.append("engine changed since commit (recompute the verdict before trusting it)")

    try:
        case = load_case(root)
        recomputed = judge(case)["verdict"]
        if recomputed != record.get("verdict"):
            problems.append(f"verdict changed: committed {record.get('verdict')}, recomputed {recomputed}")
    except ContractError as exc:  # pragma: no cover - defensive
        problems.append(f"cannot reload case: {exc}")

    return not problems, problems, record
