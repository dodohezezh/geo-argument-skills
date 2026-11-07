"""Reader-facing pages.

A researcher and a reviewer need different amounts of the same evidence: the
researcher needs the next action, the reviewer needs the reasons. Both pages
draw every fact from the same contract and the same engine calls, so the
conclusion never depends on the reader; only the selection and the order of
the facts change.

The wording is ordinary language plus the author's own statements. The engine
does not invent role names for the reader layer, and the machine values stay in
the ledgers.

The prose paragraph at the top of a page is authored by the model, not by this
module: the engine supplies the numbers, the model writes the commentary. The
page records the sha256 of that paragraph so a reader can tell prose from
computation.
"""

from __future__ import annotations

from typing import Any

from . import terms
from .audit import case_digest, engine_digest
from .contract import SCHEMA_VERSION, Case
from .ground import GROUND_SCHEMA_VERSION, GroundError, ledger_sha256, load_ledger, validate_grounding
from .hitting import changing_events, decisive_events
from .independence import report as independence_report
from .judge import RULE_VERSION, judge

ROLES = ("researcher", "reviewer")


def _labels(lang: str) -> dict[str, str]:
    return PAGES.get(lang, PAGES["en"])


PAGES: dict[str, dict[str, str]] = {
    "en": {
        "title": "GeoArg conclusion: {title}",
        "claim": "claim",
        "verdict": "conclusion",
        "audience": "reader",
        "audience_researcher": "researcher (self-check)",
        "audience_reviewer": "reviewer (assessment)",
        "field": "declared field",
        "rule_version": "rule version",
        "judgement_heading": "Commentary",
        "judgement_authored": "commentary: written by the model; sha256 of the commentary text: {digest}",
        "judgement_absent": "commentary: not provided",
        "verdict_heading": "Conclusion",
        "counts": "{verdict}: {hard} fatal, {soft} weakening, {pending} still without a result.",
        "unbacked_count": "states without a test result behind them: {count}",
        "next_heading": "What to check next",
        "next_intro": "The conclusion moves only when a test produces a result. Start with the unfinished test that can change it most at the lowest cost:",
        "next_none": "No unfinished test is left; there is no next test to run for this conclusion.",
        "next_more": "{more} more in the reviewer page.",
        "next_more_tests": "{more} more unfinished tests.",
        "test_what": "what it checks",
        "gaps_heading": "What this argument cannot express",
        "gaps_none": "None recorded.",
        "gaps_note": "These gaps are part of the result.",
        "numbers_heading": "Numbers",
        "numbers_grounding": "quotes that match the source: {rate} ({grounded}/{drafted})",
        "numbers_no_ledger": "quotes: no check record (transcriptions unverified)",
        "numbers_excluded": "records left out of the independence count: {count}",
        "numbers_warnings": "independence notes: {count}",
        "reproduce_heading": "How to check this yourself",
        "reproduce_line": "geoarg verify {case}",
        "reproduce_note": "The committed conclusion and this page must agree.",
        "reasons_heading": "Conclusion and reasons",
        "reasons_none": "No reason recorded.",
        "defence_heading": "Why the claim is not established",
        "defence_heading_supported": "Why it holds",
        "defence_heading_defeated": "What refutes it",
        "defence_heading_suspended": "What weakens it",
        "defence_none": "No condition is missing a test; the open items above hold the conclusion.",
        "supported_by": "tests that carry the conclusion: {tests}",
        "weak": "test with little power to distinguish: {test} ({power})",
        "no_gating": "no test bears on the conclusion",
        "paths_heading": "What would change the conclusion",
        "paths_intro": "Current conclusion: {verdict}. Each row is one single outcome that would change it:",
        "paths_note": "Single outcomes only; combinations of weakening counter-evidence are not listed. cost is the cheapest declared test cost, in the same unit as test.yaml.",
        "paths_none_defeated": "The conclusion is already refuted. It can recover only if the counter-evidence above is withdrawn or itself refuted; no other single outcome changes it.",
        "paths_none_suspended": "The conclusion is already weakened by counter-evidence. It recovers only if the counter-evidence above is answered or withdrawn; no other single outcome changes it.",
        "evidence_heading": "Evidence and independence",
        "chain_intro": "This argument counts {n} evidence records into its independence estimate; the shared sources and classes the author declared imply a mean correlation of {rho}, leaving about {n_eff} independent lines of evidence.",
        "chain_calibration": "{count} record(s) share a source or a calibration.",
        "chain_excluded": "{count} record(s) are left out because their status is disputed or retracted.",
        "chain_unattached": "The calibration the author declared ({items}) is not attached to any evidence record.",
        "caveat": "This conclusion covers only the conditions and evidence written into this argument. The tool does not rerun experiments and does not decide whether the claim is true.",
        "n_eff": "independent evidence: about {n_eff} lines (out of {total} records; mean correlation {rho})",
        "families": "fields of evidence: {families}",
        "warning": "independence note: {warning}",
        "excluded": "left out of the independence count: {id} ({status})",
        "unattached": "calibration sources declared but not attached to any evidence record: {items}",
        "outcome": "if this happens",
        "test": "test",
        "power": "power",
        "cost": "cost",
        "result": "conclusion becomes",
        "kind": "type",
        "severity": "severity",
        "description": "description",
        "evidence": "record",
        "status": "status",
        "declared_page": "declared page",
        "found_page": "page found",
        "no_ledger": "No quote-check record. Transcriptions are unverified.",
        "source": "Source: {path} ({pages} pages, {chars} chars, text layer: {layer}).",
        "acceptance": "Quotes that match the source: {rate} ({grounded}/{drafted} quotes checked).",
        "problem": "Problem: {text}",
        "warning_row": "Warning: {text}",
        "na": "n/a",
    },
    "zh": {
        "title": "GeoArg 结论：{title}",
        "claim": "主张",
        "verdict": "结论",
        "audience": "读者",
        "audience_researcher": "研究者（自查）",
        "audience_reviewer": "评审者（评估）",
        "field": "作者声明的领域",
        "rule_version": "规则版本",
        "judgement_heading": "评述",
        "judgement_authored": "评述：由模型撰写；对评述文字的 sha256：{digest}",
        "judgement_absent": "评述：未提供",
        "verdict_heading": "结论",
        "counts": "结论：{verdict}；{hard} 条足以推翻，{soft} 条削弱支持，{pending} 项还没有结果。",
        "unbacked_count": "缺少检验结果支撑的判定：{count} 条",
        "next_heading": "接下来该做什么",
        "next_intro": "只有检验出了结果，结论才会变。先做还没做、区分力高、成本低的：",
        "next_none": "没有尚未完成的检验；这个结论目前没有可执行的下一步检验。",
        "next_more": "另有 {more} 条见评审者版。",
        "next_more_tests": "另有 {more} 条还没做的检验。",
        "test_what": "要确认什么",
        "gaps_heading": "这套论证没能表达的问题",
        "gaps_none": "没有记录。",
        "gaps_note": "这些问题是结论的一部分。",
        "numbers_heading": "数字",
        "numbers_grounding": "引文与原文一致的比例：{rate}（{grounded}/{drafted}）",
        "numbers_no_ledger": "引文核对：没有核对记录（转录内容未经验证）",
        "numbers_excluded": "未计入独立性的记录：{count} 条",
        "numbers_warnings": "独立性提示：{count} 条",
        "reproduce_heading": "如何自行核对",
        "reproduce_line": "geoarg verify {case}",
        "reproduce_note": "已提交的结论应与本页一致。",
        "reasons_heading": "结论与理由",
        "reasons_none": "没有记录理由。",
        "defence_heading": "为什么还不能确认",
        "defence_heading_supported": "为什么成立",
        "defence_heading_defeated": "是什么推翻了它",
        "defence_heading_suspended": "是什么削弱了它",
        "defence_none": "没有缺少检验的判定；结论由上面的未决项卡住。",
        "supported_by": "支撑结论的检验：{tests}",
        "weak": "区分力不足的检验：{test}（{power}）",
        "no_gating": "没有检验与结论相关，结论缺少依据",
        "paths_heading": "哪些结果会改变结论",
        "paths_intro": "当前结论：{verdict}。下面每一行都是一种单独就会改变结论的情况：",
        "paths_note": "只列单事件结果；多条削弱性反面证据同时成立的情形没有列出。成本取作者声明的最低检验成本，单位同 test.yaml。",
        "paths_none_defeated": "结论已经被推翻。上面列出的反面证据必须被撤回或被推翻，主张才可能恢复；没有其他单事件会改变它。",
        "paths_none_suspended": "结论已经被反面证据削弱。上面列出的反面证据必须被回应或撤回，支持才可能恢复；没有其他单事件会改变它。",
        "evidence_heading": "证据与独立性",
        "chain_intro": "这份论证把 {n} 条证据记录计入独立性估算；按作者声明的共同来源和类别，平均相关为 {rho}，约合 {n_eff} 条相互独立的证据。",
        "chain_calibration": "其中 {count} 条记录因共享来源或校准而不独立。",
        "chain_excluded": "另有 {count} 条记录因状态为争议或撤回而未计入。",
        "chain_unattached": "作者声明的校准来源（{items}）没有挂到任何证据记录上。",
        "caveat": "这个结论只覆盖这份论证写下的条件和证据；工具不重跑实验，也不判定主张真假。",
        "n_eff": "独立证据：约 {n_eff} 条（共 {total} 条记录，平均相关 {rho}）",
        "families": "证据领域：{families}",
        "warning": "独立性提示：{warning}",
        "excluded": "未计入独立性：{id}（{status}）",
        "unattached": "作者声明了、但没有挂到任何证据记录上的校准来源：{items}",
        "outcome": "如果发生什么",
        "test": "检验",
        "power": "区分力",
        "cost": "成本",
        "result": "结论会变成",
        "kind": "类型",
        "severity": "严重程度",
        "description": "说明",
        "evidence": "记录",
        "status": "状态",
        "declared_page": "声明页码",
        "found_page": "实际页码",
        "no_ledger": "没有引文核对记录，转录内容未经验证。",
        "source": "来源：{path}（{pages} 页，{chars} 字符，文本层：{layer}）。",
        "acceptance": "引文与原文一致的比例：{rate}（{grounded}/{drafted} 条引文已核对）。",
        "problem": "问题：{text}",
        "warning_row": "提示：{text}",
        "na": "不适用",
    },
}


