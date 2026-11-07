"""Plain reader-facing wording shared by the cards and the report.

The engine keeps its own state values in the ledgers. The reader layer does not
translate engine roles into invented jargon: it uses ordinary language and the
author's own statements, so the result can be read without a glossary from this
tool.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .contract import Case

DEFAULT_PROFILE = "general-geology"

PROFILE_LABELS: dict[str, dict[str, str]] = {
    "general-geology": {"en": "general geology", "zh": "普通地质学"},
    "geochronology": {"en": "geochronology", "zh": "年代学"},
    "planetary-geology": {"en": "planetary geology", "zh": "行星地质学"},
    "tectonics": {"en": "tectonics", "zh": "构造地质学"},
}

STATUS_LABELS: dict[str, dict[str, str]] = {
    "UNTESTED": {"en": "not tested", "zh": "未检验"},
    "UNDETERMINED": {"en": "undetermined", "zh": "无法判定"},
    "SUSPENDED": {"en": "weakened by counter-evidence", "zh": "被反面证据削弱"},
    "DEFEATED": {"en": "refuted", "zh": "已被推翻"},
    "SUPPORTED": {"en": "supported", "zh": "成立"},
}

STATUS_EXPLANATIONS: dict[str, dict[str, str]] = {
    "UNTESTED": {
        "en": "No test has a result yet. This is not weak support; it is no information.",
        "zh": "还没有任何检验取得结果。这不是支持弱，而是没有信息。",
    },
    "UNDETERMINED": {
        "en": "Some conditions or predictions still have no result, so the claim cannot be decided yet.",
        "zh": "还有条件或推论没有结果，所以现在无法判定。",
    },
    "SUSPENDED": {
        "en": "A counter-argument is established and weakens the claim until it is answered.",
        "zh": "已有反面证据成立，在它被回应之前，主张的支持被削弱。",
    },
    "DEFEATED": {
        "en": "A fatal counter-argument or a failed high-risk prediction is established. Unless it is withdrawn, more support cannot repair the claim.",
        "zh": "已有致命的反面证据或高风险推论失败。除非它被撤回，补充支持也不能修复这个主张。",
    },
    "SUPPORTED": {
        "en": "Every condition has a result and every referenced test passed.",
        "zh": "各条件都有结果，且所引用的检验均已通过。",
    },
}

BUCKET_LABELS: dict[str, dict[str, str]] = {
    "hard": {"en": "fatal issues", "zh": "足以推翻结论的问题"},
    "soft": {"en": "weakening evidence", "zh": "会削弱结论的证据"},
    "pending": {"en": "still without a result", "zh": "还没有结果的问题"},
}

SEVERITY_LABELS: dict[str, dict[str, str]] = {
    "fatal": {"en": "fatal", "zh": "足以单独推翻"},
    "degrading": {"en": "weakening", "zh": "削弱支持"},
}

RISK_LABELS: dict[str, dict[str, str]] = {
    "high": {"en": "high", "zh": "高"},
    "medium": {"en": "medium", "zh": "中"},
    "low": {"en": "low", "zh": "低"},
}

POWER_LABELS: dict[str, dict[str, str]] = {
    "high": {"en": "high", "zh": "高"},
    "medium": {"en": "medium", "zh": "中"},
    "low": {"en": "low", "zh": "低"},
    "none": {"en": "none", "zh": "无"},
}

CLAIM_KIND_LABELS: dict[str, dict[str, str]] = {
    "reconstruction": {"en": "reconstruction", "zh": "重建类"},
    "timing": {"en": "timing", "zh": "时间关系"},
    "correlation": {"en": "correlation", "zh": "相关性"},
    "mechanism": {"en": "mechanism", "zh": "机制"},
    "existence": {"en": "existence", "zh": "存在性"},
    "classification": {"en": "classification", "zh": "分类归属"},
}

TEXT_LAYER_LABELS: dict[str, dict[str, str]] = {
    "yes": {"en": "yes", "zh": "是"},
    "no": {"en": "no", "zh": "否"},
}

INDEPENDENCE_CLASS_LABELS: dict[str, dict[str, str]] = {
    "shared-calibration": {"en": "shared calibration", "zh": "共用校准来源"},
    "data": {"en": "independent data", "zh": "独立数据"},
    "method": {"en": "same method", "zh": "同一方法"},
    "physical": {"en": "independent physical evidence", "zh": "独立物性证据"},
}

GAP_KIND_LABELS: dict[str, dict[str, str]] = {
    "cannot-express": {"en": "cannot express", "zh": "表达不了"},
    "ambiguous": {"en": "ambiguous", "zh": "含义不清"},
    "missing-field": {"en": "missing field", "zh": "缺少字段"},
    "overspecified": {"en": "overspecified", "zh": "写得太死"},
    "other": {"en": "other", "zh": "其他"},
}

GAP_SEVERITY_LABELS: dict[str, dict[str, str]] = {
    "blocking": {"en": "blocking", "zh": "阻塞"},
    "annoying": {"en": "annoying", "zh": "麻烦"},
    "minor": {"en": "minor", "zh": "次要"},
}

GROUND_STATUS_LABELS: dict[str, dict[str, str]] = {
    "grounded": {"en": "matches the source", "zh": "与原文一致"},
    "page-mismatch": {"en": "different page", "zh": "页码不对"},
    "not-found": {"en": "not found in the source", "zh": "原文里找不到"},
    "not-groundable": {"en": "no text layer in the PDF", "zh": "PDF 没有文字层"},
    "no-locator": {"en": "no quote", "zh": "没有引文"},
}

PREMISE_STATUS_LABELS: dict[str, dict[str, str]] = {
    "supported": {"en": "evidence accepted", "zh": "证据已接受"},
    "disputed": {"en": "evidence disputed", "zh": "证据有争议"},
    "unsupported": {"en": "evidence withdrawn", "zh": "证据已被撤回"},
    "missing-evidence": {"en": "no matching evidence", "zh": "找不到对应证据"},
    "undetermined": {"en": "evidence state unknown", "zh": "证据状态未知"},
    "chain-supported": {"en": "linked argument supported", "zh": "被引用的论证成立"},
    "chain-disputed": {"en": "linked argument weakened", "zh": "被引用的论证被削弱"},
    "chain-unsupported": {"en": "linked argument refuted", "zh": "被引用的论证已被推翻"},
    "chain-undetermined": {"en": "linked argument not decided", "zh": "被引用的论证无法判定"},
    "chain-unresolved": {"en": "linked argument not found", "zh": "找不到被引用的论证"},
    "chain-cycle": {"en": "argument chain loops", "zh": "论证链成环"},
}

CONDITION_STATE_LABELS: dict[str, dict[str, dict[str, str]]] = {
    "cp": {
        "unknown": {"en": "not tested", "zh": "尚未检验"},
        "holds": {"en": "stated to hold", "zh": "声明成立"},
        "fails": {"en": "fails", "zh": "不成立"},
    },
    "defeater": {
        "unknown": {"en": "not tested", "zh": "尚未检验"},
        "established": {"en": "established", "zh": "成立"},
        "refuted": {"en": "ruled out", "zh": "已排除"},
    },
    "entailment": {
        "untested": {"en": "not tested", "zh": "尚未检验"},
        "passed": {"en": "passed", "zh": "已通过"},
        "failed": {"en": "fails", "zh": "不成立"},
    },
}


def _pick(table: dict[str, dict[str, str]], key: Any, lang: str, fallback: str = "") -> str:
    entry = table.get(key) if isinstance(key, str) else None
    if entry is None:
        return str(key) if key is not None else fallback
    return entry.get(lang) or entry.get("en") or str(key)


def status_label(verdict: str, lang: str = "en") -> str:
    return _pick(STATUS_LABELS, verdict, lang)


def status_explanation(verdict: str, lang: str = "en") -> str:
    entry = STATUS_EXPLANATIONS.get(verdict)
    if entry is None:
        return ""
    return entry.get(lang) or entry.get("en") or ""


def bucket_label(bucket: str, lang: str = "en") -> str:
    return _pick(BUCKET_LABELS, bucket, lang)


def severity_label(value: Any, lang: str = "en") -> str:
    return _pick(SEVERITY_LABELS, value, lang)


def risk_label(value: Any, lang: str = "en") -> str:
    return _pick(RISK_LABELS, value, lang)


def power_label(value: Any, lang: str = "en") -> str:
    """Plain word for a test's discriminating power; empty cells stay dashes."""
    if value is None or value == "":
        return "-"
    return _pick(POWER_LABELS, value, lang)


