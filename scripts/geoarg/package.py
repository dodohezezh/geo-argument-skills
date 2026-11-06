"""Portable evidence package for a committed, attested case.

A package is a directory that can leave the machine: the folded contract,
the trust-chain sidecars (registry record, ledger, attestation, anchor,
grounding ledger), the attested deliverables, a generated self-contained
HTML report, a SHA-256 manifest, a minimal RO-Crate metadata file, and a
README that says what the package is and is not.

The package remains a usable GeoArg case directory for the same engine
version, so a reader can run ``geoarg check .`` and ``geoarg verify .`` on
it, or run ``geoarg verify-package .`` to check every digest and the
cross-references in the manifest without trusting the manifest itself.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .audit import (
    canonical_sha256,
    case_digest,
    committed_record,
    file_sha256,
    ledger_entries,
    record_sha256,
)
from .attest import attestation_sha, read_attestation
from .contract import CASE_FILES, ContractError, load_case, validate
from .judge import judge

PACKAGE_SCHEMA_VERSION = "geoarg/package/0.1"
MANIFEST_FILE = "manifest.json"
README_FILE = "README.md"
RO_CRATE_FILE = "ro-crate-metadata.json"
REPORT_FILE = "files/report.html"

_ROLE_CONTRACT = "contract"
_ROLE_DELIVERABLE = "deliverable"
_ROLE_JUDGMENT = "judgment"
_ROLE_REPORT = "report"
_ROLE_RECORD = "record"
_ROLE_LEDGER = "ledger"
_ROLE_ATTESTATION = "attestation"
_ROLE_ANCHOR = "anchor"
_ROLE_GROUNDING = "grounding"
_ROLE_SOURCE = "source"
_ROLE_DOMAIN = "domain_pack"
_ROLE_FIGURE = "figure"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _copy_file(source: Path, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return {
        "sha256": file_sha256(target),
        "bytes": target.stat().st_size,
    }


def _safe_name(path: str) -> str:
    name = Path(path).name
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name) or "file"


def _resolve(case_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return case_root / path


def _unique(names: set[str], candidate: str) -> str:
    if candidate not in names:
        names.add(candidate)
        return candidate
    stem, suffix = Path(candidate).stem, Path(candidate).suffix
    index = 2
    while f"{stem}-{index}{suffix}" in names:
        index += 1
    final = f"{stem}-{index}{suffix}"
    names.add(final)
    return final


def _ledger_head(entries: list[dict[str, Any]]) -> str | None:
    if not entries:
        return None
    last = entries[-1]
    head = last.get("sha256") or last.get("record_sha256")
    return str(head) if head else None


def _grounding(root: Path) -> tuple[dict[str, Any] | None, Path | None]:
    paths = sorted((root / ".geoarg" / "ground").glob("*.json"))
    if not paths:
        return None, None
    path = paths[0]
    payload = _read_json(path)
    return payload, path


def _engine() -> dict[str, Any]:
    from .audit import engine_digest

    return {"version": __version__, "sha256": engine_digest()}


def _ro_crate(manifest: dict[str, Any]) -> dict[str, Any]:
    parts = [
        {"@id": entry["package_path"]}
        for entry in manifest.get("files", [])
        if entry.get("package_path") and entry["package_path"] != RO_CRATE_FILE
    ]
    parts.append({"@id": MANIFEST_FILE})
    author = (manifest.get("author") or "").strip()
    dataset: dict[str, Any] = {
        "@id": "./",
        "@type": "Dataset",
        "name": manifest.get("title") or manifest.get("claim_id") or "GeoArg evidence package",
        "description": "Portable GeoArg evidence package: contract, trust-chain sidecars, attested deliverables, and a digest manifest.",
        "datePublished": manifest.get("created_at"),
        "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
        "hasPart": parts,
    }
    if author:
        dataset["author"] = {"@id": "#author"}
    graph: list[dict[str, Any]] = [
        {
            "@id": RO_CRATE_FILE,
            "@type": "CreativeWork",
            "about": {"@id": "./"},
            "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
            "identifier": MANIFEST_FILE,
        },
        dataset,
    ]
    if author:
        graph.append({"@id": "#author", "@type": "Person", "name": author})
    return {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": graph}


def _readme(payload: dict[str, Any], lang: str) -> str:
    zh = lang.startswith("zh")
    lines: list[str] = []
    if zh:
        lines += [
            "# GeoArg 证据包",
            "",
            f"论证：{payload.get('title') or ''}（{payload.get('claim_id')}）",
            f"结论：{payload.get('verdict')}",
            f"规则版本：{payload.get('rule_version')}；引擎：{payload['engine']['version']}（{payload['engine']['sha256']}）",
            f"生成时间：{payload.get('created_at')}",
            "",
            "## 内容",
            "",
            "- `argument.yaml`、`evidence.yaml`、`test.yaml`：论证本身。",
            "- `.geoarg/`：提交记录、追加式台账、证明（attestation）、锚点（anchor）、接地台账。",
            "- `files/`：被证明绑定的产出、判断段落、生成的自包含 HTML 报告。",
            "- `manifest.json`：所有文件的 SHA-256 与信任链摘要。",
            "- `ro-crate-metadata.json`：最小 RO-Crate 1.1 元数据，便于仓储归档。",
            "",
            "## 怎么核对",
            "",
            "1. 在同一引擎版本上运行 `geoarg verify-package .`，它会重算全部摘要并核对台账、记录、证明与锚点。",
            "2. 把本目录当作普通案例：`geoarg check .`、`geoarg verify .`、`geoarg report . --format html`。",
            "3. 锚点若抄到本目录之外，可用 `geoarg verify . --anchor <那份 anchor.json>` 对照台账头。",
            "",
            "## 边界",
            "",
            "- 摘要只能证明字节一致，不证明数据本身为真。",
            "- 本地台账与锚点可被重写；外部保管与时间戳服务需要另外安排。",
            "- 接地只覆盖声明了的引文；没有 OCR，非 PDF 来源按单页处理。",
        ]
    else:
        lines += [
            "# GeoArg evidence package",
            "",
            f"Argument: {payload.get('title') or ''} ({payload.get('claim_id')})",
            f"Verdict: {payload.get('verdict')}",
            f"Rule version: {payload.get('rule_version')}; engine: {payload['engine']['version']} ({payload['engine']['sha256']})",
            f"Created: {payload.get('created_at')}",
            "",
            "## Contents",
            "",
            "- `argument.yaml`, `evidence.yaml`, `test.yaml`: the argument itself.",
            "- `.geoarg/`: committed record, append-only ledger, attestation, anchor, grounding ledger.",
            "- `files/`: attested deliverables, judgment text, and the generated self-contained HTML report.",
            "- `manifest.json`: SHA-256 for every file plus trust-chain summaries.",
            "- `ro-crate-metadata.json`: minimal RO-Crate 1.1 metadata for repository archiving.",
            "",
            "## How to check it",
            "",
            "1. On the same engine version run `geoarg verify-package .`; it recomputes every digest and checks the ledger, record, attestation and anchor.",
            "2. Treat the directory as a normal case: `geoarg check .`, `geoarg verify .`, `geoarg report . --format html`.",
            "3. If the anchor copy lives outside this directory, run `geoarg verify . --anchor <that anchor.json>` to compare the ledger head.",
            "",
            "## Boundaries",
            "",
            "- Digests prove byte identity, not that the data are true.",
            "- Local ledger and anchor can be rewritten; external custody and timestamp services are separate.",
            "- Grounding covers declared quotes only; there is no OCR, and non-PDF sources are treated as one page.",
        ]
    return "\n".join(lines) + "\n"


def build_package(
    case_root: str | Path,
    out_dir: str | Path,
    *,
    lang: str = "en",
    force: bool = False,
    include_source: bool = False,
    include_figures: bool = False,
) -> dict[str, Any]:
    """Write a portable evidence package; return its manifest payload."""
    root = Path(case_root)
    case = load_case(root)
    problems = validate(case)
    if problems:
        raise ContractError("invalid contract: " + "; ".join(problems))
    if case.chain:
        from .chain import chain_problems

        chain_problems = chain_problems(root)
        if chain_problems:
            raise ContractError("argument chain: " + "; ".join(chain_problems))
    record, record_path = committed_record(root)
    attestation = read_attestation(root)
    if attestation is None:
        raise ContractError(f"no attestation under {root}; run geoarg attest first")
    entries, ledger_problems = ledger_entries(root)
    if ledger_problems:
        raise ContractError("ledger: " + "; ".join(ledger_problems))
    if not entries:
        raise ContractError(f"no ledger entries under {root}; run geoarg commit first")

    out = Path(out_dir)
    if out.exists() and any(out.iterdir()) and not force:
        raise ContractError(f"output directory is not empty: {out}; pass --force to replace it")
    if out.exists() and force:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    created_at = _now()
    files: list[dict[str, Any]] = []
    used: set[str] = set()

    def add(source: Path, package_rel: str, role: str, source_path: str | None = None) -> dict[str, Any]:
        target = out / package_rel
        copied = _copy_file(source, target)
        entry = {
            "path": source_path if source_path is not None else package_rel,
            "package_path": package_rel,
            "role": role,
            **copied,
        }
        files.append(entry)
        return entry

    for name in CASE_FILES:
        source = root / name
        if source.is_file():
            add(source, name, _ROLE_CONTRACT, name)

    if case.domain_pack and case.domain_pack.get("path"):
        pack_path = Path(str(case.domain_pack["path"]))
        if pack_path.is_file():
            add(pack_path, "domain.yaml", _ROLE_DOMAIN, "domain.yaml")

    add(root / ".geoarg" / "ledger.jsonl", ".geoarg/ledger.jsonl", _ROLE_LEDGER, ".geoarg/ledger.jsonl")
    add(record_path, f".geoarg/registry/{record_path.name}", _ROLE_RECORD, f".geoarg/registry/{record_path.name}")

    attestation_path = root / ".geoarg" / "attestation.json"
    add(attestation_path, ".geoarg/attestation.json", _ROLE_ATTESTATION, ".geoarg/attestation.json")

    anchor_path = root / ".geoarg" / "anchor.json"
    anchor_payload = None
    if anchor_path.is_file():
        anchor_payload = _read_json(anchor_path)
        add(anchor_path, ".geoarg/anchor.json", _ROLE_ANCHOR, ".geoarg/anchor.json")

    grounding_payload, grounding_path = _grounding(root)
    if grounding_payload is not None and grounding_path is not None:
        add(grounding_path, ".geoarg/ground/C1.json", _ROLE_GROUNDING, ".geoarg/ground/C1.json")

    deliverable_entries = []
    for entry in attestation.get("deliverables") or []:
        source = _resolve(root, str(entry.get("path") or ""))
        if not source.is_file():
            raise ContractError(f"attested deliverable is missing: {source}")
        package_name = _unique(used, _safe_name(str(entry.get("path") or "deliverable")))
        package_rel = f"files/deliverables/{package_name}"
        add(source, package_rel, _ROLE_DELIVERABLE, str(entry.get("path")))
        deliverable_entries.append({**entry, "package_path": package_rel})

    judgment_entries = []
    for entry in attestation.get("judgment") or []:
        source = _resolve(root, str(entry.get("path") or ""))
        if not source.is_file():
            raise ContractError(f"attested judgment file is missing: {source}")
        package_name = _unique(used, _safe_name(str(entry.get("path") or "judgment")))
        package_rel = f"files/judgments/{package_name}"
        add(source, package_rel, _ROLE_JUDGMENT, str(entry.get("path")))
        judgment_entries.append({**entry, "package_path": package_rel})

    source_entry = None
    if include_source and grounding_payload:
        pdf = grounding_payload.get("pdf") or {}
        raw = pdf.get("path")
        if raw:
            source = _resolve(root, str(raw))
            if source.is_file():
                package_name = _unique(used, _safe_name(str(raw)))
                package_rel = f"files/sources/{package_name}"
                add(source, package_rel, _ROLE_SOURCE, str(raw))
                source_entry = {"path": str(raw), "package_path": package_rel, "sha256": file_sha256(source)}

    figure_entries: list[dict[str, Any]] = []
    if include_figures:
        figures_dir = root / "figures"
        if not figures_dir.is_dir():
            raise ContractError(
                "no figures directory to include; run geoarg figures <case> first or drop --include-figures"
            )
        for figure_path in sorted(figures_dir.glob("*.svg")):
            package_name = _unique(used, _safe_name(figure_path.name))
            package_rel = f"files/figures/{package_name}"
            add(figure_path, package_rel, _ROLE_FIGURE, str(figure_path.relative_to(root)))
            figure_entries.append(
                {
                    "path": str(figure_path.relative_to(root)),
                    "package_path": package_rel,
                    "sha256": file_sha256(figure_path),
                    "bytes": figure_path.stat().st_size,
                }
            )

    from .html import render_html
    from .report import build as build_report

    model = build_report(case, lang=lang)
    html_text = render_html(model, lang=lang)
    report_target = out / REPORT_FILE
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(html_text, encoding="utf-8")
    files.append(
        {
            "path": "report.html (generated)",
            "package_path": REPORT_FILE,
            "role": _ROLE_REPORT,
            "sha256": file_sha256(report_target),
            "bytes": report_target.stat().st_size,
        }
    )

    manifest: dict[str, Any] = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "created_at": created_at,
        "title": case.claim.get("statement") or case.claim.get("title") or record.get("title"),
        "claim_id": record.get("claim_id") or case.claim.get("id"),
        "verdict": record.get("verdict"),
        "rule_version": record.get("rule_version"),
        "author": (case.argument.get("audit") or {}).get("author"),
        "engine": _engine(),
        "case_digest": case_digest(root),
        "domain": None,
        "record": {
            "path": f".geoarg/registry/{record_path.name}",
            "sha256": record_sha256(record),
            "committed_at": record.get("committed_at"),
            "verdict": record.get("verdict"),
        },
        "ledger": {
            "path": ".geoarg/ledger.jsonl",
            "sha256": file_sha256(root / ".geoarg" / "ledger.jsonl"),
            "head": _ledger_head(entries),
            "count": len(entries),
        },
        "anchor": None,
        "attestation": {
            "path": ".geoarg/attestation.json",
            "sha256": file_sha256(attestation_path),
            "attestation_sha256": attestation_sha(attestation),
            "record_sha256": attestation.get("record_sha256"),
            "engine_sha256": attestation.get("engine_sha256"),
            "created_at": attestation.get("created_at"),
            "deliverables": deliverable_entries,
            "judgment": judgment_entries,
        },
        "grounding": None,
        "figures": figure_entries,
        "files": files,
    }
    if case.domain_pack and case.domain_pack.get("path"):
        manifest["domain"] = {
            "name": case.domain_pack.get("name"),
            "path": "domain.yaml",
            "file_sha256": file_sha256(Path(str(case.domain_pack["path"]))),
        }
    if anchor_payload is not None:
        manifest["anchor"] = {
            "path": ".geoarg/anchor.json",
            "sha256": file_sha256(anchor_path),
            "anchor_sha256": anchor_payload.get("anchor_sha256"),
            "record_sha256": anchor_payload.get("record_sha256"),
            "ledger_head": anchor_payload.get("ledger_head"),
            "ledger_count": anchor_payload.get("ledger_count"),
        }
    if grounding_payload is not None and grounding_path is not None:
        manifest["grounding"] = {
            "path": ".geoarg/ground/C1.json",
            "sha256": file_sha256(grounding_path),
            "acceptance_rate": grounding_payload.get("acceptance_rate"),
            "source": source_entry,
        }

    _write_json(out / MANIFEST_FILE, manifest)
    _write_json(out / RO_CRATE_FILE, _ro_crate(manifest))
    (out / README_FILE).write_text(_readme(manifest, lang), encoding="utf-8")
    return manifest


def _check_file(out: Path, entry: dict[str, Any], problems: list[str]) -> None:
    package_path = str(entry.get("package_path") or "")
    target = out / package_path
    if not target.is_file():
        problems.append(f"package file missing: {package_path}")
        return
    digest = file_sha256(target)
    if digest != entry.get("sha256"):
        problems.append(f"package file changed: {package_path}")
    if entry.get("bytes") is not None and target.stat().st_size != entry.get("bytes"):
        problems.append(f"package file size changed: {package_path}")


def verify_package(package_dir: str | Path) -> dict[str, Any]:
    """Check a package's digests and trust-chain cross-references."""
    out = Path(package_dir)
    manifest_path = out / MANIFEST_FILE
    if not manifest_path.is_file():
        raise ContractError(f"no {MANIFEST_FILE} under {out}")
    manifest = _read_json(manifest_path)
    problems: list[str] = []
    warnings: list[str] = []
    if manifest.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        problems.append(
            f"manifest schema_version is {manifest.get('schema_version')!r}, expected {PACKAGE_SCHEMA_VERSION!r}"
        )

    for entry in manifest.get("files") or []:
        _check_file(out, entry, problems)

    case = load_case(out)
    problems.extend(f"contract: {problem}" for problem in validate(case))
    verdict = judge(case)["verdict"]
    if verdict != manifest.get("verdict"):
        problems.append(f"verdict changed: manifest {manifest.get('verdict')}, recomputed {verdict}")
    if case_digest(out) != manifest.get("case_digest"):
        problems.append("contract file digests do not match the manifest")

    record_path = out / str((manifest.get("record") or {}).get("path") or ".geoarg/registry/C1.json")
    if not record_path.is_file():
        problems.append(f"record file missing: {record_path.name}")
    else:
        record = _read_json(record_path)
        digest = record_sha256(record)
        if digest != (manifest.get("record") or {}).get("sha256"):
            problems.append("record digest does not match the manifest")
        if record.get("verdict") != manifest.get("verdict"):
            problems.append(f"record verdict {record.get('verdict')!r} does not match manifest verdict {manifest.get('verdict')!r}")

    entries, ledger_problems = ledger_entries(out)
    problems.extend(f"ledger: {problem}" for problem in ledger_problems)
    ledger = manifest.get("ledger") or {}
    if ledger.get("count") is not None and len(entries) != ledger.get("count"):
        problems.append(f"ledger has {len(entries)} entries, manifest says {ledger.get('count')}")
    head = _ledger_head(entries)
    if ledger.get("head") and head != ledger.get("head"):
        problems.append("ledger head does not match the manifest")

    attestation = read_attestation(out)
    attestation_meta = manifest.get("attestation") or {}
    if attestation is None:
        problems.append("attestation is missing")
    else:
        if attestation_sha(attestation) != attestation_meta.get("attestation_sha256"):
            problems.append("attestation digest does not match the manifest")
        if attestation.get("record_sha256") != (manifest.get("record") or {}).get("sha256"):
            problems.append("attestation points at a different record")
        for entry in attestation_meta.get("deliverables") or []:
            target = out / str(entry.get("package_path") or "")
            if not target.is_file():
                problems.append(f"attested deliverable is missing: {entry.get('path')}")
                continue
            if file_sha256(target) != entry.get("sha256"):
                problems.append(f"attested deliverable changed: {entry.get('path')}")
        for entry in attestation_meta.get("judgment") or []:
            target = out / str(entry.get("package_path") or "")
            if not target.is_file():
                problems.append(f"attested judgment file is missing: {entry.get('path')}")
            elif file_sha256(target) != entry.get("sha256"):
                problems.append(f"attested judgment file changed: {entry.get('path')}")

    anchor_meta = manifest.get("anchor")
    if anchor_meta:
        anchor_path = out / str(anchor_meta.get("path") or ".geoarg/anchor.json")
        if not anchor_path.is_file():
            problems.append("anchor file is missing")
        else:
            anchor_payload = _read_json(anchor_path)
            if anchor_payload.get("record_sha256") != (manifest.get("record") or {}).get("sha256"):
                problems.append("anchor points at a different record")
            body = {key: value for key, value in anchor_payload.items() if key != "anchor_sha256"}
            if canonical_sha256(body) != anchor_payload.get("anchor_sha256"):
                problems.append("anchor file was edited after it was written")
            if anchor_payload.get("ledger_head") and entries:
                recorded = {
                    str(value)
                    for entry in entries
                    for value in (entry.get("sha256"), entry.get("record_sha256"))
                    if value
                }
                if str(anchor_payload.get("ledger_head")) not in recorded:
                    problems.append("anchor ledger head is not in the ledger")
            if anchor_payload.get("ledger_count") is not None and len(entries) < int(anchor_payload["ledger_count"]):
                problems.append("anchor checkpoint is newer than the ledger")

    grounding_meta = manifest.get("grounding")
    if grounding_meta:
        grounding_path = out / str(grounding_meta.get("path") or ".geoarg/ground/C1.json")
        if not grounding_path.is_file():
            problems.append("grounding ledger is missing")
        elif file_sha256(grounding_path) != grounding_meta.get("sha256"):
            problems.append("grounding ledger changed")
        source_meta = grounding_meta.get("source")
        if source_meta:
            source_path = out / str(source_meta.get("package_path") or "")
            if not source_path.is_file():
                problems.append("packaged source document is missing")
            elif file_sha256(source_path) != source_meta.get("sha256"):
                problems.append("packaged source document changed")

    if manifest.get("engine", {}).get("version") != __version__:
        warnings.append(
            f"package was produced by geoarg {manifest.get('engine', {}).get('version')}; "
            f"current engine is {__version__}"
        )
    return {"ok": not problems, "problems": problems, "warnings": warnings, "manifest": manifest}


