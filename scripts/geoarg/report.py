"""Render a human-readable GeoArg report from a case.

One document model feeds two renderers (Markdown and Word) and two report
languages (English and Simplified Chinese). Contract content is rendered as
written; only the frame is translated. The wording is ordinary language plus
the author's own statements: the reader layer does not use engine-internal
role names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import terms
from .audit import case_digest, engine_digest
from .contract import SCHEMA_VERSION, Case
from .ground import GROUND_SCHEMA_VERSION, GroundError, ledger_sha256, load_ledger, validate_grounding
from .hitting import changing_events, decisive_events
from .independence import report as independence_report
from .judge import RULE_VERSION, judge

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
        "verdict": "conclusion",
        "rule_version": "rule version",
        "field": "declared field",
        "judgement": "Commentary",
        "judgement_authored": "commentary: written by the model; sha256: {digest}",
        "judgement_absent": "commentary: not provided",
        "derived_premise": "concluded in another argument (not expanded here)",
        "why": "Why this conclusion",
        "premises": "Premises",
        "cps": "Conditions that must hold",
        "defeaters": "Counter-evidence",
        "entailments": "Predictions that must hold",
        "independence": "Are the evidence lines independent?",
        "grounding": "Do the quotes match the source?",
        "decisive": "What would change the conclusion",
        "gaps": "What this argument cannot express",
        "audit": "Audit trail",
        "hard": "fatal issues",
        "soft": "weakening evidence",
        "pending": "still without a result",
        "none": "none",
        "id": "id",
        "state": "state",
        "test": "test",
        "severity": "severity",
        "status": "status",
        "risk": "risk",
        "evidence": "record",
        "declared_page": "declared page",
        "found_page": "page found",
        "outcome": "if this happens",
        "power": "power",
        "cost": "cost",
        "result": "conclusion becomes",
        "kind": "type",
        "counter_evidence": "Counter-evidence records",
        "description": "description",
        "n_eff": "independent evidence: about {n_eff} lines out of {total} records (mean correlation {rho})",
        "families": "fields of evidence: {families}",
        "warning": "independence note: {warning}",
        "unattached": "calibration declared but not attached: {items}",
        "no_ledger": "No quote-check record. Transcriptions are unverified.",
        "source": "Source: {path} ({pages} pages, {chars} chars, text layer: {layer}).",
        "acceptance": "Quotes that match the source: {rate} ({grounded}/{drafted} drafted quotes checked).",
        "problem": "Problem: {text}",
        "warning_row": "Warning: {text}",
        "na": "n/a",
        "decisive_intro": "Current conclusion: {verdict}. Each row is one single outcome that would change it:",
        "decisive_none": "None found. The claim is already decided, or the argument has no open item.",
        "decisive_none_defeated": "The conclusion is already refuted. It can recover only if the counter-evidence above is withdrawn or itself refuted; no other single outcome changes it.",
        "decisive_none_suspended": "The conclusion is already weakened. It recovers only if the counter-evidence above is answered or withdrawn; no other single outcome changes it.",
        "decisive_note": "Single outcomes only; combinations of weakening counter-evidence are not listed. cost is the cheapest declared test cost, in the same unit as test.yaml.",
        "brief_title": "GeoArg brief: {title}",
        "brief_line": "Conclusion {verdict}: {hard} fatal, {soft} weakening, {pending} still without a result. Quotes matching the source {rate}. Independent evidence about {n_eff} of {total}.",
        "brief_summary": "Essentials",
        "brief_more": "{more} more in the full report.",
        "brief_only": "This brief lists the essentials. Run `geoarg report <case>` for the full report.",
        "excluded": "left out of the independence count: {id} ({status})",
        "brief_warnings": "independence notes: {count}",
        "gaps_line": "recorded gaps: {count} (blocking: {blocking})",
        "no_ledger_short": "no quote-check record (transcriptions unverified)",
    },
    "zh": {
        "title": "GeoArg 报告：{title}",
        "claim": "主张",
        "statement": "陈述",
        "verdict": "结论",
        "rule_version": "规则版本",
        "field": "作者声明的领域",
        "judgement": "评述",
        "judgement_authored": "评述：由模型撰写；sha256：{digest}",
        "judgement_absent": "评述：未提供",
        "derived_premise": "结论来自另一条论证（本论证未展开）",
        "why": "为什么是这个结论",
        "premises": "前提",
        "cps": "必须成立的条件",
        "defeaters": "反面证据",
        "entailments": "必须成立的推论",
        "independence": "证据之间有多独立",
        "grounding": "引文与原文是否一致",
        "decisive": "哪些结果会改变结论",
        "gaps": "这套论证没能表达的问题",
        "audit": "审计信息",
        "hard": "足以推翻的问题",
        "soft": "削弱支持的问题",
        "pending": "还没有结果的问题",
        "none": "无",
        "id": "编号",
        "state": "状态",
        "test": "检验",
        "severity": "严重程度",
        "status": "状态",
        "risk": "风险",
        "evidence": "记录",
        "declared_page": "声明页码",
        "found_page": "实际页码",
        "outcome": "如果发生什么",
        "power": "区分力",
        "cost": "成本",
        "result": "结论会变成",
        "kind": "类型",
        "counter_evidence": "反面证据记录",
        "description": "说明",
        "n_eff": "独立证据：约 {n_eff} 条 / {total} 条记录（平均相关 {rho}）",
        "families": "证据领域：{families}",
        "warning": "独立性提示：{warning}",
        "unattached": "声明了但未附着的校准：{items}",
        "no_ledger": "没有引文核对记录，转录内容未经验证。",
        "source": "来源：{path}（{pages} 页，{chars} 字符，文本层：{layer}）。",
        "acceptance": "引文与原文一致的比例：{rate}（{grounded}/{drafted} 条草拟引文已核对）。",
        "problem": "问题：{text}",
        "warning_row": "提示：{text}",
        "na": "不适用",
        "decisive_intro": "当前结论：{verdict}。下面每一行都是一种单独就会改变结论的情况：",
        "decisive_none": "没有找到。主张已经有结论，或者这份论证没有未决项。",
        "decisive_none_defeated": "结论已经「已被推翻」。上面列出的反面证据必须被撤回或被推翻，主张才可能恢复；没有其他单事件会改变它。",
        "decisive_none_suspended": "结论已经「证据被削弱」。上面列出的反面证据必须被回应或撤回，支持才可能恢复；没有其他单事件会改变它。",
        "decisive_note": "只列单事件结果；多条削弱性反面证据同时成立的情形没有列出。成本取作者声明的最低检验成本，单位同 test.yaml。",
        "brief_title": "GeoArg 简报：{title}",
        "brief_line": "结论 {verdict}：{hard} 条足以推翻，{soft} 条削弱支持，{pending} 项还没有结果。引文与原文一致的比例 {rate}。独立证据约 {n_eff} / {total} 条。",
        "brief_summary": "要点",
        "brief_more": "另有 {more} 条见完整报告。",
        "brief_only": "本简报只列要点。完整报告运行 `geoarg report <case>`。",
        "excluded": "未计入独立性：{id}（{status}）",
        "brief_warnings": "独立性提示：{count} 条",
        "gaps_line": "记录的问题：{count} 条（阻塞：{blocking}）",
        "no_ledger_short": "没有引文核对记录（转录内容未经验证）",
    },
}


def _labels(lang: str) -> dict[str, str]:
    return LABELS.get(lang, LABELS["en"])


def _table(header: list[str], rows: list[list[str]]) -> Block:
    return ("table", (header, rows))


def _fmt(value: Any) -> str:
    """Render empty cells as a dash instead of Python's None or list repr."""
    if value is None:
        return "-"
    if isinstance(value, (list, tuple)):
        return ", ".join(_fmt(item) for item in value) if value else "-"
    text = str(value)
    return text if text else "-"


