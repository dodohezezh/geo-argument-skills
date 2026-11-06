"""Self-contained HTML rendering for reports and workspace audits.

The HTML output is a single file: inline CSS, no external assets, no runtime
JavaScript. Sections are collapsible with native ``<details>`` elements, and a
print stylesheet turns the file into a clean PDF through the browser's print
dialog. The data comes from the same model as the Markdown and Word renderers,
so the three outputs never disagree about a verdict or a reason.
"""

from __future__ import annotations

import html
from typing import Any

_CSS = """
:root {
  --ink: #1c1f23;
  --muted: #5c6470;
  --rule: #d7dce2;
  --paper: #fbfbf9;
  --panel: #f2f4f6;
  --accent: #1f5f8b;
  --hard: #9b2c2c;
  --soft: #8a5a00;
  --pending: #1f5f8b;
}
* { box-sizing: border-box; }
body {
  margin: 0 auto;
  padding: 2.2rem 1.4rem 4rem;
  max-width: 62rem;
  background: var(--paper);
  color: var(--ink);
  font: 16px/1.65 -apple-system, "Segoe UI", "Noto Sans", "Microsoft YaHei", sans-serif;
}
h1 { font-size: 1.7rem; line-height: 1.25; margin: 0 0 .4rem; letter-spacing: -.01em; }
h2 { font-size: 1.15rem; margin: 0; }
.meta { margin: 0 0 1.6rem; padding: 0; list-style: none; color: var(--muted); font-size: .92rem; }
.meta li { margin: .15rem 0; }
.meta b { color: var(--ink); font-weight: 600; }
section { margin: 1rem 0; border: 1px solid var(--rule); border-radius: 8px; background: #fff; }
section > details { padding: .2rem .9rem .9rem; }
section > details > summary, section > h2 {
  cursor: pointer; padding: .7rem .1rem .45rem; font-weight: 650; color: var(--accent);
  list-style-position: outside;
}
section > h2 { padding: .85rem .9rem .25rem; }
details > *:not(summary) { margin-left: .1rem; }
p { margin: .45rem 0; }
ul { margin: .35rem 0 .6rem; padding-left: 1.2rem; }
li { margin: .18rem 0; }
.note { color: var(--muted); font-style: italic; font-size: .92rem; }
.table-wrap { overflow-x: auto; margin: .5rem 0 .8rem; }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { border: 1px solid var(--rule); padding: .38rem .5rem; text-align: left; vertical-align: top; }
th { background: var(--panel); font-weight: 650; }
tr:nth-child(even) td { background: #fcfcfb; }
.bucket-hard, .bucket-soft, .bucket-pending { font-weight: 600; }
.footer { margin-top: 2rem; color: var(--muted); font-size: .82rem; border-top: 1px solid var(--rule); padding-top: .8rem; }
.figure-grid { display: grid; gap: 1rem; margin: .6rem 0 .2rem; }
.figure-grid figure { margin: 0; padding: .5rem; border: 1px solid var(--rule); border-radius: 6px; background: #fff; }
.figure-grid svg { display: block; width: 100%; height: auto; }
.figure-grid figcaption { margin-top: .35rem; color: var(--muted); font-size: .82rem; }
@media print {
  :root { --paper: #fff; }
  body { max-width: none; padding: 0; font-size: 11pt; }
  section { break-inside: avoid; border-color: #bbb; }
  details > summary { color: #000; }
  .footer { break-inside: avoid; }
}
"""


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _table(header: list[str], rows: list[list[Any]]) -> str:
    out = ['<div class="table-wrap"><table>', "<thead><tr>"]
    out.extend(f"<th>{_esc(cell)}</th>" for cell in header)
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        out.extend(f"<td>{_esc(cell)}</td>" for cell in row)
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _blocks(blocks: list[tuple[str, Any]]) -> str:
    out: list[str] = []
    for kind, payload in blocks:
        if kind == "p":
            out.append(f"<p>{_esc(payload)}</p>")
        elif kind == "bullets":
            out.append("<ul>")
            out.extend(f"<li>{_esc(line)}</li>" for line in payload)
            out.append("</ul>")
        elif kind == "table":
            header, rows = payload
            out.append(_table(list(header), [list(row) for row in rows]))
        elif kind == "note":
            out.append(f'<p class="note">{_esc(payload)}</p>')
    return "".join(out)


