"""Optional citation checks: offline source gaps and online identifier checks.

This module is deliberately outside the trust chain. The default
`check` / `commit` / `verify` pipeline never imports it and never touches the
network. Running `geoarg sources` or `geoarg references` starts the audit
explicitly; the online command writes a local snapshot
(`.geoarg/references.json`) so the result can be inspected later without
network access.

Two checks are separated because they answer different questions:

- `source_gaps`: does every citation-bearing evidence record carry a quote and
  a source document, so the claim can be grounded at all?
- `verify_references`: does each resolvable identifier (DOI, PMCID, PMID,
  arXiv id) point at a real record whose year/author agree with the citation,
  and (where the provider reports it) has it been retracted?
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contract import ContractError, load_case
from .safeio import atomic_write_text

REFERENCE_SCHEMA_VERSION = "geoarg/references/0.1"
REFERENCE_FILE = "references.json"

STATUSES = ("verified", "mismatch", "not-found", "retracted", "unverifiable", "no-identifier")
FAILING_STATUSES = ("mismatch", "not-found", "retracted")

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s,;\"'()\[\]<>]+", re.IGNORECASE)
_PMCID_RE = re.compile(r"\bPMC\d+\b")
_PMID_RE = re.compile(r"\bPMID:?\s*(\d{6,9})\b", re.IGNORECASE)
_ARXIV_RE = re.compile(r"\barXiv:?\s*(\d{4}\.\d{4,5}(?:v\d+)?)\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
_SURNAME_RE = re.compile(r"\b([A-Z][A-Za-z'\-]{2,})\b")

_UA = "geoarg/references (+https://github.com/geoarg/geo-argument-skills)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _case_relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _citation(record: dict[str, Any]) -> str:
    return str((record.get("source") or {}).get("citation") or "").strip()


def _locator(record: dict[str, Any]) -> dict[str, Any]:
    locator = record.get("source_locator")
    return locator if isinstance(locator, dict) else {}


def _has_quote(record: dict[str, Any]) -> bool:
    return bool(str(_locator(record).get("quote") or "").strip())


def _has_page(record: dict[str, Any]) -> bool:
    page = _locator(record).get("page")
    return page not in (None, "")


def _source_present(case_root: Path) -> bool:
    try:
        from .ground import load_ledger

        ledger = load_ledger(case_root)
    except Exception:  # pragma: no cover - defensive
        return False
    if not ledger:
        return False
    source = ledger.get("source") or ledger.get("pdf") or {}
    if not isinstance(source, dict) or not source:
        return False
    recorded = source.get("case_relative") or source.get("path")
    if recorded:
        candidate = case_root / str(recorded)
        if candidate.is_file():
            return True
        return bool(source.get("sha256"))
    return True


def _read_source_gaps(case_root: Path) -> dict[str, Any]:
    case = load_case(case_root)
    records = case.evidence.get("records") or []
    present = _source_present(case_root)
    rows: list[dict[str, Any]] = []
    for record in records:
        citation = _citation(record)
        if not citation:
            continue
        rows.append(
            {
                "evidence_id": str(record.get("id") or ""),
                "citation": citation,
                "verification": str((record.get("verification") or {}).get("level") or ""),
                "has_quote": _has_quote(record),
                "has_page": _has_page(record),
                "has_source": present,
            }
        )
    missing_quote = [row for row in rows if not row["has_quote"]]
    missing_source = [row for row in rows if not row["has_source"]]
    payload = {
        "schema_version": REFERENCE_SCHEMA_VERSION,
        "case": _case_relative(Path.cwd(), case_root) if str(case_root).startswith(str(Path.cwd())) else str(case_root),
        "claim_id": str(case.claim.get("id") or ""),
        "source_present": present,
        "rows": rows,
        "summary": {
            "citations": len(rows),
            "with_quote": len(rows) - len(missing_quote),
            "without_quote": len(missing_quote),
            "without_source": len(missing_source),
        },
    }
    return payload


def source_gaps(case_root: str | Path) -> dict[str, Any]:
    """Return citation-bearing evidence records and their quote/source status."""
    return _read_source_gaps(Path(case_root))


def source_gap_problems(payload: dict[str, Any], *, require_quote: bool = False, require_source: bool = False) -> list[str]:
    problems: list[str] = []
    if require_quote:
        for row in payload["rows"]:
            if not row["has_quote"]:
                problems.append(f"evidence {row['evidence_id']}: citation has no quoted passage; add source_locator.quote")
    if require_source:
        if payload["rows"] and not payload["source_present"]:
            problems.append(
                "case cites literature but carries no grounding ledger/source document; "
                "run `geoarg ground <case> --source <file>` or pass a source file"
            )
    return problems


def extract_identifiers(citation: str) -> list[dict[str, str]]:
    """Extract resolvable identifiers from a free-text citation."""
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in _DOI_RE.finditer(citation):
        value = match.group(0).rstrip(".")
        key = ("doi", value.lower())
        if key not in seen:
            seen.add(key)
            found.append({"kind": "doi", "value": value})
    for match in _PMCID_RE.finditer(citation):
        key = ("pmcid", match.group(0).upper())
        if key not in seen:
            seen.add(key)
            found.append({"kind": "pmcid", "value": match.group(0).upper()})
    for match in _PMID_RE.finditer(citation):
        key = ("pmid", match.group(1))
        if key not in seen:
            seen.add(key)
            found.append({"kind": "pmid", "value": match.group(1)})
    for match in _ARXIV_RE.finditer(citation):
        key = ("arxiv", match.group(1))
        if key not in seen:
            seen.add(key)
            found.append({"kind": "arxiv", "value": match.group(1)})
    return found


def _http_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed provider URLs
        data = response.read()
    payload = json.loads(data.decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ContractError(f"provider returned a non-object response: {url}")
    return payload


def _first(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _crossref_lookup(identifier: str, timeout: float) -> dict[str, Any]:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(identifier, safe="")
    payload = _http_json(url, timeout)
    message = payload.get("message") or {}
    if not isinstance(message, dict) or not message:
        raise ContractError(f"Crossref returned no message for {identifier}")
    year = None
    for key in ("issued", "published-print", "published-online", "created"):
        date_parts = ((message.get(key) or {}).get("date-parts") or [[None]])[0]
        if date_parts and date_parts[0]:
            year = int(date_parts[0])
            break
    families = [str(author.get("family") or "") for author in message.get("author") or [] if isinstance(author, dict)]
    updated_by = [entry for entry in message.get("updated-by") or [] if isinstance(entry, dict)]
    retracted = any("retract" in str(entry.get("type") or "").lower() for entry in updated_by)
    return {
        "provider": "crossref",
        "title": str(_first(message.get("title")) or ""),
        "year": year,
        "first_author": families[0] if families else "",
        "authors": families[:12],
        "container": str(_first(message.get("container-title")) or ""),
        "retracted": retracted,
        "url": str(message.get("URL") or ""),
    }


def _europepmc_lookup(identifier: str, timeout: float) -> dict[str, Any]:
    if identifier.upper().startswith("PMC"):
        query = f"PMCID:{identifier.upper()}"
    else:
        query = f"EXT_ID:{identifier} AND SRC:MED"
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query="
        + urllib.parse.quote(query, safe="")
        + "&format=json&pageSize=1"
    )
    payload = _http_json(url, timeout)
    results = ((payload.get("resultList") or {}).get("result") or [])
    if not results:
        raise LookupNotFound(f"Europe PMC found no record for {identifier}")
    item = results[0]
    raw_authors = str(item.get("authorString") or "")
    families: list[str] = []
    for part in raw_authors.split(","):
        tokens = part.strip().split()
        if tokens and tokens[0].strip("."):
            families.append(tokens[0].strip("."))
    return {
        "provider": "europepmc",
        "title": str(item.get("title") or ""),
        "year": int(item["pubYear"]) if str(item.get("pubYear") or "").isdigit() else None,
        "first_author": families[0] if families else "",
        "authors": families[:12],
        "container": str(item.get("journalTitle") or ""),
        "retracted": bool(item.get("isRetracted")),
        "url": f"https://europepmc.org/article/{item.get('source', 'MED')}/{item.get('id', identifier)}",
    }


class LookupNotFound(Exception):
    """Provider answered cleanly but had no record."""


def _lookup(identifier: dict[str, str], provider: str, timeout: float) -> dict[str, Any]:
    kind = identifier["kind"]
    value = identifier["value"]
    if provider == "crossref":
        if kind != "doi":
            raise LookupNotFound(f"Crossref does not resolve {kind}")
        return _crossref_lookup(value, timeout)
    if provider == "europepmc":
        if kind not in ("pmcid", "pmid", "doi"):
            raise LookupNotFound(f"Europe PMC does not resolve {kind}")
        return _europepmc_lookup(value, timeout)
    raise LookupNotFound(f"unknown provider {provider}")


def _citation_year(citation: str) -> int | None:
    years = [int(value) for value in _YEAR_RE.findall(citation)]
    return years[0] if years else None


def _citation_surname(citation: str) -> str:
    token = citation.split("(")[0]
    match = _SURNAME_RE.search(token)
    return match.group(1) if match else ""


def _assess(citation: str, remote: dict[str, Any]) -> tuple[str, list[str]]:
    notes: list[str] = []
    if remote.get("retracted"):
        return "retracted", ["provider reports a retraction/update-to"]
    local_year = _citation_year(citation)
    remote_year = remote.get("year")
    if local_year is not None and remote_year is not None and abs(local_year - int(remote_year)) > 1:
        return "mismatch", [f"citation year {local_year} vs provider year {remote_year}"]
    local_surname = _citation_surname(citation)
    families = [name.split()[-1] for name in remote.get("authors") or remote.get("first_author", "").split(",") if name]
    if local_surname and families:
        haystack = " ".join(families).lower()
        if local_surname.lower() not in haystack:
            notes.append(f"citation surname {local_surname!r} not found in provider authors")
            return "mismatch", notes
    return "verified", notes


def _request_with_retry(provider: str, identifier: dict[str, str], timeout: float) -> dict[str, Any]:
    import time

    for attempt in range(2):
        try:
            return _lookup(identifier, provider, timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(1.5)
                continue
            raise
    raise ContractError(f"{provider} unavailable")  # pragma: no cover - loop always returns/raises


def _verify_identifier(citation: str, identifier: dict[str, str], providers: list[str], timeout: float) -> dict[str, Any]:
    attempts: list[str] = []
    saw_not_found = False
    for provider in providers:
        try:
            remote = _request_with_retry(provider, identifier, timeout)
        except LookupNotFound:
            attempts.append(f"{provider}: no record")
            continue
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                attempts.append(f"{provider}: not found")
                saw_not_found = True
                continue
            attempts.append(f"{provider}: HTTP {exc.code}")
            continue
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ContractError) as exc:
            attempts.append(f"{provider}: unreachable ({exc})")
            continue
        status, notes = _assess(citation, remote)
        return {"status": status, "provider": provider, "remote": remote, "notes": notes, "attempts": attempts}
    status = "not-found" if saw_not_found else ("no-identifier" if identifier.get("kind") == "unknown" else "unverifiable")
    return {
        "status": status,
        "provider": "",
        "remote": None,
        "notes": attempts or ["no provider resolved the identifier"],
        "attempts": attempts,
    }


def _snapshot_path(case_root: Path) -> Path:
    return case_root / ".geoarg" / REFERENCE_FILE


def read_snapshot(case_root: str | Path) -> dict[str, Any] | None:
    path = _snapshot_path(Path(case_root))
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def verify_references(
    case_root: str | Path,
    *,
    providers: tuple[str, ...] = ("crossref", "europepmc"),
    refresh: bool = False,
    offline: bool = False,
    timeout: float = 8.0,
    pace: float = 0.35,
) -> dict[str, Any]:
    """Check identifiers online (or read the cached snapshot) and write the snapshot."""
    import time

    root = Path(case_root)
    cached = read_snapshot(root)
    if offline:
        if cached is None:
            raise ContractError("no references snapshot; run `geoarg references <case>` once while online")
        return cached
    if cached is not None and not refresh:
        return cached
    case = load_case(root)
    records = case.evidence.get("records") or []
    rows: list[dict[str, Any]] = []
    for record in records:
        citation = _citation(record)
        if not citation:
            continue
        identifiers = extract_identifiers(citation)
        if not identifiers:
            rows.append(
                {
                    "evidence_id": str(record.get("id") or ""),
                    "citation": citation,
                    "identifiers": [],
                    "status": "no-identifier",
                    "provider": "",
                    "remote": None,
                    "notes": ["no DOI, PMCID, PMID or arXiv id in the citation"],
                }
            )
            continue
        for position, identifier in enumerate(identifiers):
            if position or pace:
                time.sleep(max(0.0, pace))
            outcome = _verify_identifier(citation, identifier, list(providers), timeout)
            rows.append(
                {
                    "evidence_id": str(record.get("id") or ""),
                    "citation": citation,
                    "identifiers": [identifier],
                    "status": outcome["status"],
                    "provider": outcome["provider"],
                    "remote": outcome["remote"],
                    "notes": outcome["notes"],
                }
            )
    summary = {status: sum(1 for row in rows if row["status"] == status) for status in STATUSES}
    payload = {
        "schema_version": REFERENCE_SCHEMA_VERSION,
        "case": _case_relative(Path.cwd(), root) if str(root).startswith(str(Path.cwd())) else str(root),
        "claim_id": str(case.claim.get("id") or ""),
        "created_at": _now(),
        "providers": list(providers),
        "rows": rows,
        "summary": summary,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path = _snapshot_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)
    payload["snapshot"] = {"path": _case_relative(root, path), "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    return payload


def reference_requirements_met(payload: dict[str, Any]) -> list[str]:
    """Problems for `references --require-verified`: anything not verified."""
    problems: list[str] = []
    for row in payload.get("rows", []):
        if row.get("status") != "verified":
            problems.append(
                f"evidence {row.get('evidence_id')}: {row.get('status')} ({row.get('citation')})"
            )
    return problems


_LABELS = {
    "en": {
        "title": "Citation checks (optional)",
        "sources": "Citation sources",
        "no-source": "no grounding source document",
        "with-quote": "with quoted passage",
        "without-quote": "without quoted passage",
        "references": "Identifier verification",
        "verified": "verified",
        "mismatch": "mismatch",
        "not-found": "not found",
        "retracted": "retracted",
        "unverifiable": "unverifiable",
        "no-identifier": "no identifier",
        "cached": "cached snapshot",
        "note": "This optional report does not change a verdict, commit or verify result.",
    },
    "zh": {
        "title": "引用核验（可选）",
        "sources": "引用来源",
        "no-source": "没有接地源文件",
        "with-quote": "有引文片段",
        "without-quote": "没有引文片段",
        "references": "标识符核验",
        "verified": "已核验",
        "mismatch": "元数据不符",
        "not-found": "未找到",
        "retracted": "已撤稿",
        "unverifiable": "无法核验",
        "no-identifier": "无标识符",
        "cached": "缓存快照",
        "note": "这份可选报告不改变判决、commit 或 verify 的结果。",
    },
}

_STATUS_LABELS = {
    "en": {
        "verified": "verified",
        "mismatch": "mismatch",
        "not-found": "not found",
        "retracted": "retracted",
        "unverifiable": "unverifiable",
        "no-identifier": "no identifier",
    },
    "zh": {
        "verified": "已核验",
        "mismatch": "元数据不符",
        "not-found": "未找到",
        "retracted": "已撤稿",
        "unverifiable": "无法核验",
        "no-identifier": "无标识符",
    },
}


def _pick(lang: str) -> dict[str, Any]:
    return _STATUS_LABELS["zh" if str(lang).lower().startswith("zh") else "en"]


def _labels(lang: str) -> dict[str, str]:
    return _LABELS["zh" if str(lang).lower().startswith("zh") else "en"]


def render_sources(payload: dict[str, Any], lang: str = "en") -> str:
    labels = _labels(lang)
    summary = payload.get("summary") or {}
    lines = [
        f"## {labels['title']}",
        "",
        f"- {labels['sources']}: {summary.get('citations', 0)}",
        f"- {labels['with-quote']}: {summary.get('with_quote', 0)}",
        f"- {labels['without-quote']}: {summary.get('without_quote', 0)}",
        f"- {labels['no-source']}: {summary.get('without_source', 0)}",
        "",
    ]
    if payload.get("rows"):
        lines.append(f"| {'evidence' if lang.startswith('en') else '证据'} | quote | citation |")
        lines.append("|---|---|---|")
        for row in payload["rows"]:
            quote_mark = "yes" if row["has_quote"] else "no"
            lines.append(f"| {row['evidence_id']} | {quote_mark} | {row['citation']} |")
        lines.append("")
    lines.append(labels["note"])
    return "\n".join(lines) + "\n"


def render_references(payload: dict[str, Any], lang: str = "en") -> str:
    labels = _labels(lang)
    status_labels = _pick(lang)
    summary = payload.get("summary") or {}
    lines = [f"## {labels['references']}", ""]
    for status in STATUSES:
        count = int(summary.get(status, 0) or 0)
        if count:
            lines.append(f"- {status_labels[status]}: {count}")
    lines.append("")
    if payload.get("rows"):
        lines.append("| evidence | status | identifier | provider | title |")
        lines.append("|---|---|---|---|---|")
        for row in payload["rows"]:
            identifiers = ", ".join(f"{item['kind']}:{item['value']}" for item in row.get("identifiers") or [])
            remote = (row.get("remote") or {}).get("title") or ""
            lines.append(
                f"| {row['evidence_id']} | {status_labels.get(row['status'], row['status'])} | "
                f"{identifiers} | {row.get('provider', '')} | {remote} |"
            )
        lines.append("")
    if payload.get("created_at"):
        lines.append(f"checked at: {payload['created_at']}")
    lines.append(labels["note"])
    return "\n".join(lines) + "\n"