def claim_kind_label(value: Any, lang: str = "en") -> str:
    return _pick(CLAIM_KIND_LABELS, value, lang)


def claim_meta(claim: Any, lang: str = "en") -> str:
    """The claim's id, kind and author-declared layer, in ordinary words."""
    if not isinstance(claim, dict):
        return ""
    ident = str(claim.get("id") or "")
    kind = claim_kind_label(claim.get("kind"), lang)
    layer = str(claim.get("layer") or "")
    if lang == "zh":
        parts = [part for part in (kind, f"层级 {layer}" if layer else "") if part]
        return f"{ident}（{'；'.join(parts)}）" if parts else ident
    parts = [part for part in (kind, f"layer {layer}" if layer else "") if part]
    return f"{ident} ({'; '.join(parts)})" if parts else ident


def text_layer_label(value: Any, lang: str = "en") -> str:
    return _pick(TEXT_LAYER_LABELS, "yes" if value else "no", lang)


def independence_warning(item: dict[str, Any], lang: str = "en") -> str:
    """One independence warning in plain words; unknown codes pass through."""
    code = item.get("code")
    zh = lang == "zh"
    if code == "shared-sources-not-calibration":
        ident = item.get("id")
        shared = ", ".join(str(source) for source in item.get("shared") or [])
        cls = item.get("class") or ""
        if zh:
            class_label = _pick(INDEPENDENCE_CLASS_LABELS, cls, lang) or str(cls)
            return (
                f"记录 {ident} 与其他记录共用来源 {shared}，却被标成“{class_label}”；"
                "共用同一套校准来源的记录不能当成独立证据，要按同一套校准来数。"
            )
        return (
            f"{ident}: shares {item.get('shared')} with other records but is labelled {cls!r}; "
            "shared calibration must be counted at the calibration level"
        )
    if code == "physical-shares-family":
        ident = item.get("id")
        family = item.get("family")
        others = item.get("others") or []
        if zh:
            return (
                f"记录 {ident} 被标成“独立物性证据”，但它和 {others} 属于同一证据家族 "
                f"{family}。"
            )
        return f"{ident}: labelled physical but shares evidence family {family} with {others}"
    return str(item.get("text") or "")


