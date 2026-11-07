"""External domain packs: extend the fixed enums and carry field knowledge.

A case may carry an optional ``domain.yaml`` at its root (or at the root of a
workbench above it). The pack names a domain direction, extends one or more
enumerations that are otherwise built into ``contract.py``, and may add
field-level guidance: a default profile, argument patterns, test suggestions,
expected evidence families, and grounding notes.

The pack is data: it is loaded, merged into the effective enum sets, and hashed
into the commit record so a later edit is reported by ``verify``. Patterns are
ordinary pattern files under the pack's ``patterns/`` directory, in the same
format the engine ships under ``_patterns/``.

The pack is a widening, never a redefinition: it can add values, not remove or
rewrite built-in ones. If two packs are nested, only the nearest one applies;
the engine never merges packs from several levels because that would make the
same case mean different things depending on where it is inspected from.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml

from .hashing import file_sha256

from .contract import ENUMS, EXTENSIBLE_ENUM_KEYS, ContractError

DOMAIN_FILE = "domain.yaml"
DOMAIN_SCHEMA_VERSION = "geoarg/domain/0.1"
DEFAULT_PATTERNS_DIR = "patterns"
_GROUNDING_FORMATS = ("pdf", "docx", "html", "markdown", "text")


def _fail(message: str) -> "ContractError":
    return ContractError(f"{DOMAIN_FILE}: {message}")


def _slug(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{where} must be a non-empty string")
    text = value.strip()
    if any(ch.isspace() for ch in text) or "/" in text or "\\" in text:
        raise _fail(f"{where} must be a slug without spaces or path separators: {value!r}")
    return text


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{where} must be a non-empty string")
    return value.strip()


def _patterns(dir_path: Path) -> list[dict[str, Any]]:
    if not dir_path.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(dir_path.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise _fail(f"cannot read pattern {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise _fail(f"pattern {path.name} must be a YAML mapping")
        missing = [key for key in ("name", "argument", "evidence", "test") if not data.get(key)]
        if missing:
            raise _fail(f"pattern {path.name} is missing {', '.join(missing)}")
        rows.append(
            {
                "name": str(data["name"]),
                "title": str(data.get("title") or data["name"]),
                "domain": str(data.get("domain") or "other"),
                "description": str(data.get("description") or ""),
                "argument": str(data["argument"]),
                "evidence": str(data["evidence"]),
                "test": str(data["test"]),
                "file": path.name,
                "sha256": file_sha256(path) or "",
            }
        )
    names = [row["name"] for row in rows]
    if len(names) != len(set(names)):
        raise _fail(f"patterns in {dir_path} repeat a name")
    return rows


def _suggestions(value: Any, enums: dict[str, set[str]]) -> dict[str, list[dict[str, str]]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _fail("test_suggestions must be a mapping of claim kind to a list")
    cleaned: dict[str, list[dict[str, str]]] = {}
    for claim_kind, rows in value.items():
        kind = _slug(claim_kind, "test_suggestions key")
        if kind not in enums["claim_kinds"]:
            raise _fail(f"test_suggestions key {kind!r} is not an effective claim kind")
        if not isinstance(rows, list) or not rows:
            raise _fail(f"test_suggestions.{kind} must be a non-empty list")
        cleaned[kind] = []
        for row in rows:
            if isinstance(row, str):
                method = _slug(row, f"test_suggestions.{kind}")
                why = ""
            elif isinstance(row, dict):
                method = _slug(row.get("method"), f"test_suggestions.{kind}.method")
                why = str(row.get("why") or "").strip()
            else:
                raise _fail(f"test_suggestions.{kind} entries must be a method or a mapping")
            if method not in enums["method_types"]:
                raise _fail(f"test_suggestions method {method!r} is not an effective method type")
            cleaned[kind].append({"method": method, "why": why})
    return cleaned


def _families(value: Any, enums: dict[str, set[str]]) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list) or not value:
        raise _fail("evidence_families must be a non-empty list")
    cleaned: list[dict[str, str]] = []
    for row in value:
        if isinstance(row, str):
            name = _slug(row, "evidence_families")
            independence_class = ""
            why = ""
        elif isinstance(row, dict):
            name = _slug(row.get("name"), "evidence_families.name")
            independence_class = str(row.get("independence_class") or "").strip()
            why = str(row.get("why") or "").strip()
        else:
            raise _fail("evidence_families entries must be a name or a mapping")
        if independence_class and independence_class not in enums["independence_classes"]:
            raise _fail(f"evidence family {name!r} uses unknown independence class {independence_class!r}")
        cleaned.append({"name": name, "independence_class": independence_class, "why": why})
    return cleaned


def _default_profile(value: Any, enums: dict[str, set[str]]) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise _fail("default_profile must be a mapping")
    primary = _slug(value.get("primary"), "default_profile.primary")
    if primary not in enums["profiles"]:
        raise _fail(f"default_profile.primary {primary!r} is not an effective profile")
    secondary = value.get("secondary") or []
    if not isinstance(secondary, list):
        raise _fail("default_profile.secondary must be a list")
    secondary_clean: list[str] = []
    for item in secondary:
        name = _slug(item, "default_profile.secondary")
        if name not in enums["profiles"]:
            raise _fail(f"default_profile secondary {name!r} is not an effective profile")
        secondary_clean.append(name)
    rationale = str(value.get("rationale") or "").strip()
    return {"primary": primary, "secondary": secondary_clean, "rationale": rationale}


def _grounding(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise _fail("grounding must be a mapping")
    formats = value.get("formats") or []
    if not isinstance(formats, list):
        raise _fail("grounding.formats must be a list")
    clean_formats: list[str] = []
    for item in formats:
        name = str(item).strip().lower()
        if name not in _GROUNDING_FORMATS:
            raise _fail(f"grounding format {item!r} is not one of {', '.join(_GROUNDING_FORMATS)}")
        clean_formats.append(name)
    notes = value.get("notes") or []
    if not isinstance(notes, list):
        raise _fail("grounding.notes must be a list of strings")
    return {"formats": clean_formats, "notes": [str(note).strip() for note in notes if str(note).strip()]}


def _load_file(path: Path) -> dict[str, Any]:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise _fail(f"cannot read {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise _fail(f"{path}: top level must be a mapping")
    version = doc.get("schema_version")
    if version not in (None, DOMAIN_SCHEMA_VERSION):
        raise _fail(f"schema_version must be {DOMAIN_SCHEMA_VERSION}")
    name = _slug(doc.get("name"), "name")
    enums = doc.get("enums")
    if enums is None:
        raise _fail("enums must be a mapping of enum name to a list of values")
    if not isinstance(enums, dict) or not enums:
        raise _fail("enums must be a non-empty mapping of enum name to a list of values")
    cleaned: dict[str, list[str]] = {}
    for key, values in enums.items():
        if key not in EXTENSIBLE_ENUM_KEYS:
            raise _fail(
                f"cannot extend {key!r}; extensible enums: {', '.join(EXTENSIBLE_ENUM_KEYS)}"
            )
        if not isinstance(values, list) or not values:
            raise _fail(f"enums.{key} must be a non-empty list")
        seen: set[str] = set()
        rows: list[str] = []
        for value in values:
            item = _slug(value, f"enums.{key}")
            if item in seen:
                raise _fail(f"enums.{key} repeats {item!r}")
            seen.add(item)
            rows.append(item)
        cleaned[key] = rows
    effective = {key: set(values) for key, values in ENUMS.items()}
    for key, values in cleaned.items():
        effective.setdefault(key, set()).update(values)
    patterns_dir = path.parent / str(doc.get("patterns_dir") or DEFAULT_PATTERNS_DIR)
    patterns = _patterns(patterns_dir) if patterns_dir.is_dir() else []
    return {
        "schema_version": DOMAIN_SCHEMA_VERSION,
        "name": name,
        "title": doc.get("title") or name,
        "description": doc.get("description") or "",
        "enums": cleaned,
        "patterns": patterns,
        "patterns_dir": str(patterns_dir),
        "default_profile": _default_profile(doc.get("default_profile"), effective),
        "test_suggestions": _suggestions(doc.get("test_suggestions"), effective),
        "evidence_families": _families(doc.get("evidence_families"), effective),
        "grounding": _grounding(doc.get("grounding")),
    }


def find_domain_file(case_root: str | Path) -> Path | None:
    """Return the nearest ``domain.yaml`` from the case directory upward."""
    override = os.environ.get("GEOARG_DOMAIN_FILE")
    if override:
        path = Path(override)
        if path.is_file():
            return path
        raise _fail(f"GEOARG_DOMAIN_FILE points at a missing file: {path}")
    root = Path(case_root).resolve()
    for parent in (root, *root.parents):
        candidate = parent / DOMAIN_FILE
        if candidate.is_file():
            return candidate
    return None


def load_domain(case_root: str | Path) -> dict[str, Any] | None:
    """Load and validate the pack that applies to one case, if any."""
    path = find_domain_file(case_root)
    if path is None:
        return None
    doc = _load_file(path)
    doc["path"] = path
    return doc


def effective_enums(pack: dict[str, Any] | None) -> dict[str, set[str]]:
    """Return built-in enums widened with the pack's values."""
    out: dict[str, set[str]] = {key: set(values) for key, values in ENUMS.items()}
    if not pack:
        return out
    for key, values in (pack.get("enums") or {}).items():
        out.setdefault(key, set()).update(values)
    return out


