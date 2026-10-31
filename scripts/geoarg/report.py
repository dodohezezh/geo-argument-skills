"""Render a human-readable GeoArg report from a case.

The report is rendered from one document model into two formats: Markdown for
terminals and diffs, Word (.docx) for people who read reports in Word. Word is
the default because the audit skill's deliverable is a reviewable document.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .audit import case_digest
from .contract import Case
from .ground import GroundError, load_ledger, validate_grounding
from .hitting import decisive_events
from .independence import report as independence_report
from .judge import judge

# A block is one of:
#   ("p", text)
#   ("bullets", [text, ...])
#   ("table", (header, rows))
#   ("note", text)
Block = tuple[str, Any]


def _table(header: list[str], rows: list[list[str]]) -> Block:
    return ("table", (header, rows))


def build(case: Case) -> dict:
    """Build the document model shared by the Markdown and Word renderers."""
    result = judge(case)
    indep = independence_report(case)
    decisive = decisive_events(case)
    claim = case.claim

    meta: list[tuple[str, str]] = [
        ("claim", f"{claim.get('id')} ({claim.get('kind')}, {claim.get('layer')})"),
        ("statement", str(claim.get("statement", ""))),
        ("verdict", result["verdict"]),
        ("rule version", result["rule_version"]),
    ]
    if result["flags"]:
        meta.append(("flags", "; ".join(result["flags"])))

    sections: list[dict] = []

    why: list[str] = []
    for key, title in (("hard", "hard defeat"), ("soft", "suspension"), ("pending", "unresolved")):
        reasons = result["reasons"][key]
        if reasons:
            why.extend(f"{title}: {reason}" for reason in reasons)
        else:
            why.append(f"{title}: none")
    sections.append({"heading": "Why this verdict", "blocks": [("bullets", why)]})

    sections.append(
        {
            "heading": "Premises",
            "blocks": [_table(["id", "state", "statement"], [[p["id"], p["status"], p["statement"]] for p in result["premises"]])],
        }
    )
    sections.append(
        {
            "heading": "Ceteris paribus conditions",
            "blocks": [_table(["id", "state", "test"], [[c["id"], c["state"], c["test"]] for c in result["cps"]])],
        }
    )
    sections.append(
        {
            "heading": "Defeaters",
            "blocks": [
                _table(
                    ["id", "state", "severity", "test"],
                    [[d["id"], d["state"], d["severity"], d["test"]] for d in result["defeaters"]],
                )
            ],
        }
    )
    sections.append(
        {
            "heading": "Entailments",
            "blocks": [
                _table(
                    ["id", "status", "risk", "test"],
                    [[e["id"], e["status"], e["risk"], e["test"]] for e in result["entailments"]],
                )
            ],
        }
    )

    indep_lines = [
        f"effective independent evidence: n_eff = {indep['n_eff']} out of {indep['n_records']} records "
        f"(mean rho = {indep['mean_rho']})",
        f"families: {', '.join(indep['families']) or 'none'}",
    ]
    indep_lines.extend(f"warning: {warning}" for warning in indep["warnings"])
    if indep["declared_calibration_not_attached"]:
        indep_lines.append(f"declared but unattached calibration: {indep['declared_calibration_not_attached']}")
    sections.append({"heading": "Independence", "blocks": [("bullets", indep_lines)]})

    grounding_blocks: list[Block] = []
    try:
        ledger = load_ledger(case.root)
        grounding_problems, grounding_warnings = validate_grounding(case, ledger)
    except GroundError as exc:
        ledger = None
        grounding_problems = [f"grounding ledger unreadable: {exc}"]
        grounding_warnings = []
    if ledger is None:
        grounding_blocks.append(("p", "No grounding ledger. Transcription-level evidence is unverified."))
    else:
        pdf = ledger["pdf"]
        extracted = ledger["extracted"]
        text_layer = "yes" if extracted["text_layer"] else "no"
        rate = ledger["acceptance_rate"]
        grounding_blocks.append(
            (
                "p",
                f"Source: {pdf['path']} ({extracted['pages']} pages, {extracted['chars']} chars, text layer: {text_layer}).",
            )
        )
        grounding_blocks.append(
            (
                "p",
                f"Acceptance rate: {rate if rate is not None else 'n/a'} "
                f"({ledger['grounded']}/{ledger['drafted']} drafted quotes grounded).",
            )
        )
        rows = [
            [rid, entry["status"], entry.get("page", ""), entry.get("found_page", "")]
            for rid, entry in ledger["records"].items()
        ]
        if rows:
            grounding_blocks.append(_table(["evidence", "status", "declared page", "found page"], rows))
    for problem in grounding_problems:
        grounding_blocks.append(("p", f"Problem: {problem}"))
    for warning in grounding_warnings:
        grounding_blocks.append(("p", f"Warning: {warning}"))
    sections.append({"heading": "Grounding", "blocks": grounding_blocks})

    decisive_blocks: list[Block] = [
        ("p", f"Base verdict is {decisive['base_verdict']}. These single outcomes would retract the claim now:")
    ]
    if decisive["events"]:
        decisive_blocks.append(
            _table(
                ["outcome", "test", "power", "result"],
                [[e["label"], e["test"], e["power"], e["resulting_verdict"]] for e in decisive["events"]],
            )
        )
    else:
        decisive_blocks.append(("p", "None found. The claim is already defeated, or the contract has no live unknown items."))
    decisive_blocks.append(("note", decisive["note"]))
    sections.append({"heading": "Decisive tests", "blocks": decisive_blocks})

    gaps = case.argument.get("gaps", [])
    if gaps:
        sections.append(
            {
                "heading": "Registered gaps",
                "blocks": [
                    _table(
                        ["kind", "severity", "description"],
                        [[g.get("kind"), g.get("severity"), g.get("description")] for g in gaps],
                    )
                ],
            }
        )

    audit_lines = [f"{name}: {digest}" for name, digest in case_digest(case.root).items()]
    sections.append({"heading": "Audit", "blocks": [("bullets", audit_lines)]})

    return {
        "title": f"GeoArg report: {case.argument.get('title', 'untitled')}",
        "meta": meta,
        "sections": sections,
    }


def render(case: Case) -> str:
    """Render the document model as Markdown."""
    model = build(case)
    out: list[str] = [f"# {model['title']}", ""]
    for label, value in model["meta"]:
        out.append(f"- {label}: {value}")
    out.append("")
    for section in model["sections"]:
        out.append(f"## {section['heading']}")
        for kind, payload in section["blocks"]:
            if kind == "p":
                out.append(payload)
            elif kind == "bullets":
                out.extend(f"- {line}" for line in payload)
            elif kind == "table":
                header, rows = payload
                out.append("| " + " | ".join(header) + " |")
                out.append("|" + "|".join(["---"] * len(header)) + "|")
                for row in rows:
                    out.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
            elif kind == "note":
                out.append(f"_{payload}_")
        out.append("")
    return "\n".join(out)


def render_docx(case: Case, path: str | Path) -> Path:
    """Render the document model as a Word document and return its path."""
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RuntimeError("python-docx is required for Word reports: pip install python-docx") from exc

    model = build(case)
    document = Document()
    document.core_properties.title = model["title"]
    document.add_heading(model["title"], level=0)
    for label, value in model["meta"]:
        paragraph = document.add_paragraph(style="List Bullet")
        run = paragraph.add_run(f"{label}: ")
        run.bold = True
        run.font.size = Pt(10)
        paragraph.add_run(value)

    for section in model["sections"]:
        document.add_heading(section["heading"], level=2)
        for kind, payload in section["blocks"]:
            if kind == "p":
                document.add_paragraph(payload)
            elif kind == "bullets":
                for line in payload:
                    document.add_paragraph(line, style="List Bullet")
            elif kind == "note":
                paragraph = document.add_paragraph()
                paragraph.add_run(payload).italic = True
            elif kind == "table":
                header, rows = payload
                table = document.add_table(rows=1, cols=len(header))
                table.style = "Table Grid"
                for index, title in enumerate(header):
                    cell = table.rows[0].cells[index]
                    cell.text = title
                    for run in cell.paragraphs[0].runs:
                        run.bold = True
                for row in rows:
                    cells = table.add_row().cells
                    for index, value in enumerate(row):
                        cells[index].text = str(value)

    target = Path(path)
    document.save(str(target))
    return target
