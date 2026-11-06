"""Figure style rules for GeoArg reports.

The rules are adapted from the nature-figure-craft skill
(https://github.com/Alto-R/nature-figure-craft; code MIT, documentation CC BY
4.0): one claim per figure, landed widths (88 mm single column, 180 mm double
column), a minimum landed type size, a semantic palette, and a grayscale
readability check. No code is copied: GeoArg writes its own deterministic SVG,
so figures need no plotting dependency and are byte-identical across runs.

Figures are presentation only. They never enter ``engine_digest``, a verdict, a
committed record, a bundle conclusion, or a trust-chain check.
"""

from __future__ import annotations

SINGLE_MM = 88.0
DOUBLE_MM = 180.0
MIN_FONT_PT = 6.0
FONT_STACK = '"Helvetica Neue", Arial, "Noto Sans", "Microsoft YaHei", sans-serif'

INK = "#1c1f23"
MUTED = "#5c6470"
RULE = "#6b7280"
PAPER = "#ffffff"

VERDICT_COLORS = {
    "DEFEATED": "#D55E00",
    "SUSPENDED": "#E69F00",
    "UNTESTED": "#8A8A8A",
    "UNDETERMINED": "#56B4E9",
    "SUPPORTED": "#0072B2",
}

BUCKET_ORDER = ("hard", "soft", "pending", "ok")
BUCKET_COLORS = {"hard": "#D55E00", "soft": "#E69F00", "pending": "#8A8A8A", "ok": "#0072B2"}
BUCKET_LABELS = {
    "en": {
        "hard": "hard (blocking)",
        "soft": "soft (weakening)",
        "pending": "pending",
        "ok": "satisfied",
    },
    "zh": {
        "hard": "\u81f4\u547d\uff08\u786c\uff09",
        "soft": "\u524a\u5f31\uff08\u8f6f\uff09",
        "pending": "\u5f85\u5b9a",
        "ok": "\u5df2\u6ee1\u8db3",
    },
}

ITEM_STATE_COLORS = {
    "supported": "#0072B2",
    "chain-supported": "#0072B2",
    "disputed": "#E69F00",
    "chain-disputed": "#E69F00",
    "unsupported": "#D55E00",
    "missing-evidence": "#D55E00",
    "chain-unsupported": "#D55E00",
    "undetermined": "#56B4E9",
    "chain-undetermined": "#56B4E9",
    "untested": "#8A8A8A",
    "unknown": "#8A8A8A",
    "chain-unresolved": "#8A8A8A",
    "chain-cycle": "#8A8A8A",
    "holds": "#0072B2",
    "fails": "#D55E00",
    "refuted": "#56B4E9",
    "established": "#D55E00",
    "passed": "#0072B2",
    "failed": "#D55E00",
}

EVIDENCE_STATUS_COLORS = {
    "accepted": "#0072B2",
    "disputed": "#E69F00",
    "retracted": "#D55E00",
    "superseded": "#8A8A8A",
}

CLASS_ORDER = ("decisive", "backing", "redundant", "unused", "untapped")
CLASS_COLORS = {
    "decisive": "#D55E00",
    "backing": "#0072B2",
    "redundant": "#E69F00",
    "unused": "#8A8A8A",
    "untapped": "#C8C8C8",
}

POWER_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}
POWER_LABELS = {
    "en": {0: "none", 1: "low", 2: "medium", 3: "high"},
    "zh": {0: "\u65e0", 1: "\u4f4e", 2: "\u4e2d", 3: "\u9ad8"},
}


def pt_to_mm(value: float) -> float:
    """Convert a landed type size in points to millimetres."""
    return float(value) * 25.4 / 72.0


def mm_to_pt(value: float) -> float:
    """Convert millimetres to points."""
    return float(value) * 72.0 / 25.4


def _rgb(hex_color: str) -> tuple[float, float, float]:
    value = str(hex_color).strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"expected a 6-digit hex colour, got {hex_color!r}")
    try:
        return tuple(int(value[index : index + 2], 16) / 255.0 for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"expected a 6-digit hex colour, got {hex_color!r}") from exc


def relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance of a hex colour."""
    channels = []
    for channel in _rgb(hex_color):
        channels.append(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    """WCAG contrast ratio between two hex colours."""
    high, low = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def grayscale_conflicts(colors: dict[str, str], minimum: float = 1.35) -> list[dict[str, object]]:
    """Return colour pairs whose grayscale contrast is below ``minimum``.

    A pair that fails here may still be legible in colour, but a grayscale print
    cannot separate the two categories. The check is advisory; figures that use
    only one of each conflicting pair are fine.
    """
    names = sorted(colors)
    conflicts: list[dict[str, object]] = []
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            ratio = contrast_ratio(colors[first], colors[second])
            if ratio < minimum:
                conflicts.append({"a": first, "b": second, "ratio": round(ratio, 3)})
    return conflicts


def palette_report(colors: dict[str, str], minimum: float = 1.35) -> dict[str, object]:
    """Summarise a palette for the docs and the tests."""
    names = sorted(colors)
    ratios = [
        contrast_ratio(colors[names[index]], colors[second])
        for index, second in ((index, second) for index in range(len(names)) for second in names[index + 1 :])
    ]
    luminance = {name: round(relative_luminance(colors[name]), 4) for name in names}
    return {
        "colors": [{"name": name, "hex": colors[name], "luminance": luminance[name]} for name in names],
        "conflicts": grayscale_conflicts(colors, minimum),
        "min_contrast": round(min(ratios), 3) if ratios else None,
    }


def check_font(size_pt: float) -> float:
    """Reject a landed type size below the minimum."""
    size = float(size_pt)
    if size < MIN_FONT_PT:
        raise ValueError(f"font {size:g}pt is below the landed minimum {MIN_FONT_PT:g}pt")
    return size


def state_color(state: str | None) -> str:
    """Colour for one item state, with a neutral fallback."""
    return ITEM_STATE_COLORS.get(str(state or ""), "#8A8A8A")


def bucket_label(bucket: str, lang: str = "en") -> str:
    """Human label for a reason bucket."""
    table = BUCKET_LABELS["zh"] if str(lang).lower().startswith("zh") else BUCKET_LABELS["en"]
    return table.get(str(bucket), table["pending"])


def power_label(rank: int | None, lang: str = "en") -> str:
    """Human label for a discriminating-power rank."""
    table = POWER_LABELS["zh"] if str(lang).lower().startswith("zh") else POWER_LABELS["en"]
    try:
        key = int(rank or 0)
    except (TypeError, ValueError):
        key = 0
    return table.get(key, table[0])


def verdict_color(verdict: str | None) -> str:
    """Colour for a verdict token."""
    return VERDICT_COLORS.get(str(verdict or ""), "#8A8A8A")