def gap_kind_label(value: Any, lang: str = "en") -> str:
    return _pick(GAP_KIND_LABELS, value, lang)


def gap_severity_label(value: Any, lang: str = "en") -> str:
    return _pick(GAP_SEVERITY_LABELS, value, lang)


def ground_status_label(value: Any, lang: str = "en") -> str:
    return _pick(GROUND_STATUS_LABELS, value, lang)


def premise_status_label(value: Any, lang: str = "en") -> str:
    return _pick(PREMISE_STATUS_LABELS, value, lang)


def chain_premise_label(premise: dict[str, Any], lang: str = "en") -> str:
    """Label a premise row, resolving a derived premise through its target."""
    status = premise.get("status") or ""
    if status == "chain-unresolved":
        return "找不到被引用的论证" if lang == "zh" else "linked argument not found"
    if status == "chain-cycle":
        return "论证链成环" if lang == "zh" else "argument chain loops"
    chain = premise.get("chain") or {}
    verdict = chain.get("verdict")
    if status.startswith("chain-") and verdict:
        prefix = "被引用的论证" if lang == "zh" else "linked argument "
        return prefix + status_label(verdict, lang)
    return premise_status_label(status, lang)


def condition_state_label(kind: str, value: Any, lang: str = "en") -> str:
    table = CONDITION_STATE_LABELS.get(kind, {})
    return _pick(table, value, lang)