def _fmt_number(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _fmt(value)


def _judgement_blocks(judgment: str | None) -> list[Block]:
    normalized = terms.normalize_judgment(judgment)
    return [("p", paragraph) for paragraph in normalized.split("\n\n")] if normalized else []


def _audit_lines(case: Case, ledger: dict | None, labels: dict[str, str], lang: str, judgment: str | None) -> list[str]:
    zh = lang == "zh"
    lines = [
        (f"输入文件 {name}：{digest}" if zh else f"input {name}: {digest}")
        for name, digest in case_digest(case.root).items()
    ]
    lines.append((f"核对程序版本：{engine_digest()}" if zh else f"checker version: {engine_digest()}"))
    lines.append(
        (f"引文核对记录：{ledger_sha256(case.root) or labels['na']}" if zh else f"quote-check record: {ledger_sha256(case.root) or labels['na']}")
    )
    lines.append((f"论证文件格式：{SCHEMA_VERSION}" if zh else f"argument format: {SCHEMA_VERSION}"))
    lines.append((f"规则版本：{RULE_VERSION}" if zh else f"rule version: {RULE_VERSION}"))
    lines.append((f"引文核对格式版本：{GROUND_SCHEMA_VERSION}" if zh else f"quote-check format: {GROUND_SCHEMA_VERSION}"))
    lines.append(
        f"{labels['field']}：{terms.profile_label(case, lang)}"
        if zh
        else f"{labels['field']}: {terms.profile_label(case, lang)}"
    )
    if terms.normalize_judgment(judgment):
        lines.append(labels["judgement_authored"].format(digest=terms.judgment_digest(judgment)))
    else:
        lines.append(labels["judgement_absent"])
    return lines


def _grounding_problem(text: str, lang: str) -> str:
    if lang != "zh":
        return text
    if text.startswith("pdf missing"):
        return "PDF 找不到：" + text.split(":", 1)[1].strip() if ":" in text else "PDF 找不到"
    return terms.grounding_problem_text(text, lang)


def _decisive_table(
    labels: dict[str, str], case: Case, events: list[dict], lang: str
) -> Block:
    return _table(
        [labels["outcome"], labels["test"], labels["power"], labels["cost"], labels["result"]],
        [
            [
                terms.event_sentence(case, event, lang),
                _fmt(event["test"]),
                terms.power_label(event["power"], lang),
                _fmt_number(event["cost"]),
                terms.status_label(event.get("resulting_verdict"), lang),
            ]
            for event in events
        ],
    )


def build(case: Case, lang: str = "en", judgment: str | None = None) -> dict:
    """Build the document model shared by the Markdown and Word renderers."""
    L = _labels(lang)
    result = judge(case)
    indep = independence_report(case)
    decisive = decisive_events(case)
    claim = case.claim

    meta: list[tuple[str, str]] = [
        (L["claim"], f"{claim.get('id')} ({claim.get('kind')}, {claim.get('layer')})"),
        (L["statement"], str(claim.get("statement", ""))),
        (L["field"], terms.profile_label(case, lang)),
        (L["verdict"], terms.status_label(result["verdict"], lang)),
        (L["rule_version"], result["rule_version"]),
    ]

    sections: list[dict] = []
    if _judgement_blocks(judgment):
        sections.append({"heading": L["judgement"], "blocks": _judgement_blocks(judgment)})

    why: list[Block] = [("p", terms.status_explanation(result["verdict"], lang))]
    items = result.get("reason_items") or []
    if items:
        for bucket in ("hard", "soft", "pending"):
            bucket_items = [item for item in items if item.get("bucket") == bucket]
            why.append(("p", f"{terms.bucket_label(bucket, lang)}:"))
            why.append(
                (
                    "bullets",
                    [terms.item_sentence(case, item, lang) for item in bucket_items] or [L["none"]],
                )
            )
    else:
        for bucket in ("hard", "soft", "pending"):
            reasons = result["reasons"][bucket]
            why.append(("p", f"{terms.bucket_label(bucket, lang)}:"))
            why.append(("bullets", list(reasons) or [L["none"]]))
    sections.append({"heading": L["why"], "blocks": why})

    sections.append(
        {
            "heading": L["premises"],
            "blocks": [
                _table(
                    [L["id"], L["status"], L["description"]],
                    [
                        [
                            p["id"],
                            terms.chain_premise_label(p, lang),
                            p["statement"],
                        ]
                        for p in result["premises"]
                    ],
                )
            ],
        }
    )
    sections.append(
        {
            "heading": L["cps"],
            "blocks": [
                _table(
                    [L["id"], L["state"], L["test"], L["description"]],
                    [
                        [
                            _fmt(c["id"]),
                            terms.condition_state_label("cp", c["state"], lang),
                            _fmt(c["test"]),
                            terms.statement_of(case, "cp", c["id"]),
                        ]
                        for c in result["cps"]
                    ],
                )
            ],
        }
    )
    sections.append(
        {
            "heading": L["defeaters"],
            "blocks": [
                _table(
                    [L["id"], L["state"], L["severity"], L["test"], L["counter_evidence"], L["description"]],
                    [
                        [
                            _fmt(d["id"]),
                            terms.condition_state_label("defeater", d["state"], lang),
                            terms.severity_label(d["severity"], lang),
                            _fmt(d["test"]),
                            _fmt(", ".join(d.get("counter_evidence") or [])),
                            terms.statement_of(case, "defeater", d["id"]),
                        ]
                        for d in result["defeaters"]
                    ],
                )
            ],
        }
    )
    sections.append(
        {
            "heading": L["entailments"],
            "blocks": [
                _table(
                    [L["id"], L["status"], L["risk"], L["test"], L["counter_evidence"], L["description"]],
                    [
                        [
                            _fmt(e["id"]),
                            terms.condition_state_label("entailment", e["status"], lang),
                            terms.risk_label(e["risk"], lang),
                            _fmt(e["test"]),
                            _fmt(", ".join(e.get("counter_evidence") or [])),
                            terms.statement_of(case, "entailment", e["id"]),
                        ]
                        for e in result["entailments"]
                    ],
                )
            ],
        }
    )

    indep_lines = [
        L["n_eff"].format(n_eff=indep["n_eff"], total=indep["n_records"], rho=indep["mean_rho"]),
        L["families"].format(families=", ".join(indep["families"]) or L["none"]),
    ]
    indep_lines.extend(L["warning"].format(warning=warning) for warning in indep["warnings"])
    for excluded in indep["excluded_records"]:
        indep_lines.append(L["excluded"].format(id=excluded["id"], status=excluded["status"]))
    if indep["declared_calibration_not_attached"]:
        indep_lines.append(
            L["unattached"].format(items=", ".join(indep["declared_calibration_not_attached"]))
        )
    sections.append({"heading": L["independence"], "blocks": [("bullets", indep_lines)]})

    grounding_blocks: list[Block] = []
    try:
        ledger = load_ledger(case.root)
        grounding_problems, grounding_warnings = validate_grounding(case, ledger)
    except GroundError as exc:
        ledger = None
        grounding_problems = [f"quote-check record unreadable: {exc}"]
        grounding_warnings = []
    if ledger is None:
        grounding_blocks.append(("p", L["no_ledger"]))
    else:
        pdf = ledger["pdf"]
        extracted = ledger["extracted"]
        rate = ledger["acceptance_rate"]
        grounding_blocks.append(
            (
                "p",
                L["source"].format(
                    path=pdf["path"],
                    pages=extracted["pages"],
                    chars=extracted["chars"],
                    layer="yes" if extracted["text_layer"] else "no",
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
            [
                rid,
                terms.ground_status_label(entry.get("status"), lang),
                _fmt(entry.get("page")),
                _fmt(entry.get("found_page")),
            ]
            for rid, entry in ledger["records"].items()
        ]
        if rows:
            grounding_blocks.append(
                _table([L["evidence"], L["status"], L["declared_page"], L["found_page"]], rows)
            )
    for problem in grounding_problems:
        grounding_blocks.append(("p", L["problem"].format(text=_grounding_problem(problem, lang))))
    for warning in grounding_warnings:
        grounding_blocks.append(("p", L["warning_row"].format(text=_grounding_problem(warning, lang))))
    sections.append({"heading": L["grounding"], "blocks": grounding_blocks})

    decisive_blocks: list[Block] = [
        ("p", L["decisive_intro"].format(verdict=terms.status_label(decisive["base_verdict"], lang)))
    ]
    changing = changing_events(decisive["events"], decisive["base_verdict"])
    if changing:
        decisive_blocks.append(_decisive_table(L, case, changing, lang))
    elif decisive["base_verdict"] == "DEFEATED":
        decisive_blocks.append(("p", L["decisive_none_defeated"]))
    elif decisive["base_verdict"] == "SUSPENDED":
        decisive_blocks.append(("p", L["decisive_none_suspended"]))
    else:
        decisive_blocks.append(("p", L["decisive_none"]))
    decisive_blocks.append(("note", L["decisive_note"]))
    sections.append({"heading": L["decisive"], "blocks": decisive_blocks})

    gaps = case.argument.get("gaps", [])
    if gaps:
        sections.append(
            {
                "heading": L["gaps"],
                "blocks": [
                    _table(
                        [L["kind"], L["severity"], L["description"]],
                        [
                            [
                                terms.gap_kind_label(g.get("kind"), lang),
                                terms.gap_severity_label(g.get("severity"), lang),
                                g.get("description"),
                            ]
                            for g in gaps
                        ],
                    )
                ],
            }
        )

    sections.append(
        {
            "heading": L["audit"],
            "blocks": [("bullets", _audit_lines(case, ledger, L, lang, judgment))],
        }
    )

    return {
        "title": L["title"].format(title=case.argument.get("title", "untitled")),
        "meta": meta,
        "sections": sections,
    }


def build_brief(case: Case, lang: str = "en", judgment: str | None = None) -> dict:
    """Build the one-page brief: conclusion, key numbers, top decisive tests."""
    L = _labels(lang)
    result = judge(case)
    indep = independence_report(case)
    decisive = decisive_events(case)
    claim = case.claim

    meta: list[tuple[str, str]] = [
        (L["claim"], f"{claim.get('id')} ({claim.get('kind')}, {claim.get('layer')})"),
        (L["statement"], str(claim.get("statement", ""))),
        (L["field"], terms.profile_label(case, lang)),
    ]

    hard = result["reasons"]["hard"]
    soft = result["reasons"]["soft"]
    pending = result["reasons"]["pending"]

    try:
        ledger = load_ledger(case.root)
    except GroundError:
        ledger = None
    if ledger is not None:
        rate = ledger["acceptance_rate"]
        acceptance = rate if rate is not None else L["na"]
    else:
        acceptance = L["na"]

    lines: list[str] = [
        L["brief_line"].format(
            verdict=terms.status_label(result["verdict"], lang),
            hard=len(hard),
            soft=len(soft),
            pending=len(pending),
            rate=acceptance,
            n_eff=indep["n_eff"],
            total=indep["n_records"],
        )
    ]
    weak = [test for test in result["gating_tests"] if test.get("power") in (None, "none", "low")]
    if weak:
        lines.append(
            (f"判别力不足的检验：{', '.join(_fmt(test.get('id')) for test in weak)}"
             if lang == "zh"
             else f"tests with little power to distinguish: {', '.join(_fmt(test.get('id')) for test in weak)}")
        )
    if ledger is None:
        lines.append(L["no_ledger_short"])
    if indep["warnings"]:
        lines.append(L["brief_warnings"].format(count=len(indep["warnings"])))
    gaps = case.argument.get("gaps", [])
    if gaps:
        blocking = sum(1 for gap in gaps if gap.get("severity") == "blocking")
        lines.append(L["gaps_line"].format(count=len(gaps), blocking=blocking))

    blocks: list[Block] = [("bullets", lines)]
    changing = changing_events(decisive["events"], decisive["base_verdict"])
    top = changing[:3]
    if top:
        blocks.append(_decisive_table(L, case, top, lang))
        if len(changing) > len(top):
            blocks.append(("note", L["brief_more"].format(more=len(changing) - len(top))))
    elif decisive["base_verdict"] == "DEFEATED":
        blocks.append(("p", L["decisive_none_defeated"]))
    elif decisive["base_verdict"] == "SUSPENDED":
        blocks.append(("p", L["decisive_none_suspended"]))
    else:
        blocks.append(("p", L["decisive_none"]))
    blocks.append(("note", L["brief_only"]))

    sections = []
    if _judgement_blocks(judgment):
        judgement_blocks: list[Block] = list(_judgement_blocks(judgment))
        judgement_blocks.append(
            ("note", L["judgement_authored"].format(digest=terms.judgment_digest(judgment)))
        )
        sections.append({"heading": L["judgement"], "blocks": judgement_blocks})
    sections.append({"heading": L["brief_summary"], "blocks": blocks})
    return {
        "title": L["brief_title"].format(title=case.argument.get("title", "untitled")),
        "meta": meta,
        "sections": sections,
    }


def render(
    case: Case,
    lang: str = "en",
    brief: bool = False,
    judgment: str | None = None,
) -> str:
    """Render the document model as Markdown."""
    model = build_brief(case, lang, judgment) if brief else build(case, lang, judgment)
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
                if out and out[-1] != "":
                    out.append("")
                out.append("| " + " | ".join(header) + " |")
                out.append("|" + "|".join(["---"] * len(header)) + "|")
                for row in rows:
                    out.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
            elif kind == "note":
                out.append(f"_{payload}_")
        out.append("")
    return "\n".join(out)


def render_docx(
    case: Case,
    path: str | Path,
    lang: str = "en",
    brief: bool = False,
    judgment: str | None = None,
) -> Path:
    """Render the document model as a Word document and return its path."""
    try:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.shared import Pt
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RuntimeError("python-docx is required for Word reports: pip install python-docx") from exc

    model = build_brief(case, lang, judgment) if brief else build(case, lang, judgment)
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
