"""Minimal deterministic SVG canvas for GeoArg figures.

The canvas works in millimetres: ``width``/``height`` are the landed figure
dimensions, the viewBox matches them one-to-one, and type sizes are converted
from points to millimetres. The output is a standalone ``<svg>`` element with no
scripts, no external assets, and no timestamps, so the bytes are identical for
identical inputs.
"""

from __future__ import annotations

import html as _html

from . import figstyle


def _n(value: float) -> str:
    text = f"{float(value):.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _attr(value: str) -> str:
    return _html.escape(str(value), quote=True)


class Svg:
    """A tiny SVG canvas in millimetre units."""

    def __init__(
        self,
        width_mm: float,
        height_mm: float,
        *,
        title: str = "",
        description: str = "",
        lang: str = "en",
    ) -> None:
        if float(width_mm) <= 0 or float(height_mm) <= 0:
            raise ValueError("figure size must be positive")
        self.width = float(width_mm)
        self.height = float(height_mm)
        self.title = str(title)
        self.description = str(description)
        self.lang = "zh-CN" if str(lang).lower().startswith("zh") else "en"
        self._parts: list[str] = []

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: str,
        *,
        stroke: str = "none",
        stroke_width: float = 0.0,
        opacity: float = 1.0,
        rx: float = 0.0,
    ) -> None:
        self._parts.append(
            f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(width)}" height="{_n(height)}" '
            f'rx="{_n(rx)}" fill="{fill}" stroke="{stroke}" stroke-width="{_n(stroke_width)}" '
            f'opacity="{_n(opacity)}"/>'
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        stroke: str = figstyle.RULE,
        *,
        width: float = 0.25,
        dash: str | None = None,
        opacity: float = 1.0,
    ) -> None:
        dash_attr = f' stroke-dasharray="{_attr(dash)}"' if dash else ""
        self._parts.append(
            f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" '
            f'stroke="{stroke}" stroke-width="{_n(width)}" opacity="{_n(opacity)}"{dash_attr}/>'
        )

    def polyline(
        self,
        points: list[tuple[float, float]],
        stroke: str,
        *,
        width: float = 0.45,
        fill: str = "none",
        opacity: float = 1.0,
    ) -> None:
        if not points:
            return
        rendered = " ".join(f"{_n(x)},{_n(y)}" for x, y in points)
        self._parts.append(
            f'<polyline points="{rendered}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{_n(width)}" opacity="{_n(opacity)}"/>'
        )

    def polygon(self, points: list[tuple[float, float]], fill: str, *, opacity: float = 1.0) -> None:
        if not points:
            return
        rendered = " ".join(f"{_n(x)},{_n(y)}" for x, y in points)
        self._parts.append(f'<polygon points="{rendered}" fill="{fill}" opacity="{_n(opacity)}"/>')

    def circle(self, cx: float, cy: float, radius: float, fill: str, *, stroke: str = "none", stroke_width: float = 0.0) -> None:
        self._parts.append(
            f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(radius)}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{_n(stroke_width)}"/>'
        )

    def text(
        self,
        x: float,
        y: float,
        value: object,
        *,
        size_pt: float = 8.0,
        anchor: str = "start",
        fill: str = figstyle.INK,
        weight: str = "normal",
        opacity: float = 1.0,
        italic: bool = False,
    ) -> None:
        size = figstyle.pt_to_mm(figstyle.check_font(size_pt))
        style_attr = ' font-style="italic"' if italic else ""
        self._parts.append(
            f'<text x="{_n(x)}" y="{_n(y)}" font-family="{_attr(figstyle.FONT_STACK)}" '
            f'font-size="{_n(size)}" fill="{fill}" text-anchor="{_attr(anchor)}" '
            f'font-weight="{_attr(weight)}"{style_attr} opacity="{_n(opacity)}">'
            f"{_html.escape('' if value is None else str(value))}</text>"
        )

    def text_top(self, x: float, top: float, value: object, *, size_pt: float = 8.0, **kwargs: object) -> None:
        """Place text with its top edge at ``top`` instead of its baseline."""
        size = figstyle.pt_to_mm(figstyle.check_font(size_pt))
        self.text(x, top + size * 0.92, value, size_pt=size_pt, **kwargs)  # type: ignore[arg-type]

    def render(self) -> str:
        head = [
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(self.width)}mm" '
                f'height="{_n(self.height)}mm" viewBox="0 0 {_n(self.width)} {_n(self.height)}" '
                f'role="img" xml:lang="{self.lang}">'
            )
        ]
        if self.title:
            head.append(f"<title>{_html.escape(self.title)}</title>")
        if self.description:
            head.append(f"<desc>{_html.escape(self.description)}</desc>")
        head.append(f'<rect width="{_n(self.width)}" height="{_n(self.height)}" fill="{figstyle.PAPER}"/>')
        return "\n".join(head + self._parts + ["</svg>"]) + "\n"