def grounding_problem_text(text: str, lang: str = "en") -> str:
    """Readable versions of the quote-check problem strings the engine emits."""
    if lang != "zh":
        return text
    if text.startswith("quote-check record unreadable: "):
        return "引文核对记录读不了：" + text.split(": ", 1)[1]
    if text.startswith("grounding ledger read"):
        return "引文核对记录读不了"
    if "is not grounded" in text:
        rid = text.split("evidence ", 1)[1].split(":", 1)[0] if "evidence " in text else text
        return f"记录 {rid} 的引文没有通过核对"
    if text.startswith("grounding is stale"):
        return "引文在核对之后改过，需要重新核对"
    if text.startswith("pdf changed since grounding"):
        return "PDF 在核对之后变过，需要重新核对"
    if "accepted transcription-level quote is not grounded" in text:
        return "有转录级引文还没有核对，请运行 geoarg ground"
    return text


def profile_label(case: Case, lang: str = "en") -> str:
    """The field the author declared, or an honest 'not declared' note."""
    declared = case.argument.get("profile") or {}
    primary = declared.get("primary") if isinstance(declared, dict) else None
    if not primary:
        return "not declared" if lang != "zh" else "未声明"
    return PROFILE_LABELS.get(primary, {}).get(lang) or str(primary)


def _conditions(case: Case) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for item in case.argument.get("premises", []):
        index[("premise", item.get("id"))] = item
    inference = case.argument.get("inference", {})
    for item in inference.get("cp", []):
        index[("cp", item.get("id"))] = item
    for item in inference.get("defeaters", []):
        index[("defeater", item.get("id"))] = item
    for item in case.argument.get("entailments", []):
        index[("entailment", item.get("id"))] = item
    return index


def statement_of(case: Case, kind: str, ident: str) -> str:
    item = _conditions(case).get((kind, ident)) or {}
    return str(item.get("statement") or "")


def _claim_word(kind: str, lang: str) -> str:
    if lang == "zh":
        return {"premise": "证据已接受", "cp": "成立", "defeater": "已排除", "entailment": "已通过"}.get(
            kind, "成立"
        )
    return {"premise": "accepted", "cp": "holds", "defeater": "refuted", "entailment": "passed"}.get(
        kind, "holds"
    )


def _detail_tail(kind: str, detail: str, lang: str) -> str:
    claimed = _claim_word(kind, lang)
    zh = lang == "zh"
    if detail == "none-power":
        return (
            f"作者填的是{claimed}，但唯一有结果的检验没有区分力，不能作为依据"
            if zh
            else f"the author says it {claimed}, but the only test with a result cannot distinguish and cannot back it"
        )
    if detail == "failed":
        return (
            f"作者填的是{claimed}，但所引用的检验失败了，不能支撑它"
            if zh
            else f"the author says it {claimed}, but a referenced test failed"
        )
    return (
        f"作者填的是{claimed}，但还没有检验结果支撑它"
        if zh
        else f"the author says it {claimed}, but no test result backs it"
    )


def _strip_end(text: str) -> str:
    """Drop sentence-final punctuation so the renderer adds exactly one stop."""
    return text.rstrip().rstrip("。.;；!！?？,，、 ")