def _fmt(value: Any) -> str:
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


def _event_row(labels: dict[str, str], case: Case, event: dict, lang: str) -> list[str]:
    return [
        terms.event_sentence(case, event, lang),
        _fmt(event.get("test")),
        terms.power_label(event.get("power"), lang),
        _fmt_number(event.get("cost")),
        terms.status_label(event.get("resulting_verdict"), lang),
    ]


def _event_table(
    labels: dict[str, str], case: Case, events: list[dict], lang: str
) -> tuple[list[str], list[list[str]]]:
    header = [labels["outcome"], labels["test"], labels["power"], labels["cost"], labels["result"]]
    return header, [_event_row(labels, case, event, lang) for event in events]


_POWER_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3, None: 4}


def _next_test_blocks(
    case: Case, labels: dict[str, str], lang: str, result: dict
) -> list[tuple[str, Any]]:
    """Unfinished gating tests, the checks a researcher can actually run next."""
    records = {
        record.get("id"): record
        for record in case.tests.get("records", [])
        if isinstance(record, dict)
    }
    candidates: list[tuple[str, str, Any, Any]] = []
    for gate in result["gating_tests"]:
        test_id = gate.get("id")
        if not isinstance(test_id, str):
            continue
        if gate.get("status") in ("passed", "failed"):
            continue
        record = records.get(test_id, {})
        candidates.append(
            (
                test_id,
                str(record.get("name") or "-"),
                gate.get("power"),
                record.get("cost"),
            )
        )
    candidates.sort(
        key=lambda row: (
            _POWER_ORDER.get(row[2], 4),
            row[3] if isinstance(row[3], (int, float)) and not isinstance(row[3], bool) else float("inf"),
            row[0],
        )
    )

    blocks: list[tuple[str, Any]] = [("p", labels["next_intro"])]
    if not candidates:
        blocks.append(("p", labels["next_none"]))
        return blocks
    top = candidates[:3]
    header = [labels["test"], labels["test_what"], labels["power"], labels["cost"]]
    rows = [
        [test_id, name, terms.power_label(power, lang), _fmt_number(cost)]
        for test_id, name, power, cost in top
    ]
    blocks.append(("table", (header, rows)))
    if len(candidates) > len(top):
        blocks.append(("note", labels["next_more_tests"].format(more=len(candidates) - len(top))))
    return blocks