def pack_patterns(pack: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list((pack or {}).get("patterns") or [])


def domain_digest(case_root: str | Path) -> dict[str, Any] | None:
    """A stable identity for the pack that applies to a case."""
    pack = load_domain(case_root)
    if pack is None:
        return None
    payload = {
        "name": pack["name"],
        "schema_version": pack["schema_version"],
        "enums": {key: sorted(values) for key, values in pack["enums"].items()},
        "patterns": [
            {"name": row["name"], "sha256": row["sha256"]} for row in pack["patterns"]
        ],
        "default_profile": pack["default_profile"],
        "test_suggestions": pack["test_suggestions"],
        "evidence_families": pack["evidence_families"],
        "grounding": pack["grounding"],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "name": pack["name"],
        "path": str(pack["path"]),
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "values": {key: sorted(values) for key, values in pack["enums"].items()},
        "patterns": [row["name"] for row in pack["patterns"]],
    }


def builtin_enums() -> dict[str, list[str]]:
    return {key: sorted(values) for key, values in ENUMS.items()}


def _labels(lang: str) -> dict[str, str]:
    if str(lang).lower().startswith("zh"):
        return {
            "title": f"# 领域包（{DOMAIN_SCHEMA_VERSION}）",
            "active": "当前领域包",
            "file": "文件",
            "enums": "扩展的枚举",
            "patterns": "随包论证模式",
            "profile": "默认 profile",
            "suggestions": "检验建议",
            "families": "证据族",
            "grounding": "接地提示",
            "none": "当前案例没有 `domain.yaml`；使用内置枚举。",
            "builtin": "内置枚举",
            "note": "domain.yaml 只能加值，不能改内置语义；最近的 domain.yaml 生效（案例目录优先）。",
            "why": "理由",
        }
    return {
        "title": f"# Domain packs ({DOMAIN_SCHEMA_VERSION})",
        "active": "Active pack",
        "file": "File",
        "enums": "Extended enums",
        "patterns": "Bundled argument patterns",
        "profile": "Default profile",
        "suggestions": "Test suggestions",
        "families": "Evidence families",
        "grounding": "Grounding hints",
        "none": "This case has no `domain.yaml`; built-in enums apply.",
        "builtin": "Built-in enums",
        "note": "A domain.yaml can add values, never change built-in semantics; the nearest file wins (case directory first).",
        "why": "why",
    }


def render_domains(pack: dict[str, Any] | None, lang: str = "en") -> str:
    labels = _labels(lang)
    builtin = builtin_enums()
    if not pack:
        lines = [labels["title"], "", labels["none"], ""]
        lines.append(f"## {labels['builtin']}")
        for key in EXTENSIBLE_ENUM_KEYS:
            lines.append(f"- `{key}`: {', '.join(builtin[key])}")
        lines.append("")
        lines.append(labels["note"])
        return "\n".join(lines) + "\n"
    lines = [labels["title"], "", f"## {labels['active']}: {pack['name']}"]
    lines.append(f"- {labels['file']}: {pack['path']}")
    lines.append(f"- {labels['enums']}: {', '.join(sorted(pack['enums']))}")
    lines.append("")
    for key in sorted(pack["enums"]):
        values = ", ".join(sorted(set(pack["enums"][key]) | set(builtin.get(key, []))))
        lines.append(f"- `{key}`: {values}")
    if pack.get("patterns"):
        lines.append("")
        lines.append(f"## {labels['patterns']}")
        for row in pack["patterns"]:
            lines.append(f"- `{row['name']}` ({row['domain']}): {row['title']}")
            if row["description"]:
                lines.append(f"  {row['description']}")
    if pack.get("default_profile"):
        profile = pack["default_profile"]
        secondary = ", ".join(profile["secondary"]) if profile["secondary"] else "-"
        lines.append("")
        lines.append(f"## {labels['profile']}")
        lines.append(f"- primary: {profile['primary']}; secondary: {secondary}")
        if profile["rationale"]:
            lines.append(f"- {profile['rationale']}")
    if pack.get("test_suggestions"):
        lines.append("")
        lines.append(f"## {labels['suggestions']}")
        for kind in sorted(pack["test_suggestions"]):
            methods = ", ".join(row["method"] for row in pack["test_suggestions"][kind])
            lines.append(f"- `{kind}`: {methods}")
    if pack.get("evidence_families"):
        lines.append("")
        lines.append(f"## {labels['families']}")
        for row in pack["evidence_families"]:
            tail = f" ({row['independence_class']})" if row["independence_class"] else ""
            reason = f" - {row['why']}" if row["why"] else ""
            lines.append(f"- {row['name']}{tail}{reason}")
    if pack.get("grounding"):
        lines.append("")
        lines.append(f"## {labels['grounding']}")
        formats = ", ".join(pack["grounding"]["formats"]) or "-"
        lines.append(f"- formats: {formats}")
        for note in pack["grounding"]["notes"]:
            lines.append(f"- {note}")
    lines.append("")
    lines.append(f"## {labels['builtin']}")
    for key in EXTENSIBLE_ENUM_KEYS:
        lines.append(f"- `{key}`: {', '.join(builtin[key])}")
    lines.append("")
    lines.append(labels["note"])
    return "\n".join(lines) + "\n"