def item_sentence(
    case: Case, item: dict[str, Any], lang: str = "en", omit_untested: bool = False
) -> str:
    """One reason in plain words: the author's statement plus what is missing.

    ``omit_untested`` drops the bare "not tested yet" tail, for lists that
    already say so in their heading and would otherwise repeat it per item.
    """
    kind = str(item.get("kind") or "")
    ident = str(item.get("id") or "")
    state = item.get("state")
    zh = lang == "zh"
    statement = _strip_end(statement_of(case, kind, ident))
    base = f"{ident}：{statement}" if (zh and statement) else (f"{ident}: {statement}" if statement else ident)

    if kind == "premise":
        chain = item.get("chain") if isinstance(item.get("chain"), dict) else None
        if state in ("chain-unresolved", "chain-cycle"):
            if state == "chain-cycle":
                tail = (
                    "论证链成环，无法给出结论"
                    if zh
                    else "the argument chain loops, so no conclusion can be drawn"
                )
            else:
                tail = (
                    "找不到被引用的论证"
                    if zh
                    else "the referenced argument was not found"
                )
        elif isinstance(state, str) and state.startswith("chain-"):
            target = str((chain or {}).get("argument_id") or (chain or {}).get("case") or "")
            verdict = (chain or {}).get("verdict")
            label = status_label(str(verdict), lang) if verdict else premise_status_label(state, lang)
            where = (f"（{target}）" if target else "") if zh else (f" ({target})" if target else "")
            if zh:
                tail = f"结论来自另一条论证{where}：{label}"
                if state == "chain-unsupported":
                    tail += "，所以这条前提不成立"
                elif state == "chain-supported":
                    tail += "，这条前提成立"
            else:
                tail = f"conclusion of another argument{where}: {label}"
                if state == "chain-unsupported":
                    tail += ", so this premise fails"
                elif state == "chain-supported":
                    tail += ", so this premise is satisfied"
        elif item.get("derived"):
            tail = (
                "结论来自另一条论证，这条论证没有展开那一步"
                if zh
                else "the conclusion comes from another argument, which this argument does not expand"
            )
        elif state == "unsupported":
            tail = "证据已被撤回" if zh else "the evidence has been withdrawn"
        elif state == "missing-evidence":
            tail = "找不到对应证据" if zh else "no matching evidence record"
        elif state == "disputed":
            tail = "证据有争议" if zh else "the evidence is disputed"
        else:
            tail = "证据状态未知" if zh else "the evidence state is unknown"
    elif kind == "cp":
        if state == "fails":
            tail = "不成立" if zh else "it fails"
        elif item.get("detail"):
            tail = _detail_tail(kind, str(item["detail"]), lang)
        else:
            tail = "" if omit_untested else ("尚未检验" if zh else "it has not been tested")
    elif kind == "defeater":
        if state == "established":
            sev = severity_label(item.get("severity"), lang)
            tail = f"成立（{sev}）" if zh else f"it is established ({sev})"
        elif item.get("detail"):
            tail = _detail_tail(kind, str(item["detail"]), lang)
        else:
            tail = "" if omit_untested else ("尚未检验" if zh else "it has not been tested")
    elif kind == "entailment":
        if state == "failed":
            risk = risk_label(item.get("risk"), lang)
            tail = f"不成立（风险：{risk}）" if zh else f"it fails (risk: {risk})"
        elif item.get("detail"):
            tail = _detail_tail(kind, str(item["detail"]), lang)
        else:
            tail = "" if omit_untested else ("尚未检验" if zh else "it has not been tested")
    else:
        tail = str(state or "")

    if not tail:
        return f"{base}。" if zh else f"{base}."
    return f"{base}；{tail}。" if zh else f"{base}: {tail}."


def event_sentence(case: Case, event: dict[str, Any], lang: str = "en") -> str:
    """One single outcome that would change the conclusion, in plain words."""
    kind = str(event.get("kind") or "")
    ident = str(event.get("id") or "")
    statement = _strip_end(statement_of(case, kind, ident))
    zh = lang == "zh"
    if zh:
        quoted = f"「{statement}」" if statement else ""
        if kind == "premise":
            return f"如果 {ident}{quoted}的证据被撤回"
        if kind == "cp":
            return f"如果 {ident}{quoted}不成立"
        if kind == "defeater":
            return f"如果 {ident}{quoted}成立"
        if kind == "entailment":
            return f"如果 {ident}{quoted}不成立"
        return f"如果 {ident} 的状态改变"
    quoted = f"“{statement}”" if statement else ""
    if kind == "premise":
        return f"If the evidence for {ident}{quoted} is withdrawn"
    if kind == "cp":
        return f"If {ident}{quoted} fails"
    if kind == "defeater":
        return f"If {ident}{quoted} is established"
    if kind == "entailment":
        return f"If {ident}{quoted} fails"
    return f"If the state of {ident} changes"


def normalize_judgment(text: str | None) -> str:
    """Normalise the model-written commentary once, for display and for hashing."""
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [paragraph.strip() for paragraph in normalized.split("\n\n")]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def judgment_digest(text: str | None) -> str:
    """sha256 of the normalised commentary, the text a reader can re-hash."""
    normalized = normalize_judgment(text)
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