def _gaps_block(case: Case, labels: dict[str, str], lang: str) -> list[tuple[str, Any]]:
    gaps = case.argument.get("gaps", [])
    if not gaps:
        return [("p", labels["gaps_none"])]
    order = {"blocking": 0, "annoying": 1, "minor": 2}
    ordered = sorted(gaps, key=lambda gap: order.get(gap.get("severity"), 3))
    rows = [
        [
            terms.gap_kind_label(gap.get("kind"), lang),
            terms.gap_severity_label(gap.get("severity"), lang),
            _fmt(gap.get("description")),
        ]
        for gap in ordered
    ]
    return [("table", ([labels["kind"], labels["severity"], labels["description"]], rows))]


def _grounding(case: Case):
    try:
        ledger = load_ledger(case.root)
        problems, warnings = validate_grounding(case, ledger)
    except GroundError as exc:
        ledger = None
        problems = [f"quote-check record unreadable: {exc}"]
        warnings = []
    return ledger, problems, warnings


def _grounding_blocks(
    case: Case,
    labels: dict[str, str],
    lang: str,
    ledger: dict | None,
    problems: list[str],
    warnings: list[str],
) -> list[tuple[str, Any]]:
    blocks: list[tuple[str, Any]] = []
    if ledger is None:
        blocks.append(("p", labels["no_ledger"]))
    else:
        pdf = ledger["pdf"]
        extracted = ledger["extracted"]
        blocks.append(
            (
                "p",
                labels["source"].format(
                    path=pdf["path"],
                    pages=extracted["pages"],
                    chars=extracted["chars"],
                    layer=terms.text_layer_label(extracted["text_layer"], lang),
                ),
            )
        )
        rate = ledger["acceptance_rate"]
        blocks.append(
            (
                "p",
                labels["acceptance"].format(
                    rate=rate if rate is not None else labels["na"],
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
            blocks.append(
                (
                    "table",
                    (
                        [labels["evidence"], labels["status"], labels["declared_page"], labels["found_page"]],
                        rows,
                    ),
                )
            )
    for problem in problems:
        blocks.append(("p", labels["problem"].format(text=problem)))
    for warning in warnings:
        blocks.append(("p", labels["warning_row"].format(text=warning)))
    return blocks


def _audit_lines(
    case: Case, ledger: dict | None, labels: dict[str, str], lang: str, judgment: str | None
) -> list[str]:
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


def _judgement_block(judgment: str | None) -> list[tuple[str, Any]]:
    normalized = terms.normalize_judgment(judgment)
    if not normalized:
        return []
    return [("p", paragraph) for paragraph in normalized.split("\n\n")]


def _verdict_lines(result: dict, labels: dict[str, str], lang: str) -> list[str]:
    lines = [
        labels["counts"].format(
            verdict=terms.status_label(result["verdict"], lang),
            hard=len(result["reasons"]["hard"]),
            soft=len(result["reasons"]["soft"]),
            pending=len(result["reasons"]["pending"]),
        )
    ]
    explanation = terms.status_explanation(result["verdict"], lang)
    if explanation:
        lines.append(explanation)
    if result["unbacked"]:
        lines.append(labels["unbacked_count"].format(count=len(result["unbacked"])))
    return lines


def _reason_items(result: dict) -> list[dict]:
    order = {"hard": 0, "soft": 1, "pending": 2}
    return sorted(result.get("reason_items") or [], key=lambda item: order.get(item.get("bucket"), 3))


def _researcher_sections(
    case: Case,
    labels: dict[str, str],
    lang: str,
    result: dict,
    indep: dict,
    ledger: dict | None,
    judgment: str | None,
) -> list[tuple[str, list[tuple[str, Any]]]]:
    next_blocks = _next_test_blocks(case, labels, lang, result)

    numbers: list[str] = []
    if ledger is None:
        numbers.append(labels["numbers_no_ledger"])
    else:
        rate = ledger["acceptance_rate"]
        numbers.append(
            labels["numbers_grounding"].format(
                rate=rate if rate is not None else labels["na"],
                grounded=ledger["grounded"],
                drafted=ledger["drafted"],
            )
        )
    numbers.append(
        labels["n_eff"].format(n_eff=indep["n_eff"], total=indep["n_records"], rho=indep["mean_rho"])
    )
    if indep["excluded_records"]:
        numbers.append(labels["numbers_excluded"].format(count=len(indep["excluded_records"])))
    if indep["warnings"]:
        numbers.append(labels["numbers_warnings"].format(count=len(indep["warnings"])))

    reproduce = [labels["reproduce_line"].format(case=case.root.name)]
    if terms.normalize_judgment(judgment):
        reproduce.append(labels["judgement_authored"].format(digest=terms.judgment_digest(judgment)))

    sections: list[tuple[str, list[tuple[str, Any]]]] = []
    if terms.normalize_judgment(judgment):
        sections.append((labels["judgement_heading"], _judgement_block(judgment)))
    sections.extend(
        [
            (labels["verdict_heading"], [("bullets", _verdict_lines(result, labels, lang))]),
            (labels["next_heading"], next_blocks),
            (labels["gaps_heading"], _gaps_block(case, labels, lang)),
            (labels["numbers_heading"], [("bullets", numbers)]),
            (
                labels["reproduce_heading"],
                [("bullets", reproduce), ("note", labels["reproduce_note"])],
            ),
        ]
    )
    return sections


def _evidence_chain(labels: dict[str, str], lang: str, indep: dict) -> list[str]:
    lines = [
        labels["chain_intro"].format(
            n=indep["n_records"], rho=indep["mean_rho"], n_eff=indep["n_eff"]
        )
    ]
    if indep["warnings"]:
        lines.append(labels["chain_calibration"].format(count=len(indep["warnings"])))
    if indep["excluded_records"]:
        lines.append(labels["chain_excluded"].format(count=len(indep["excluded_records"])))
    if indep["declared_calibration_not_attached"]:
        lines.append(
            labels["chain_unattached"].format(items=", ".join(indep["declared_calibration_not_attached"]))
        )
    return lines


def _reviewer_sections(
    case: Case,
    labels: dict[str, str],
    lang: str,
    result: dict,
    indep: dict,
    decisive: dict,
    ledger: dict | None,
    grounding_problems: list[str],
    grounding_warnings: list[str],
    judgment: str | None,
) -> list[tuple[str, list[tuple[str, Any]]]]:
    verdict = result["verdict"]
    reason_blocks: list[tuple[str, Any]] = [("bullets", _verdict_lines(result, labels, lang))]
    items = _reason_items(result)
    if items:
        # For a decided verdict the fatal or weakening items are explained in the
        # section below; repeating them here would print the same sentence twice.
        shown_buckets = ("pending",) if verdict in ("DEFEATED", "SUSPENDED") else ("hard", "soft", "pending")
        for bucket in shown_buckets:
            bucket_items = [item for item in items if item.get("bucket") == bucket]
            if bucket_items:
                reason_blocks.append(("p", f"{terms.bucket_label(bucket, lang)}:"))
                reason_blocks.append(
                    (
                        "bullets",
                        [terms.item_sentence(case, item, lang) for item in bucket_items],
                    )
                )
    else:
        reason_blocks.append(("p", labels["reasons_none"]))

    weak = [test for test in result["gating_tests"] if test.get("power") in (None, "none", "low")]
    passed = [test for test in result["gating_tests"] if test.get("status") == "passed"]

    if verdict == "SUPPORTED":
        heading = labels["defence_heading_supported"]
        defence: list[str] = []
        if passed:
            defence.append(labels["supported_by"].format(tests=", ".join(_fmt(test.get("id")) for test in passed)))
        defence.extend(
            labels["weak"].format(test=_fmt(test.get("id")), power=terms.power_label(test.get("power"), lang))
            for test in weak
        )
        if not result["gating_tests"]:
            defence.append(labels["no_gating"])
    elif verdict in ("DEFEATED", "SUSPENDED"):
        heading = labels["defence_heading_defeated" if verdict == "DEFEATED" else "defence_heading_suspended"]
        decisive_items = [item for item in items if item.get("bucket") in ("hard", "soft")]
        defence = [terms.item_sentence(case, item, lang) for item in decisive_items]
        defence.extend(
            labels["weak"].format(test=_fmt(test.get("id")), power=terms.power_label(test.get("power"), lang))
            for test in weak
        )
    else:
        heading = labels["defence_heading"]
        unbacked_items = [
            item for item in items if item.get("bucket") == "pending" and item.get("detail")
        ]
        defence = [terms.item_sentence(case, item, lang) for item in unbacked_items]
        defence.extend(
            labels["weak"].format(test=_fmt(test.get("id")), power=terms.power_label(test.get("power"), lang))
            for test in weak
        )
        if not result["gating_tests"]:
            defence.append(labels["no_gating"])
    if not defence:
        defence.append(labels["defence_none"])

    events = changing_events(decisive["events"], decisive["base_verdict"])
    path_blocks: list[tuple[str, Any]] = [
        ("p", labels["paths_intro"].format(verdict=terms.status_label(decisive["base_verdict"], lang)))
    ]
    if events:
        path_blocks.append(("table", _event_table(labels, case, events, lang)))
    elif decisive["base_verdict"] == "DEFEATED":
        path_blocks.append(("p", labels["paths_none_defeated"]))
    elif decisive["base_verdict"] == "SUSPENDED":
        path_blocks.append(("p", labels["paths_none_suspended"]))
    else:
        path_blocks.append(("p", labels["next_none"]))
    path_blocks.append(("note", labels["paths_note"]))

    evidence_blocks: list[tuple[str, Any]] = [
        ("p", paragraph) for paragraph in _evidence_chain(labels, lang, indep)
    ]
    evidence_lines = [
        labels["n_eff"].format(n_eff=indep["n_eff"], total=indep["n_records"], rho=indep["mean_rho"]),
        labels["families"].format(families=", ".join(indep["families"]) or labels["na"]),
    ]
    warning_texts = [
        terms.independence_warning(item, lang) for item in (indep.get("warning_items") or [])
    ] or list(indep["warnings"])
    evidence_lines.extend(labels["warning"].format(warning=warning) for warning in warning_texts)
    for excluded in indep["excluded_records"]:
        evidence_lines.append(
            labels["excluded"].format(id=excluded["id"], status=excluded["status"])
        )
    if indep["declared_calibration_not_attached"]:
        evidence_lines.append(
            labels["unattached"].format(items=", ".join(indep["declared_calibration_not_attached"]))
        )
    evidence_blocks.append(("bullets", evidence_lines))
    evidence_blocks.extend(_grounding_blocks(case, labels, lang, ledger, grounding_problems, grounding_warnings))

    sections: list[tuple[str, list[tuple[str, Any]]]] = []
    if terms.normalize_judgment(judgment):
        sections.append((labels["judgement_heading"], _judgement_block(judgment)))
    sections.extend(
        [
            (labels["reasons_heading"], reason_blocks),
            (heading, [("bullets", defence)]),
            (labels["paths_heading"], path_blocks),
            (labels["evidence_heading"], evidence_blocks),
            (
                labels["gaps_heading"],
                _gaps_block(case, labels, lang) + [("note", labels["gaps_note"])],
            ),
            (
                labels["reproduce_heading"],
                [
                    (
                        "bullets",
                        _audit_lines(case, ledger, labels, lang, judgment)
                        + [labels["reproduce_line"].format(case=case.root.name)],
                    ),
                    ("note", labels["caveat"]),
                ],
            ),
        ]
    )
    return sections


def build_card(
    case: Case,
    lang: str = "en",
    role: str = "researcher",
    judgment: str | None = None,
) -> dict:
    """Build the page model for one reader role."""
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}, not {role!r}")
    lang = lang if lang in ("en", "zh") else "en"
    labels = _labels(lang)
    result = judge(case)
    indep = independence_report(case)
    decisive = decisive_events(case)
    ledger, grounding_problems, grounding_warnings = _grounding(case)

    claim = case.claim
    meta = [
        (labels["claim"], terms.claim_meta(claim, lang)),
        (labels["verdict"], terms.status_label(result["verdict"], lang)),
        (labels["audience"], labels[f"audience_{role}"]),
        (labels["field"], terms.profile_label(case, lang)),
        (labels["rule_version"], result["rule_version"]),
    ]

    if role == "researcher":
        sections = _researcher_sections(case, labels, lang, result, indep, ledger, judgment)
    else:
        sections = _reviewer_sections(
            case,
            labels,
            lang,
            result,
            indep,
            decisive,
            ledger,
            grounding_problems,
            grounding_warnings,
            judgment,
        )

    return {
        "title": labels["title"].format(title=case.argument.get("title", "untitled")),
        "meta": meta,
        "sections": sections,
    }


def render_card(
    case: Case,
    lang: str = "en",
    role: str = "researcher",
    judgment: str | None = None,
) -> str:
    """Render the page as Markdown."""
    model = build_card(case, lang, role, judgment)
    out: list[str] = [f"# {model['title']}", ""]
    for label, value in model["meta"]:
        out.append(f"- {label}: {value}")
    out.append("")
    for heading, blocks in model["sections"]:
        out.append(f"## {heading}")
        for kind, payload in blocks:
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