def render_html(
    model: dict[str, Any],
    lang: str = "en",
    figures: list[tuple[str, str]] | None = None,
) -> str:
    """Render the report document model as a self-contained HTML page.

    ``figures`` is an optional list of ``(name, svg_text)`` pairs; when given,
    the received SVG files are embedded inline under a Figures section, so the
    page stays a single file with no external assets.
    """
    title = model.get("title") or "GeoArg report"
    meta = model.get("meta") or []
    sections = model.get("sections") or []
    lang_attr = "zh-CN" if str(lang).lower().startswith("zh") else "en"
    out: list[str] = [
        "<!doctype html>",
        f'<html lang="{lang_attr}">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_esc(title)}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        f"<h1>{_esc(title)}</h1>",
    ]
    if meta:
        out.append('<ul class="meta">')
        for label, value in meta:
            out.append(f"<li><b>{_esc(label)}</b>: {_esc(value)}</li>")
        out.append("</ul>")
    for section in sections:
        heading = section.get("heading") or ""
        out.append("<section>")
        out.append("<details open>")
        out.append(f"<summary>{_esc(heading)}</summary>")
        out.append(_blocks(section.get("blocks") or []))
        out.append("</details>")
        out.append("</section>")
    if figures:
        out.append("<section>")
        out.append("<details open>")
        lang_attr = "zh-CN" if str(lang).lower().startswith("zh") else "en"
        out.append(f"<summary>{_esc('论证图' if lang_attr == 'zh-CN' else 'Figures')}</summary>")
        out.append('<div class="figure-grid">')
        for name, svg_text in figures:
            out.append(f"<figure>{svg_text}<figcaption>{_esc(name)}</figcaption></figure>")
        out.append("</div>")
        out.append("</details>")
        out.append("</section>")
    out.append('<p class="footer">Generated by geoarg. This page is a rendering; the committed record and the ledger are the evidence of what was checked.</p>')
    out.append("</body>")
    out.append("</html>")
    return "\n".join(out)


def _workspace_labels(lang: str) -> dict[str, str]:
    from .chain import _labels

    return _labels(lang)


def render_workspace_html(report: dict[str, Any], lang: str = "en") -> str:
    """Render a workspace audit payload as a self-contained HTML page."""
    labels = _workspace_labels(lang)
    lang_attr = "zh-CN" if str(lang).lower().startswith("zh") else "en"
    problems = report.get("problems") or []
    root = report.get("root", "")
    title = labels["title"].format(root=root)
    out: list[str] = [
        "<!doctype html>",
        f'<html lang="{lang_attr}">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_esc(title)}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        f"<h1>{_esc(title)}</h1>",
        f"<p>{_esc(labels['intro'].format(count=len(report.get('cases') or [])))}</p>",
    ]

    def section(heading: str, body: list[str]) -> None:
        out.append("<section>")
        out.append("<details open>")
        out.append(f"<summary>{_esc(heading)}</summary>")
        out.extend(body)
        out.append("</details>")
        out.append("</section>")

    cases = report.get("cases") or []
    body: list[str] = []
    if cases:
        rows = []
        for row in cases:
            verdict_text = (
                _status_label(row["verdict"], lang) if row.get("verdict") else "-"
            )
            rows.append(
                [
                    row.get("argument_id") or "-",
                    row.get("title") or row.get("claim_id") or "-",
                    verdict_text,
                    row.get("case"),
                ]
            )
        body.append(_table([labels["argument"], labels["claim"], labels["verdict"], labels["case"]], rows))
    else:
        body.append("<p>-</p>")
    section(labels["cases_heading"], body)

    chains = report.get("chains") or []
    body = []
    if chains:
        rows = []
        for row in chains:
            target = row.get("target") or row.get("premise_ref") or "-"
            target_verdict = (
                _status_label(row["target_verdict"], lang) if row.get("target_verdict") else "-"
            )
            rows.append([row.get("premise_ref"), target, target_verdict])
        body.append(_table([labels["premise"], labels["target"], labels["target_verdict"]], rows))
    else:
        body.append(f"<p>{_esc(labels['chains_none'])}</p>")
    section(labels["chains_heading"], body)

    shared = report.get("evidence_shared") or []
    body = []
    if shared:
        rows = [[row["evidence_id"], ", ".join(row["cases"])] for row in shared]
        body.append(_table([labels["evidence"], labels["cases"]], rows))
    else:
        body.append(f"<p>{_esc(labels['shared_none'])}</p>")
    section(labels["shared_heading"], body)

    conflicts = report.get("evidence_conflicts") or []
    body = []
    if conflicts:
        body.append("<ul>")
        body.extend(f"<li>{_esc(row['evidence_id'])}: {_esc(', '.join(row['cases']))}</li>" for row in conflicts)
        body.append("</ul>")
    else:
        body.append(f"<p>{_esc(labels['conflicts_none'])}</p>")
    section(labels["conflicts_heading"], body)

    drift = [p for p in problems if "since commit" in p or "ledger" in p or "verdict changed" in p]
    body = []
    if drift:
        body.append("<ul>")
        body.extend(f"<li>{_esc(item)}</li>" for item in drift)
        body.append("</ul>")
    else:
        body.append(f"<p>{_esc(labels['drift_none'])}</p>")
    section(labels["drift_heading"], body)

    body = []
    if problems:
        body.append("<ul>")
        body.extend(f"<li>{_esc(item)}</li>" for item in problems)
        body.append("</ul>")
        body.append(f"<p><b>{_esc(labels['not_ok'].format(count=len(problems)))}</b></p>")
    else:
        body.append(f"<p>{_esc(labels['problems_none'])}</p>")
        body.append(f"<p><b>{_esc(labels['ok'])}</b></p>")
    section(labels["problems_heading"], body)

    out.append('<p class="footer">Generated by geoarg. This page is a rendering; the committed record and the ledger are the evidence of what was checked.</p>')
    out.append("</body>")
    out.append("</html>")
    return "\n".join(out)


def _status_label(verdict: str, lang: str) -> str:
    from . import terms

    return terms.status_label(verdict, lang)
