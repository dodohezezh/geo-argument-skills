"""A minimal local form editor for one case.

``geoarg edit <case>`` serves a small HTML form on 127.0.0.1. The form edits the
high-value fields of the contract (claim, premises, conditions, defeaters,
entailments, evidence, tests); fields the form does not show are preserved.

Design constraints, in order:

* no third-party dependency and no external asset;
* the form is server-rendered, so the whole editor is testable without a browser;
* a save writes the three YAML files atomically and immediately reports the
  engine's validation problems, but never repairs them silently;
* the server binds 127.0.0.1 and requires a random per-run token, because the
  case directory is the user's data.
"""

from __future__ import annotations

import html
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import yaml

from .contract import ContractError, load_case, validate
from .domains import effective_enums
from .safeio import atomic_write_text

_MAX_BODY = 2_000_000


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def model(case_root: str | Path) -> dict[str, Any]:
    """Return the editable shape of one case plus effective enum values."""
    case = load_case(case_root)
    enums = effective_enums(case.domain_pack)
    pack = None if case.domain_pack is None else {
        "name": case.domain_pack["name"],
        "path": str(case.domain_pack["path"]),
    }
    return {
        "case": str(case.root),
        "pack": pack,
        "argument": _jsonable(case.argument),
        "evidence": _jsonable(case.evidence),
        "tests": _jsonable(case.tests),
        "enums": {key: sorted(values) for key, values in enums.items()},
        "problems": validate(case),
    }


# ---------------------------------------------------------------------------
# Form parsing


def _first(form: dict[str, list[str]], name: str, default: str = "") -> str:
    values = form.get(name)
    if not values:
        return default
    return values[0]


