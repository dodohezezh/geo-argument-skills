"""Deterministic SVG argument figures for GeoArg cases.

Four figures are generated:

``argument-status.svg``
    Reason buckets per item type (premises, conditions, defeaters, entailments).
``independence.svg``
    Reported ``n_eff`` against an assumed pairwise ``rho``.
``decision-value.svg``
    Leave-one-out evidence classes plus test power against cost.
``evidence-coverage.svg``
    Declared coverage against detectability for each evidence record, or the
    evidence-status distribution when coverage fractions are not declared.

The visual rules are adapted from the nature-figure-craft skill
(https://github.com/Alto-R/nature-figure-craft; code MIT, docs CC BY 4.0): one
claim per figure, landed 88/180 mm widths, a minimum landed type size, a
semantic palette, and a grayscale readability check. No code is copied and no
plotting dependency is added. The output is deterministic: identical inputs give
byte-identical SVG files.

Figures are presentation only. They never enter ``engine_digest``, a verdict, a
committed record, a bundle conclusion, or a trust-chain check.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import figstyle, figsvg
from .contract import Case, load_case
from .impact import ablation
from .independence import report as independence_report
from .judge import judge
from .terms import status_label

FIGURE_SCHEMA_VERSION = "geoarg/figures/0.1"
MANIFEST_FILE = "figures.json"

FIGURES: tuple[tuple[str, str, str], ...] = (
    ("argument-status", "Argument status", "\u8bba\u8bc1\u72b6\u6001"),
    ("independence", "Independence", "\u72ec\u7acb\u6027"),
    ("decision-value", "Decision value", "\u51b3\u7b56\u4ef7\u503c"),
    ("evidence-coverage", "Evidence coverage", "\u8bc1\u636e\u8986\u76d6"),
)

LIMITS = (
    "Figures are a rendering of interpreted states, not new evidence.",
    "No probability is encoded or implied; counts and ranges are descriptive.",
    "Figures are not part of engine_digest, a verdict, or a trust-chain check.",
    "Land using the 88 mm / 180 mm widths; smaller or larger copies change the landed type size.",
)


def _is_zh(lang: str) -> bool:
    return str(lang).lower().startswith("zh")


def _labels(lang: str) -> dict[str, str]:
    if _is_zh(lang):
        return {
            "status_title": "\u8bba\u8bc1\u72b6\u6001\uff1a{claim}\uff08{verdict}\uff09",
            "status_note": "\u8ba1\u6570\u662f\u7ecf\u89e3\u91ca\u7684\u72b6\u6001\uff0c\u56fe\u4e2d\u4e0d\u542b\u6982\u7387\u3002",
            "premises": "\u524d\u63d0",
            "cp": "\u6761\u4ef6",
            "defeaters": "\u53cd\u9762\u8bc1\u636e",
            "entailments": "\u5fc5\u987b\u6210\u7acb\u7684\u63a8\u8bba",
            "independence_title": "\u72ec\u7acb\u6027\u538b\u529b\u6d4b\u8bd5\uff1an_eff \u4e0e\u5047\u5b9a rho",
            "independence_note": "\u58f0\u660e\u5b57\u6bb5\uff0c\u975e\u5b9e\u6d4b\u3002",
            "assumed_rho": "\u5047\u5b9a\u7684\u4e24\u4e24 rho",
            "n_eff": "n_eff",
            "decision_title": "\u51b3\u7b56\u4ef7\u503c\uff1a\u7559\u4e00\u6cd5",
            "evidence_panel": "\u8bc1\u636e",
            "tests_panel": "\u68c0\u9a8c\uff1a\u5224\u522b\u529b\u4e0e\u6210\u672c",
            "cost": "\u6210\u672c",
            "power": "\u5224\u522b\u529b",
            "decision_note": "\u7559\u4e00\u6cd5\u6d88\u878d\uff1b\u4e0d\u4f30\u6982\u7387\u3002",
            "coverage_title": "\u8bc1\u636e\u8986\u76d6\u4e0e\u53ef\u68c0\u6d4b\u6027",
            "coverage": "\u8986\u76d6\u5206\u6570",
            "detectability": "\u53ef\u68c0\u6d4b\u6027",
            "coverage_note": "\u6765\u81ea evidence.yaml \u7684\u58f0\u660e\u503c\u3002",
            "status_note_coverage": "\u672c\u6848\u4f8b\u672a\u58f0\u660e\u8986\u76d6\u5206\u6570\uff0c\u6539\u753b\u8bc1\u636e\u72b6\u6001\u3002",
            "evidence_status": "\u8bc1\u636e\u72b6\u6001",
        }
    return {
        "status_title": "Argument status: {claim} ({verdict})",
        "status_note": "Counts are interpreted states; the figure encodes no probability.",
        "premises": "Premises",
        "cp": "Conditions",
        "defeaters": "Defeaters",
        "entailments": "Entailments",
        "independence_title": "Independence stress: n_eff vs assumed rho",
        "independence_note": "Declared fields, not measured.",
        "assumed_rho": "assumed pairwise rho",
        "n_eff": "n_eff",
        "decision_title": "Decision value: leave-one-out",
        "evidence_panel": "Evidence",
        "tests_panel": "Tests: power vs cost",
        "cost": "cost",
        "power": "power",
        "decision_note": "Leave-one-out ablation; no probability is estimated.",
        "coverage_title": "Evidence coverage and detectability",
        "coverage": "coverage fraction",
        "detectability": "detectability",
        "coverage_note": "Declared values from evidence.yaml.",
        "status_note_coverage": "No coverage fractions declared; showing the evidence-status distribution.",
        "evidence_status": "Evidence status",
    }


def _claim_label(case: Case) -> str:
    return str(case.claim.get("statement") or case.claim.get("title") or case.claim.get("id") or "claim")


def _claim_id(case: Case) -> str:
    return str(case.claim.get("id") or "")


def _clip(value: object, limit: int = 110) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "\u2026"


def _items(case: Case) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for premise in case.argument.get("premises") or []:
        items.append(
            {
                "kind": "premise",
                "id": str(premise.get("id") or ""),
                "state": str(premise.get("status") or "untested"),
                "derived": premise.get("kind") == "derived",
            }
        )
    inference = case.argument.get("inference") or {}
    for condition in inference.get("cp") or []:
        items.append(
            {
                "kind": "cp",
                "id": str(condition.get("id") or ""),
                "state": str(condition.get("state") or "unknown"),
            }
        )
    for defeater in inference.get("defeaters") or []:
        items.append(
            {
                "kind": "defeater",
                "id": str(defeater.get("id") or ""),
                "state": str(defeater.get("state") or "unknown"),
                "severity": str(defeater.get("severity") or "degrading"),
            }
        )
    for entailment in case.argument.get("entailments") or []:
        items.append(
            {
                "kind": "entailment",
                "id": str(entailment.get("id") or ""),
                "state": str(entailment.get("status") or "untested"),
                "risk": str(entailment.get("risk") or "medium"),
            }
        )
    return items


def _default_bucket(item: dict[str, Any]) -> str:
    kind = item["kind"]
    state = item["state"]
    if kind == "premise":
        if state in ("supported", "chain-supported"):
            return "ok"
        if state in ("unsupported", "missing-evidence", "chain-unsupported"):
            return "hard"
        if state in ("disputed", "chain-disputed"):
            return "soft"
        return "pending"
    if kind == "cp":
        return {"holds": "ok", "fails": "hard"}.get(state, "pending")
    if kind == "defeater":
        if state == "established":
            return "hard" if item.get("severity") == "fatal" else "soft"
        if state == "refuted":
            return "ok"
        return "pending"
    if kind == "entailment":
        if state == "failed":
            return "hard" if item.get("risk") == "high" else "soft"
        if state == "passed":
            return "ok"
        return "pending"
    return "pending"


def _status_svg(case: Case, result: dict[str, Any], lang: str) -> figsvg.Svg:
    labels = _labels(lang)
    items = _items(case)
    reason_buckets = {
        (str(entry.get("kind") or ""), str(entry.get("id") or "")): str(entry.get("bucket") or "pending")
        for entry in result.get("reason_items") or []
    }
    groups = (
        ("premises", [item for item in items if item["kind"] == "premise"]),
        ("cp", [item for item in items if item["kind"] == "cp"]),
        ("defeaters", [item for item in items if item["kind"] == "defeater"]),
        ("entailments", [item for item in items if item["kind"] == "entailment"]),
    )
    verdict = str(result.get("verdict") or "UNDETERMINED")
    title = labels["status_title"].format(claim=_claim_id(case) or "claim", verdict=status_label(verdict, lang))
    svg = figsvg.Svg(
        figstyle.DOUBLE_MM,
        100.0,
        title=title,
        description=_claim_label(case),
        lang=lang,
    )
    svg.text_top(4.0, 3.0, title, size_pt=9.5, weight="bold")
    svg.text_top(4.0, 9.2, _clip(_claim_label(case)), size_pt=7.2, fill=figstyle.MUTED)

    x0 = 40.0
    bar_width = 118.0
    top = 19.0
    row_height = 13.0
    for index, (key, group) in enumerate(groups):
        y = top + index * row_height
        total = len(group)
        svg.text_top(4.0, y + 2.6, f"{labels[key]} ({total})", size_pt=7.6, weight="bold")
        if not total:
            svg.line(x0, y + 5.5, x0 + bar_width, y + 5.5, figstyle.RULE, width=0.2, dash="1,1")
            svg.text_top(x0 + 2.0, y + 3.2, "0", size_pt=7.0, fill=figstyle.MUTED)
            continue
        counts = {bucket: 0 for bucket in figstyle.BUCKET_ORDER}
        for item in group:
            bucket = reason_buckets.get((item["kind"], item["id"])) or _default_bucket(item)
            counts[bucket] = counts.get(bucket, 0) + 1
        cursor = x0
        for bucket in figstyle.BUCKET_ORDER:
            count = counts.get(bucket, 0)
            if not count:
                continue
            segment = bar_width * count / total
            svg.rect(cursor, y + 1.4, segment, 8.4, figstyle.BUCKET_COLORS[bucket], stroke=figstyle.PAPER, stroke_width=0.3)
            if segment >= 9.0:
                svg.text_top(
                    cursor + segment / 2.0,
                    y + 3.0,
                    str(count),
                    size_pt=7.0,
                    anchor="middle",
                    fill="#ffffff",
                    weight="bold",
                )
            cursor += segment
        svg.line(cursor, y + 1.4, x0 + bar_width, y + 1.4, figstyle.PAPER, width=0.0)

    legend_y = 74.0
    for index, bucket in enumerate(figstyle.BUCKET_ORDER):
        x = x0 + index * 33.0
        svg.rect(x, legend_y, 3.0, 3.0, figstyle.BUCKET_COLORS[bucket])
        svg.text_top(x + 4.2, legend_y - 0.2, figstyle.bucket_label(bucket, "zh" if _is_zh(lang) else "en"), size_pt=7.0, fill=figstyle.MUTED)

    svg.text_top(4.0, 88.5, labels["status_note"], size_pt=6.8, fill=figstyle.MUTED, italic=True)
    return svg


def _independence_svg(case: Case, lang: str) -> figsvg.Svg:
    labels = _labels(lang)
    payload = independence_report(case)
    stress = payload.get("stress") or {}
    scenarios = [entry for entry in stress.get("scenarios") or [] if "multiplier" not in entry]
    points = [(float(entry.get("assumed_rho") or 0.0), float(entry.get("n_eff") or 0.0)) for entry in scenarios]
    values = [value for _, value in points] + [float(payload.get("n_eff") or 1.0), float(payload.get("n_records") or 1.0)]
    high = max(values + [1.2]) + 0.35
    low = max(0.0, min(values) - 0.35)

    svg = figsvg.Svg(figstyle.SINGLE_MM, 66.0, title=labels["independence_title"], description=labels["independence_note"], lang=lang)
    svg.text_top(4.0, 3.0, labels["independence_title"], size_pt=8.4, weight="bold")
    reported = float(payload.get("n_eff") or 0.0)
    rho = float(payload.get("mean_rho") or 0.0)
    span = f"{stress.get('min', reported):g}\u2013{stress.get('max', reported):g}"
    svg.text_top(4.0, 9.4, f"n_eff {reported:g} at rho {rho:g}; range {span}", size_pt=7.0, fill=figstyle.MUTED)

    x0, x1 = 16.0, 82.0
    y0, y1 = 18.0, 48.0
    svg.line(x0, y1, x1, y1, figstyle.RULE, width=0.28)
    svg.line(x0, y0, x0, y1, figstyle.RULE, width=0.28)
    ticks_x = (0.0, 0.25, 0.5, 0.75, 1.0)
    for tick in ticks_x:
        x = x0 + (x1 - x0) * tick
        svg.line(x, y1, x, y1 + 1.2, figstyle.RULE, width=0.25)
        svg.text_top(x, y1 + 2.4, f"{tick:g}", size_pt=6.8, anchor="middle", fill=figstyle.MUTED)
    tick_values = sorted({1.0, round(high, 2)})
    for tick in tick_values:
        y = y1 - (y1 - y0) * (tick - low) / (high - low)
        svg.line(x0 - 1.2, y, x0, y, figstyle.RULE, width=0.25)
        svg.text_top(x0 - 2.0, y - 1.1, f"{tick:g}", size_pt=6.8, anchor="end", fill=figstyle.MUTED)
    mapped = [
        (x0 + (x1 - x0) * min(max(rho_value, 0.0), 1.0), y1 - (y1 - y0) * (value - low) / (high - low))
        for rho_value, value in points
    ]
    svg.polyline(mapped, "#0072B2", width=0.5)
    for x_value, y_value in mapped:
        svg.circle(x_value, y_value, 0.9, "#0072B2")
    marker_x = x0 + (x1 - x0) * min(max(rho, 0.0), 1.0)
    marker_y = y1 - (y1 - y0) * (reported - low) / (high - low)
    svg.circle(marker_x, marker_y, 2.0, figstyle.PAPER, stroke="#D55E00", stroke_width=0.5)
    svg.text_top(marker_x + 2.6, marker_y - 1.4, f"{reported:g}", size_pt=7.0, fill="#D55E00", weight="bold")

    svg.text_top(x0, y1 + 7.4, labels["assumed_rho"], size_pt=6.8, fill=figstyle.MUTED)
    svg.text_top(x0 - 12.0, y0 - 3.4, labels["n_eff"], size_pt=6.8, fill=figstyle.MUTED)
    svg.text_top(4.0, 58.0, labels["independence_note"], size_pt=6.6, fill=figstyle.MUTED, italic=True)
    return svg


def _decision_svg(case: Case, lang: str) -> figsvg.Svg:
    labels = _labels(lang)
    payload = ablation(case)
    evidence_rows = list(payload.get("evidence") or [])
    test_rows = list(payload.get("tests") or [])
    evidence_counts = {name: 0 for name in figstyle.CLASS_ORDER}
    for row in evidence_rows:
        name = str(row.get("class") or "unused")
        evidence_counts[name] = evidence_counts.get(name, 0) + 1
    test_by_id = {str(test.get("id")): test for test in case.tests.get("records") or []}
    svg = figsvg.Svg(figstyle.DOUBLE_MM, 86.0, title=labels["decision_title"], description=_claim_label(case), lang=lang)
    svg.text_top(4.0, 3.0, labels["decision_title"], size_pt=9.0, weight="bold")

    # Left panel: evidence leave-one-out classes.
    svg.text_top(9.0, 11.0, labels["evidence_panel"], size_pt=7.8, weight="bold")
    bar_x = 44.0
    bar_max = 38.0
    classes = [name for name in figstyle.CLASS_ORDER if name in ("decisive", "backing", "redundant", "unused")]
    maximum = max([evidence_counts.get(name, 0) for name in classes] + [1])
    for index, name in enumerate(classes):
        y = 20.0 + index * 11.0
        count = evidence_counts.get(name, 0)
        svg.text_top(9.0, y + 2.2, name, size_pt=7.0, fill=figstyle.MUTED)
        width = bar_max * count / maximum
        if width > 0:
            svg.rect(bar_x, y + 1.0, width, 6.2, figstyle.CLASS_COLORS[name])
        svg.text_top(bar_x + bar_max + 2.0, y + 2.2, str(count), size_pt=7.0, fill=figstyle.INK)

    # Right panel: test power against cost.
    svg.text_top(96.0, 11.0, labels["tests_panel"], size_pt=7.8, weight="bold")
    px0, px1 = 104.0, 170.0
    py0, py1 = 22.0, 56.0
    svg.line(px0, py1, px1, py1, figstyle.RULE, width=0.28)
    svg.line(px0, py0, px0, py1, figstyle.RULE, width=0.28)
    costs = [float(test.get("cost") or 0) for test in case.tests.get("records") or []]
    max_cost = max(costs + [1.0])
    for power_rank in range(4):
        y = py1 - (py1 - py0) * power_rank / 3.0
        svg.line(px0 - 1.0, y, px0, y, figstyle.RULE, width=0.22)
        svg.text_top(px0 - 2.0, y - 1.1, figstyle.power_label(power_rank, "zh" if _is_zh(lang) else "en"), size_pt=6.6, anchor="end", fill=figstyle.MUTED)
    for cost in range(1, int(max_cost) + 1):
        x = px0 + (px1 - px0) * ((cost - 1.0) / max(max_cost - 1.0, 1.0))
        svg.text_top(x, py1 + 2.6, str(cost), size_pt=6.6, anchor="middle", fill=figstyle.MUTED)
    svg.text_top((px0 + px1) / 2.0, py1 + 6.4, labels["cost"], size_pt=6.8, anchor="middle", fill=figstyle.MUTED)
    svg.text_top(px0 - 10.0, py0 - 3.6, labels["power"], size_pt=6.8, fill=figstyle.MUTED)
    for row in test_rows:
        test_id = str(row.get("id") or "")
        test = test_by_id.get(test_id) or {}
        rank = figstyle.POWER_RANK.get(str(test.get("discriminating_power") or "none"), 0)
        cost = float(test.get("cost") or 0)
        x = px0 + (px1 - px0) * ((cost - 1.0) / max(max_cost - 1.0, 1.0)) if max_cost > 1 else (px0 + px1) / 2.0
        y = py1 - (py1 - py0) * rank / 3.0
        colour = figstyle.CLASS_COLORS.get(str(row.get("class") or "untapped"), "#C8C8C8")
        svg.circle(x, y, 1.7, colour, stroke=figstyle.PAPER, stroke_width=0.3)
        svg.text_top(x + 2.3, y - 1.2, test_id, size_pt=6.6, fill=figstyle.MUTED)

    svg.text_top(4.0, 76.0, labels["decision_note"], size_pt=6.8, fill=figstyle.MUTED, italic=True)
    return svg


def _coverage_points(case: Case) -> list[tuple[float, float, str, str]]:
    points: list[tuple[float, float, str, str]] = []
    for record in case.evidence.get("records") or []:
        coverage = record.get("coverage") or {}
        fraction = coverage.get("coverage_fraction")
        detectability = coverage.get("detectability")
        if isinstance(fraction, (int, float)) and isinstance(detectability, (int, float)):
            points.append((float(fraction), float(detectability), str(record.get("status") or "undetermined"), str(record.get("id") or "")))
    return points


def _coverage_svg(case: Case, lang: str) -> figsvg.Svg:
    labels = _labels(lang)
    points = _coverage_points(case)
    svg = figsvg.Svg(figstyle.SINGLE_MM, 66.0, title=labels["coverage_title"], description=labels["coverage_note"], lang=lang)
    svg.text_top(4.0, 3.0, labels["coverage_title"], size_pt=8.4, weight="bold")
    if len(points) < 2:
        svg.text_top(4.0, 9.2, labels["status_note_coverage"], size_pt=6.8, fill=figstyle.MUTED)
        counts: dict[str, int] = {}
        for record in case.evidence.get("records") or []:
            name = str(record.get("status") or "undetermined")
            counts[name] = counts.get(name, 0) + 1
        names = sorted(counts)
        maximum = max(counts.values(), default=1)
        for index, name in enumerate(names):
            y = 20.0 + index * 9.0
            svg.text_top(4.0, y + 2.0, name, size_pt=6.8, fill=figstyle.MUTED)
            width = 52.0 * counts[name] / maximum
            svg.rect(34.0, y + 0.8, width, 5.4, figstyle.EVIDENCE_STATUS_COLORS.get(name, "#8A8A8A"))
            svg.text_top(34.0 + width + 1.4, y + 2.0, str(counts[name]), size_pt=6.8)
        svg.text_top(4.0, 58.0, labels["coverage_note"], size_pt=6.6, fill=figstyle.MUTED, italic=True)
        return svg

    x0, x1 = 20.0, 82.0
    y0, y1 = 16.0, 46.0
    svg.line(x0, y1, x1, y1, figstyle.RULE, width=0.28)
    svg.line(x0, y0, x0, y1, figstyle.RULE, width=0.28)
    for tick in (0.0, 0.5, 1.0):
        x = x0 + (x1 - x0) * tick
        svg.text_top(x, y1 + 2.4, f"{tick:g}", size_pt=6.6, anchor="middle", fill=figstyle.MUTED)
        y = y1 - (y1 - y0) * tick
        svg.text_top(x0 - 2.0, y - 1.0, f"{tick:g}", size_pt=6.6, anchor="end", fill=figstyle.MUTED)
    svg.text_top((x0 + x1) / 2.0, y1 + 7.2, labels["coverage"], size_pt=6.8, anchor="middle", fill=figstyle.MUTED)
    svg.text_top(x0 - 14.0, y0 - 3.6, labels["detectability"], size_pt=6.8, fill=figstyle.MUTED)
    for fraction, detectability, status, record_id in points:
        x = x0 + (x1 - x0) * min(max(fraction, 0.0), 1.0)
        y = y1 - (y1 - y0) * min(max(detectability, 0.0), 1.0)
        svg.circle(x, y, 1.8, figstyle.EVIDENCE_STATUS_COLORS.get(status, "#8A8A8A"), stroke=figstyle.PAPER, stroke_width=0.3)
        svg.text_top(x + 2.2, y - 1.0, _clip(record_id, 22), size_pt=6.4, fill=figstyle.MUTED)
    svg.text_top(4.0, 58.0, labels["coverage_note"], size_pt=6.6, fill=figstyle.MUTED, italic=True)
    return svg


def build_figures(case_or_root: Case | str | Path, out_dir: str | Path, *, lang: str = "en") -> dict[str, Any]:
    """Write the four SVG figures plus ``figures.json``; return the manifest."""
    case = case_or_root if isinstance(case_or_root, Case) else load_case(case_or_root)
    root = Path(case.root)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        result = judge(case)
    except Exception:  # a broken chain must not hide the other figures
        result = {"verdict": "UNDETERMINED"}
    builders = {
        "argument-status": lambda: _status_svg(case, result, lang),
        "independence": lambda: _independence_svg(case, lang),
        "decision-value": lambda: _decision_svg(case, lang),
        "evidence-coverage": lambda: _coverage_svg(case, lang),
    }
    figures: list[dict[str, Any]] = []
    for name, title_en, title_zh in FIGURES:
        svg = builders[name]()
        text = svg.render()
        data = text.encode("utf-8")
        target = out / f"{name}.svg"
        target.write_bytes(data)
        figures.append(
            {
                "name": name,
                "title": title_zh if _is_zh(lang) else title_en,
                "file": target.name,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest: dict[str, Any] = {
        "schema_version": FIGURE_SCHEMA_VERSION,
        "case": str(root),
        "claim_id": _claim_id(case),
        "verdict": str(result.get("verdict") or ""),
        "lang": "zh" if _is_zh(lang) else "en",
        "figures": figures,
        "limits": list(LIMITS),
    }
    (out / MANIFEST_FILE).write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def load_figures(figures_dir: str | Path) -> list[tuple[str, str]]:
    """Read ``(name, svg_text)`` pairs for report embedding; empty when absent."""
    root = Path(figures_dir)
    if not root.is_dir():
        return []
    names: list[str] = []
    manifest_path = root / MANIFEST_FILE
    if manifest_path.is_file():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            names = [str(entry.get("file")) for entry in payload.get("figures") or [] if entry.get("file")]
    if not names:
        names = [path.name for path in sorted(root.glob("*.svg"))]
    figures: list[tuple[str, str]] = []
    for name in names:
        path = root / name
        if path.is_file():
            figures.append((Path(name).stem, path.read_text(encoding="utf-8")))
    return figures
