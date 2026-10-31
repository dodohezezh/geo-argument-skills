"""Ground transcribed evidence against a source PDF.

The gate has a speculative-decoding shape. A model drafts quotes cheaply; this
module verifies every quote against the PDF text layer deterministically, and
only a grounded quote may stay `accepted` at transcription level. The guarantee
is deliberately narrow: a grounded quote means the string occurs in the source,
not that the interpretation built on it is right.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contract import Case

GROUND_SCHEMA_VERSION = "geoarg/ground/0.1"
MIN_TEXT_CHARS = 20

GROUNDED = "grounded"
PAGE_MISMATCH = "page-mismatch"
NOT_FOUND = "not-found"
NOT_GROUNDABLE = "not-groundable"
NO_LOCATOR = "no-locator"

_COUNTED = (GROUNDED, PAGE_MISMATCH, NOT_FOUND, NOT_GROUNDABLE, NO_LOCATOR)


class GroundError(Exception):
    """Raised when a PDF cannot be read or its text cannot be extracted."""


def normalize(text: str) -> str:
    """Normalize extracted and quoted text so layout does not hide a match."""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u00ad", "")
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.casefold().strip()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def quote_sha256(quote: str) -> str:
    """Digest of the normalized quote. Stored so a later edit can be detected."""
    return _sha256(normalize(quote).encode("utf-8"))


def _pypdf():  # type: ignore[no-untyped-def]
    try:
        import pypdf
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise GroundError("pypdf is required for grounding: pip install pypdf") from exc
    return pypdf


def extract_pages(pdf_path: str | Path) -> tuple[list[str], dict[str, Any]]:
    """Return normalized text per page plus extraction metadata."""
    pypdf = _pypdf()
    path = Path(pdf_path)
    if not path.is_file():
        raise GroundError(f"pdf not found: {path}")
    try:
        reader = pypdf.PdfReader(str(path))
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception as exc:  # pragma: no cover - encryption path
                raise GroundError(f"pdf is encrypted: {path}") from exc
        pages: list[str] = []
        for page in reader.pages:
            try:
                pages.append(normalize(page.extract_text() or ""))
            except Exception:  # pragma: no cover - per-page decode failure
                pages.append("")
    except GroundError:
        raise
    except Exception as exc:
        raise GroundError(f"cannot read pdf {path}: {exc}") from exc
    chars = sum(len(page) for page in pages)
    metadata = {
        "extractor": f"pypdf {pypdf.__version__}",
        "pages": len(pages),
        "chars": chars,
        "text_layer": chars >= MIN_TEXT_CHARS,
    }
    return pages, metadata


def _page_starts(pages: list[str]) -> list[int]:
    starts: list[int] = []
    offset = 0
    for page in pages:
        starts.append(offset)
        offset += len(page) + 1
    return starts


def _page_of(starts: list[int], offset: int) -> int:
    page = 1
    for index, start in enumerate(starts):
        if start <= offset:
            page = index + 1
    return page


def ground_records(case: Case, pdf_path: str | Path) -> dict[str, Any]:
    """Check every declared quote against the PDF and return the ledger."""
    pages, extracted = extract_pages(pdf_path)
    document = " ".join(pages)
    starts = _page_starts(pages)
    path = Path(pdf_path).resolve()
    counts = {status: 0 for status in _COUNTED}
    results: dict[str, dict[str, Any]] = {}
    drafted = 0

    for record in case.evidence.get("records", []):
        rid = record.get("id")
        locator = record.get("source_locator") or {}
        page = locator.get("page")
        quote = locator.get("quote")
        entry: dict[str, Any] = {
            "page": page if isinstance(page, int) else None,
            "found_page": None,
            "quote_sha256": quote_sha256(quote) if isinstance(quote, str) and quote.strip() else None,
        }
        if not isinstance(quote, str) or not quote.strip():
            status = NO_LOCATOR
        elif not extracted["text_layer"]:
            status = NOT_GROUNDABLE
        else:
            normalized = normalize(quote)
            declared = page if isinstance(page, int) else 0
            if 1 <= declared <= len(pages) and normalized in pages[declared - 1]:
                status = GROUNDED
                entry["found_page"] = declared
            else:
                hit = document.find(normalized)
                if hit >= 0:
                    status = PAGE_MISMATCH
                    entry["found_page"] = _page_of(starts, hit)
                else:
                    status = NOT_FOUND
        entry["status"] = status
        results[rid] = entry
        counts[status] += 1
        if status != NO_LOCATOR:
            drafted += 1

    grounded = counts[GROUNDED]
    for known in (GROUNDED, PAGE_MISMATCH, NOT_FOUND, NOT_GROUNDABLE):
        counts.setdefault(known, 0)
    try:
        relative = path.relative_to(Path(case.root).resolve())
        pdf_entry = {"path": str(relative), "case_relative": True}
    except ValueError:
        pdf_entry = {"path": str(path), "case_relative": False}
    pdf_entry["sha256"] = _sha256(Path(pdf_path).read_bytes())

    return {
        "schema_version": GROUND_SCHEMA_VERSION,
        "claim_id": case.claim.get("id"),
        "pdf": pdf_entry,
        "extracted": extracted,
        "records": results,
        "counts": counts,
        "drafted": drafted,
        "grounded": grounded,
        "acceptance_rate": round(grounded / drafted, 3) if drafted else None,
        "grounded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def ledger_dir(case_root: str | Path) -> Path:
    return Path(case_root) / ".geoarg" / "ground"


def ledger_file(case_root: str | Path) -> Path | None:
    """Return the committed grounding ledger for a case, if one exists."""
    directory = ledger_dir(case_root)
    if not directory.is_dir():
        return None
    candidates = sorted(directory.glob("*.json"))
    return candidates[0] if candidates else None


def write_ledger(case: Case, ledger: dict[str, Any]) -> Path:
    out_dir = ledger_dir(case.root)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = str(case.claim.get("id") or "case").replace("/", "_")
    path = out_dir / f"{safe}.json"
    path.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_ledger(case_root: str | Path) -> dict[str, Any] | None:
    path = ledger_file(case_root)
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GroundError(f"corrupt grounding ledger {path}: {exc}") from exc


def ledger_sha256(case_root: str | Path) -> str | None:
    path = ledger_file(case_root)
    if path is None:
        return None
    return _sha256(path.read_bytes())


def validate_grounding(case: Case, ledger: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    """Return (problems, warnings) for the transcription-level quote gate.

    A quote is required at transcription level. When such a record is accepted,
    the ledger must show it grounded and the quote must not have changed since.
    """
    problems: list[str] = []
    warnings: list[str] = []
    records = (ledger or {}).get("records", {})

    for record in case.evidence.get("records", []):
        rid = record.get("id")
        level = (record.get("verification") or {}).get("level")
        if level != "transcription":
            continue
        locator = record.get("source_locator") or {}
        quote = locator.get("quote")
        page = locator.get("page")
        if not isinstance(quote, str) or not quote.strip() or not isinstance(page, int) or page < 1:
            problems.append(
                f"evidence {rid}: transcription-level evidence needs source_locator with page and quote"
            )
            continue
        if record.get("status") != "accepted":
            continue
        if ledger is None:
            problems.append(
                f"evidence {rid}: accepted transcription-level quote is not grounded; run geoarg ground <case> --pdf <paper>"
            )
            continue
        entry = records.get(rid)
        if entry is None:
            problems.append(f"evidence {rid}: quote has no grounding entry; re-run geoarg ground")
            continue
        status = entry.get("status")
        if status != GROUNDED:
            found = entry.get("found_page")
            detail = f", found on page {found}" if found and status == PAGE_MISMATCH else ""
            problems.append(f"evidence {rid}: quote is {status}{detail}, not grounded")
            continue
        if entry.get("quote_sha256") != quote_sha256(quote):
            problems.append(f"evidence {rid}: grounding is stale (the quote changed since ground)")

    if ledger:
        pdf = ledger.get("pdf") or {}
        raw = pdf.get("path")
        if raw:
            path = Path(case.root) / raw if pdf.get("case_relative") else Path(raw)
            if path.is_file():
                if _sha256(path.read_bytes()) != pdf.get("sha256"):
                    problems.append(f"pdf changed since grounding: {raw}; re-run geoarg ground")
            else:
                warnings.append(f"grounded pdf is missing at {raw}; the quote digest is checked, the pdf is not")

    return problems, warnings