def _int_or_none(text: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _float_or_none(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _split_csv(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]



def _row_indices(form: dict[str, list[str]], prefix: str) -> list[int]:
    indices: set[int] = set()
    for name in form:
        if not name.startswith(prefix + "."):
            continue
        rest = name[len(prefix) + 1 :]
        head, _, _ = rest.partition(".")
        if head.isdigit():
            indices.add(int(head))
    return sorted(indices)


def _merge_docs(case: Any, form: dict[str, list[str]]) -> tuple[dict, dict, dict]:
    """Build new documents from the form, keeping fields the form does not edit."""
    argument = dict(case.argument)
    evidence = dict(case.evidence)
    tests = dict(case.tests)

    claim = dict(argument.get("claim") or {})
    domain = _first(form, "domain", "").strip()
    if domain:
        argument["domain"] = domain
    for key in ("statement", "kind", "layer", "scope"):
        value = _first(form, f"claim.{key}", "")
        if value.strip():
            claim[key] = value.strip()
    argument["claim"] = claim

    inference = dict(argument.get("inference") or {})
    for key in ("rule_id", "warrant"):
        value = _first(form, f"inference.{key}", "")
        if value.strip():
            inference[key] = value.strip()

    premises: list[dict[str, Any]] = []
    for index in _row_indices(form, "premises"):
        ident = _first(form, f"premises.{index}.id", "").strip()
        if not ident:
            continue
        base = dict((argument.get("premises") or [{}])[index]) if index < len(argument.get("premises") or []) else {}
        base["id"] = ident
        for key in ("statement", "kind", "status", "layer", "evidence_refs", "argument_ref"):
            value = _first(form, f"premises.{index}.{key}", "")
            if not value.strip():
                base.pop(key, None)
                continue
            base[key] = _split_csv(value) if key == "evidence_refs" else value.strip()
        premises.append(base)
    if premises:
        argument["premises"] = premises

    cp: list[dict[str, Any]] = []
    for index in _row_indices(form, "cp"):
        ident = _first(form, f"cp.{index}.id", "").strip()
        if not ident:
            continue
        old = (inference.get("cp") or [])
        base = dict(old[index]) if index < len(old) else {}
        base["id"] = ident
        for key in ("statement", "cp_type", "state", "test_ref"):
            value = _first(form, f"cp.{index}.{key}", "")
            if not value.strip():
                base.pop(key, None)
                continue
            base[key] = value.strip()
        cp.append(base)
    if cp:
        inference["cp"] = cp

    defeaters: list[dict[str, Any]] = []
    for index in _row_indices(form, "defeaters"):
        ident = _first(form, f"defeaters.{index}.id", "").strip()
        if not ident:
            continue
        old = (inference.get("defeaters") or [])
        base = dict(old[index]) if index < len(old) else {}
        base["id"] = ident
        for key in ("statement", "type", "severity", "state", "test_ref"):
            value = _first(form, f"defeaters.{index}.{key}", "")
            if not value.strip():
                base.pop(key, None)
                continue
            base[key] = value.strip()
        defeaters.append(base)
    if defeaters:
        inference["defeaters"] = defeaters
    argument["inference"] = inference

    entailments: list[dict[str, Any]] = []
    for index in _row_indices(form, "entailments"):
        ident = _first(form, f"entailments.{index}.id", "").strip()
        if not ident:
            continue
        old = (argument.get("entailments") or [])
        base = dict(old[index]) if index < len(old) else {}
        base["id"] = ident
        for key in ("statement", "kind", "risk", "status", "test_ref"):
            value = _first(form, f"entailments.{index}.{key}", "")
            if not value.strip():
                base.pop(key, None)
                continue
            base[key] = value.strip()
        entailments.append(base)
    if entailments:
        argument["entailments"] = entailments

    records: list[dict[str, Any]] = []
    for index in _row_indices(form, "evidence"):
        ident = _first(form, f"evidence.{index}.id", "").strip()
        if not ident:
            continue
        old = (evidence.get("records") or [])
        base = dict(old[index]) if index < len(old) else {}
        base["id"] = ident
        for key in ("statement", "kind", "layer", "status"):
            value = _first(form, f"evidence.{index}.{key}", "")
            if not value.strip():
                base.pop(key, None)
                continue
            base[key] = value.strip()
        citation = _first(form, f"evidence.{index}.citation", "").strip()
        page = _first(form, f"evidence.{index}.page", "").strip()
        quote = _first(form, f"evidence.{index}.quote", "").strip()
        source = dict(base.get("source") or {})
        if citation:
            source["citation"] = citation
        else:
            source.pop("citation", None)
        if source:
            base["source"] = source
        if page or quote:
            locator = dict(base.get("source_locator") or {})
            if page:
                locator["page"] = _int_or_none(page)
            else:
                locator.pop("page", None)
            if quote:
                locator["quote"] = quote
            else:
                locator.pop("quote", None)
            base["source_locator"] = locator
        records.append(base)
    if records:
        evidence["records"] = records

    test_records: list[dict[str, Any]] = []
    for index in _row_indices(form, "tests"):
        ident = _first(form, f"tests.{index}.id", "").strip()
        if not ident:
            continue
        old = (tests.get("records") or [])
        base = dict(old[index]) if index < len(old) else {}
        base["id"] = ident
        for key in ("name", "status", "discriminating_power", "checks"):
            value = _first(form, f"tests.{index}.{key}", "")
            if not value.strip():
                base.pop(key, None)
                continue
            base[key] = _split_csv(value) if key == "checks" else value.strip()
        method_type = _first(form, f"tests.{index}.method_type", "").strip()
        method = dict(base.get("method") or {})
        if method_type:
            method["type"] = method_type
        if method:
            base["method"] = method
        cost = _first(form, f"tests.{index}.cost", "").strip()
        if cost:
            base["cost"] = _float_or_none(cost)
        test_records.append(base)
    if test_records:
        tests["records"] = test_records

    return argument, evidence, tests


def apply_form(case_root: str | Path, form: dict[str, list[str]]) -> list[str]:
    """Write the three YAML documents from form values; return validation problems."""
    root = Path(case_root)
    case = load_case(root)
    argument, evidence, tests = _merge_docs(case, form)
    for name, doc, path in (
        ("argument.yaml", argument, root / "argument.yaml"),
        ("evidence.yaml", evidence, root / "evidence.yaml"),
        ("test.yaml", tests, root / "test.yaml"),
    ):
        if not isinstance(doc, dict):
            raise ContractError(f"{name}: form produced a non-mapping document")
        text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
        atomic_write_text(path, text)
    try:
        fresh = load_case(root)
    except ContractError as exc:
        return [str(exc)]
    return validate(fresh)


# ---------------------------------------------------------------------------
# HTML rendering


_CSS = """
:root { --ink:#1d232b; --muted:#5b6673; --line:#d7dde5; --paper:#fbfcfd; --accent:#1f6f5c; }
* { box-sizing: border-box; }
body { margin:0; background:var(--paper); color:var(--ink); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
header { padding:18px 22px; border-bottom:1px solid var(--line); background:#fff; }
h1 { margin:0 0 4px; font-size:20px; }
h2 { margin:26px 0 8px; font-size:16px; }
.muted { color:var(--muted); font-size:13px; }
main { padding:8px 22px 60px; max-width:1100px; }
label { display:block; font-size:12px; color:var(--muted); margin:6px 0 2px; }
input[type=text], textarea, select { width:100%; padding:6px 8px; border:1px solid var(--line); border-radius:6px; font:inherit; background:#fff; }
textarea { min-height:54px; resize:vertical; }
table { width:100%; border-collapse:collapse; margin:6px 0 10px; }
th { text-align:left; font-size:12px; color:var(--muted); padding:4px 6px; border-bottom:1px solid var(--line); }
td { vertical-align:top; padding:4px 6px; border-bottom:1px solid #edf1f5; }
.row-num { width:34px; color:var(--muted); font-size:12px; }
.savebar { position:sticky; bottom:0; background:#fff; border-top:1px solid var(--line); padding:10px 22px; display:flex; gap:12px; align-items:center; }
button { background:var(--accent); color:#fff; border:0; border-radius:6px; padding:8px 16px; font:inherit; cursor:pointer; }
.problems { background:#fff4f2; border:1px solid #f0c4bc; border-radius:8px; padding:10px 14px; margin:12px 0; }
.ok { background:#eef7f2; border:1px solid #bfe0cf; border-radius:8px; padding:10px 14px; margin:12px 0; }
canvas { display:none; }
"""


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _text_input(name: str, value: Any, placeholder: str = "", size: str = "") -> str:
    style = f' style="max-width:{size}"' if size else ""
    return (
        f'<input type="text" name="{_esc(name)}" value="{_esc(value)}" '
        f'placeholder="{_esc(placeholder)}"{style}>'
    )


def _textarea(name: str, value: Any) -> str:
    return f'<textarea name="{_esc(name)}">{_esc(value)}</textarea>'


def _select(name: str, value: Any, options: list[str]) -> str:
    rows = [f'<option value=""{" selected" if not value else ""}>(unset)</option>']
    for option in sorted(set(options)):
        selected = " selected" if str(value) == option else ""
        rows.append(f'<option value="{_esc(option)}"{selected}>{_esc(option)}</option>')
    return f'<select name="{_esc(name)}">{"".join(rows)}</select>'


def _collection_table(prefix: str, rows: list[dict[str, Any]], fields: list[tuple[str, str, str]], enums: dict[str, list[str]]) -> str:
    """Render one editable collection with an empty trailing row."""
    head = "".join(f"<th>{_esc(label)}</th>" for label in ("#", *[label for label, _, _ in fields]))
    body: list[str] = []
    total = len(rows) + 1
    for index in range(total):
        row = rows[index] if index < len(rows) else {}
        cells = [f'<td class="row-num">{index}</td>']
        for key, kind, option_key in fields:
            name = f"{prefix}.{index}.{key}"
            value = row.get(key, "")
            if key == "evidence_refs" or key == "checks":
                value = ", ".join(value) if isinstance(value, list) else value
            if kind == "textarea":
                control = _textarea(name, value)
            elif kind == "select":
                control = _select(name, value, enums.get(option_key, []))
            elif kind == "datalist":
                options_id = f"{prefix}-{key}-options"
                control = (
                    f'<input type="text" name="{_esc(name)}" value="{_esc(value)}" list="{_esc(options_id)}">'
                    f'<datalist id="{_esc(options_id)}">'
                    + "".join(f'<option value="{_esc(option)}"></option>' for option in sorted(enums.get(option_key, [])))
                    + "</datalist>"
                )
            else:
                control = _text_input(name, value)
            cells.append(f"<td>{control}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def render_page(case_root: str | Path, token: str, problems: list[str] | None = None, saved: bool = False, lang: str = "en") -> str:
    data = model(case_root)
    argument = data["argument"]
    evidence = data["evidence"]
    tests = data["tests"]
    enums = data["enums"]
    claim = argument.get("claim") or {}
    inference = argument.get("inference") or {}
    pack = data["pack"]

    problem_html = ""
    if saved:
        if problems:
            rows = "".join(f"<li>{_esc(problem)}</li>" for problem in problems)
            problem_html = f'<div class="problems"><strong>Saved, but the engine reports problems:</strong><ul>{rows}</ul></div>'
        else:
            problem_html = '<div class="ok">Saved. The contract validates.</div>'
    elif problems:
        rows = "".join(f"<li>{_esc(problem)}</li>" for problem in problems)
        problem_html = f'<div class="problems"><ul>{rows}</ul></div>'

    pack_line = (
        f'domain pack: <code>{_esc(pack["name"])}</code> ({_esc(pack["path"])})'
        if pack
        else "no domain pack (built-in enums)"
    )

    parts: list[str] = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>geoarg edit: {_esc(Path(data['case']).name)}</title>",
        f"<style>{_CSS}</style></head><body>",
        f"<header><h1>geoarg edit</h1><div class=\"muted\">{_esc(data['case'])} · {pack_line}</div></header>",
        '<main><form method="post" action="/edit">',
        f'<input type="hidden" name="_token" value="{_esc(token)}">',
        problem_html,
        "<h2>Claim</h2>",
        "<label>statement</label>" + _textarea("claim.statement", claim.get("statement", "")),
        "<label>domain</label>" + _select("domain", argument.get("domain", ""), enums["domains"]),
        "<label>kind</label>" + _select("claim.kind", claim.get("kind", ""), enums["claim_kinds"]),
        "<label>layer</label>" + _select("claim.layer", claim.get("layer", ""), enums["layers"]),
        "<label>scope</label>" + _text_input("claim.scope", claim.get("scope", "")),
        "<h2>Inference</h2>",
        "<label>rule id</label>" + _text_input("inference.rule_id", inference.get("rule_id", "")),
        "<label>warrant</label>" + _textarea("inference.warrant", inference.get("warrant", "")),
        "<div class=\"muted\">A row with an empty id is ignored; to delete a record, clear its id.</div>",
        "<h2>Premises</h2>",
        _collection_table(
            "premises",
            list(argument.get("premises") or []),
            [
                ("id", "text", ""),
                ("statement", "textarea", ""),
                ("kind", "select", "premise_kind"),
                ("status", "select", "premise_status"),
                ("layer", "select", "layers"),
                ("evidence_refs", "text", ""),
                ("argument_ref", "text", ""),
            ],
            {**enums, "premise_kind": ["evidenced", "derived"]},
        ),
        "<h2>Conditions (cp)</h2>",
        _collection_table(
            "cp",
            list(inference.get("cp") or []),
            [
                ("id", "text", ""),
                ("statement", "textarea", ""),
                ("cp_type", "datalist", "cp_types"),
                ("state", "text", ""),
                ("test_ref", "text", ""),
            ],
            enums,
        ),
        "<h2>Defeaters</h2>",
        _collection_table(
            "defeaters",
            list(inference.get("defeaters") or []),
            [
                ("id", "text", ""),
                ("statement", "textarea", ""),
                ("type", "select", "defeater_types"),
                ("severity", "select", "severities"),
                ("state", "text", ""),
                ("test_ref", "text", ""),
            ],
            enums,
        ),
        "<h2>Entailments</h2>",
        _collection_table(
            "entailments",
            list(argument.get("entailments") or []),
            [
                ("id", "text", ""),
                ("statement", "textarea", ""),
                ("kind", "datalist", "entailment_kinds"),
                ("risk", "select", "risks"),
                ("status", "text", ""),
                ("test_ref", "text", ""),
            ],
            enums,
        ),
        "<h2>Evidence</h2>",
        _collection_table(
            "evidence",
            list(evidence.get("records") or []),
            [
                ("id", "text", ""),
                ("statement", "textarea", ""),
                ("kind", "datalist", "evidence_kinds"),
                ("layer", "select", "evidence_layers"),
                ("status", "select", "evidence_status"),
                ("citation", "text", ""),
                ("page", "text", ""),
                ("quote", "text", ""),
            ],
            enums,
        ),
        "<h2>Tests</h2>",
        _collection_table(
            "tests",
            list(tests.get("records") or []),
            [
                ("id", "text", ""),
                ("name", "text", ""),
                ("method_type", "datalist", "method_types"),
                ("discriminating_power", "select", "powers"),
                ("status", "select", "test_status"),
                ("checks", "text", ""),
                ("cost", "text", ""),
            ],
            enums,
        ),
        "</main>",
        f'<div class="savebar"><button type="submit">Save and validate</button>'
        f'<span class="muted">Writes {_esc(Path(data["case"]).name)}/argument.yaml, evidence.yaml, test.yaml atomically.</span></div>',
        "</form></body></html>",
    ]
    return "".join(parts)


# ---------------------------------------------------------------------------
# HTTP server


class _Handler(BaseHTTPRequestHandler):
    server_version = "geoarg-edit/1.0"
    case_root: Path
    token: str

    def log_message(self, fmt: str, *args: Any) -> None:  # pragma: no cover - quiet server
        return

    def _send(self, status: int, body: str, content_type: str = "text/html; charset=utf-8") -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _problems(self, saved: bool, problems: list[str] | None) -> str:
        return render_page(self.case_root, self.token, problems=problems, saved=saved)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path.split("?", 1)[0] not in ("/", "/index.html"):
            self._send(404, "not found")
            return
        self._send(200, self._problems(False, None))

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if self.path != "/edit":
            self._send(404, "not found")
            return
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > _MAX_BODY:
            self._send(413, "request body missing or too large")
            return
        raw = self.rfile.read(length).decode("utf-8", "replace")
        form = parse_qs(raw, keep_blank_values=True)
        if _first(form, "_token", "") != self.token:
            self._send(403, "invalid editor token; reload the page")
            return
        try:
            problems = apply_form(self.case_root, form)
        except (ContractError, OSError, yaml.YAMLError) as exc:
            self._send(200, self._problems(True, [str(exc)]))
            return
        self._send(200, self._problems(True, problems))


def serve(
    case_root: str | Path,
    host: str = "127.0.0.1",
    port: int = 0,
    token: str | None = None,
) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    """Start the editor server; returns (server, thread, url)."""
    root = Path(case_root).resolve()
    load_case(root)  # fail early, not inside the request handler
    handler = type("_BoundHandler", (_Handler,), {"case_root": root, "token": token or secrets.token_urlsafe(18)})
    httpd = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    actual_port = httpd.server_address[1]
    url = f"http://{host}:{actual_port}/"
    return httpd, thread, url


def run_editor(case_root: str | Path, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    """Run until interrupted."""
    httpd, _thread, url = serve(case_root, host=host, port=port)
    print(f"geoarg edit: {url}")
    print("press Ctrl+C to stop")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # pragma: no cover - headless environments
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