def render_package(payload: dict[str, Any], lang: str = "en") -> str:
    zh = lang.startswith("zh")
    lines = ["# " + ("证据包" if zh else "Evidence package"), ""]
    lines.append(f"- {'论证' if zh else 'Argument'}: {payload.get('title') or ''} ({payload.get('claim_id')})")
    lines.append(f"- {'结论' if zh else 'Verdict'}: {payload.get('verdict')}")
    lines.append(f"- {'规则版本' if zh else 'Rule version'}: {payload.get('rule_version')}")
    lines.append(f"- {'引擎' if zh else 'Engine'}: {payload['engine']['version']} ({payload['engine']['sha256']})")
    lines.append(f"- {'文件数' if zh else 'Files'}: {len(payload.get('files') or [])}")
    lines.append(f"- {'台账' if zh else 'Ledger'}: {payload['ledger']['count']} entries, head {payload['ledger']['head']}")
    deliverable_count = len((payload.get("attestation") or {}).get("deliverables") or [])
    lines.append(f"- {'已绑定产出' if zh else 'Bound deliverables'}: {deliverable_count}")
    return "\n".join(lines) + "\n"


def render_verify(payload: dict[str, Any], lang: str = "en") -> str:
    zh = lang.startswith("zh")
    lines = []
    if payload["ok"]:
        lines.append("OK: " + ("证据包可核对。" if zh else "the package checks out."))
    else:
        lines.append("MISMATCH: " + ("证据包有问题。" if zh else "the package has problems."))
    for problem in payload["problems"]:
        lines.append(f"- {problem}")
    for warning in payload["warnings"]:
        lines.append(f"- warning: {warning}")
    return "\n".join(lines) + "\n"
