"""Render a human-readable GeoArg report from a case.

One document model feeds two renderers (Markdown and Word) and two report
languages (English and Simplified Chinese). Contract content is rendered as
written; only the report frame is translated.
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

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "title": "GeoArg report: {title}",
        "claim": "claim",
        "statement": "statement",
        "verdict": "verdict",
        "rule_version": "rule version",
        "flags": "flags",
        "why": "Why this verdict",
        "premises": "Premises",
        "cps": "Ceteris paribus conditions",
        "defeaters": "Defeaters",
        "entailments": "Entailments",
        "independence": "Independence",
        "grounding": "Grounding",
        "decisive": "Decisive tests",
        "gaps": "Registered gaps",
        "audit": "Audit",
        "hard": "hard defeat",
        "soft": "suspension",
        "pending": "unresolved",
        "none": "none",
        "id": "id",
        "state": "state",
        "test": "test",
        "severity": "severity",
        "status": "status",
        "risk": "risk",
        "evidence": "evidence",
        "declared_page": "declared page",
        "found_page": "found page",
        "outcome": "outcome",
        "power": "power",
        "result": "result",
        "kind": "kind",
        "description": "description",
        "n_eff": "effective independent evidence: n_eff = {n_eff} out of {total} records (mean rho = {rho})",
        "families": "families: {families}",
        "warning": "warning: {warning}",
        "unattached": "declared but unattached calibration: {items}",
        "no_ledger": "No grounding ledger. Transcription-level evidence is unverified.",
        "source": "Source: {path} ({pages} pages, {chars} chars, text layer: {layer}).",
        "acceptance": "Acceptance rate: {rate} ({grounded}/{drafted} drafted quotes grounded).",
        "problem": "Problem: {text}",
        "warning_row": "Warning: {text}",
        "na": "n/a",
        "decisive_intro": "Base verdict is {verdict}. These single outcomes would retract the claim now:",
        "decisive_none": "None found. The claim is already defeated, or the contract has no live unknown items.",
    },
    "zh": {
        "title": "GeoArg 报告：{title}",
        "claim": "主张",
        "statement": "陈述",
        "verdict": "判决",
        "rule_version": "规则版本",
        "flags": "标记",
        "why": "判决理由",
        "premises": "前提",
        "cps": "其他条件不变条件",
        "defeaters": "判废条件",
        "entailments": "可检验蕴含",
        "independence": "独立性",
        "grounding": "接地",
        "decisive": "决定性检验",
        "gaps": "已登记缺口",
        "audit": "审计",
        "hard": "硬判决",
        "soft": "中止",
        "pending": "未决",
        "none": "无",
        "id": "编号",
        "state": "状态",
        "test": "检验",
        "severity": "严重度",
        "status": "状态",
        "risk": "风险",
        "evidence": "证据",
        "declared_page": "声明页码",
        "found_page": "命中页码",
        "outcome": "结果",
        "power": "判别力",
        "result": "判决结果",
        "kind": "种类",
        "description": "描述",
        "n_eff": "有效独立证据：n_eff = {n_eff} / {total} 条记录（平均 rho = {rho}）",
        "families": "证据族：{families}",
        "warning": "警戒：{warning}",
        "unattached": "声明但未附着的校准：{items}",
        "no_ledger": "无接地台账。转录级证据未经验证。",
        "source": "来源：{path}（{pages} 页，{chars} 字符，文本层：{layer}）。",
        "acceptance": "验收率：{rate}（{grounded}/{drafted} 条草拟引文已接地）。",
        "problem": "问题：{text}",
        "warning_row": "警戒：{text}",
        "na": "不适用",
        "decisive_intro": "基础判决为 {verdict}。以下单事件结果会立即撤回该主张：",
        "decisive_none": "未找到。主张已被判决，或契约没有活的未知项。",
    },
}


def _labels(lang: str) -> dict[str, str]:
    return LABELS.get(lang, LABELS["en"])


def _table(header: list[str], rows: list[list[str]]) -> Block:
    return ("table", (header, rows))


def build(case: Case, lang: str = "en") -> dict:
    """Build the document model shared by the Markdown and Word renderers."""
    L = _labels(lang)
    result = judge(case)
    indep = independence_report(case)
    decisive = decisive_events(case)
    claim = case.claim

    meta: list[tuple[str, str]] = [
        (L["claim"], f"{claim.get('id')} ({claim.get('kind')}, {claim.get('layer')})"),
        (L["statement"], str(claim.get("statement", ""))),
        (L["verdict"], result["verdict"]),
        (L["rule_version"], result["rule_version"]),
    ]
    if result["flags"]:
        meta.append((L["flags"], "; ".join(result["flags"])))

    sections: list[dict] = []

    why: list[str] = []
    for key, title in (("hard", L["hard"]), ("soft", L["soft"]), ("pending", L["pending"])):
        reasons = result["reasons"][key]
        if reasons:
            why.extend(f"{title}: {reason}" for reason in reasons)
        else:
            why.append(f"{title}: {L['none']}")
    sections.append({"heading": L["why"], "blocks": [("bullets", why)]})

    sections.append(
        {
            "heading": L["premises"],
            "blocks": [_table([L["id"], L["state"], L["statement"]], [[p["id"], p["status"], p["statement"]] for p in result["premises"]])],
        }
    )
    sections.append(
        {
            "heading": L["cps"],
            "blocks": [_table([L["id"], L["state"], L["test"]], [[c["id"], c["state"], c["test"]] for c in result["cps"]])],
        }
    )
    sections.append(
        {
            "heading": L["defeaters"],
            "blocks": [
                _table(
                    [L["id"], L["state"], L["severity"], L["test"]],
                    [[d["id"], d["state"], d["severity"], d["test"]] for d in result["defeaters"]],
                )
            ],
        }
    )
    sections.append(
        {
            "heading": L["entailments"],
            "blocks": [
                _table(
                    [L["id"], L["status"], L["risk"], L["test"]],
                    [[e["id"], e["status"], e["risk"], e["test"]] for e in result["entailments"]],
                )
            ],
        }
    )

    indep_lines = [
        L["n_eff"].format(n_eff=indep["n_eff"], total=indep["n_records"], rho=indep["mean_rho"]),
        L["families"].format(families=", ".join(indep["families"]) or L["none"]),
    ]
    indep_lines.extend(L["warning"].format(warning=warning) for warning in indep["warnings"])
    if indep["declared_calibration_not_attached"]:
        indep_lines.append(L["unattached"].format(items=indep["declared_calibration_not_attached"]))
    sections.append({"heading": L["independence"], "blocks": [("bullets", indep_lines)]})

    grounding_blocks: list[Block] = []
    try:
        ledger = load_ledger(case.root)
        grounding_problems, grounding_warnings = validate_grounding(case, ledger)
    except GroundError as exc:
        ledger = None
        grounding_problems = [f"grounding ledger unreadable: {exc}"]
        grounding_warnings = []
    if ledger is None:
        grounding_blocks.append(("p", L["no_ledger"]))
    else:
        pdf = ledger["pdf"]
        extracted = ledger["extracted"]
        text_layer = "yes" if extracted["text_layer"] else "no"
        rate = ledger["acceptance_rate"]
        grounding_blocks.append(
            (
                "p",
                L["source"].format(
                    path=pdf["path"], pages=extracted["pages"], chars=extracted["chars"], layer=text_layer
                ),
            )
        )
        grounding_blocks.append(
            (
                "p",
                L["acceptance"].format(
                    rate=rate if rate is not None else L["na"],
                    grounded=ledger["grounded"],
                    drafted=ledger["drafted"],
                ),
            )
        )
        rows = [
            [rid, entry["status"], entry.get("page", ""), entry.get("found_page", "")]
            for rid, entry in ledger["records"].items()
        ]
        if rows:
            grounding_blocks.append(_table([L["evidence"], L["status"], L["declared_page"], L["found_page"]], rows))
    for problem in grounding_problems:
        grounding_blocks.append(("p", L["problem"].format(text=problem)))
    for warning in grounding_warnings:
        grounding_blocks.append(("p", L["warning_row"].format(text=warning)))
    sections.append({"heading": L["grounding"], "blocks": grounding_blocks})

    decisive_blocks: list[Block] = [("p", L["decisive_intro"].format(verdict=decisive["base_verdict"]))]
    if decisive["events"]:
        decisive_blocks.append(
            _table(
                [L["outcome"], L["test"], L["power"], L["result"]],
                [[e["label"], e["test"], e["power"], e["resulting_verdict"]] for e in decisive["events"]],
            )
        )
    else:
        decisive_blocks.append(("p", L["decisive_none"]))
    decisive_blocks.append(("note", decisive["note"]))
    sections.append({"heading": L["decisive"], "blocks": decisive_blocks})

    gaps = case.argument.get("gaps", [])
    if gaps:
        sections.append(
            {
                "heading": L["gaps"],
                "blocks": [
                    _table(
                        [L["kind"], L["severity"], L["description"]],
                        [[g.get("kind"), g.get("severity"), g.get("description")] for g in gaps],
                    )
                ],
            }
        )

    audit_lines = [f"{name}: {digest}" for name, digest in case_digest(case.root).items()]
    sections.append({"heading": L["audit"], "blocks": [("bullets", audit_lines)]})

    return {
        "title": L["title"].format(title=case.argument.get("title", "untitled")),
        "meta": meta,
        "sections": sections,
    }


def render(case: Case, lang: str = "en") -> str:
    """Render the document model as Markdown."""
    model = build(case, lang)
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


def render_docx(case: Case, path: str | Path, lang: str = "en") -> Path:
    """Render the document model as a Word document and return its path."""
    try:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.shared import Pt
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RuntimeError("python-docx is required for Word reports: pip install python-docx") from exc

    model = build(case, lang)
    document = Document()
    document.core_properties.title = model["title"]
    document.add_heading(model["title"], level=0)
    normal = document.styles["Normal"]
    if lang == "zh":
        normal.font.name = "Calibri"
        normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "Microsoft YaHei")
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
