"""Access to the JSON Schemas shipped inside the package.

The schemas are documentation and a second opinion, not the authoritative
validator: `contract.validate` is the contract. They ship in the wheel so a
consumer can validate a case, a workspace, an attestation, or an anchor without
cloning this repository.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_DIR = Path(__file__).resolve().parent / "_schema"
_NAMES = (
    "argument",
    "evidence",
    "test",
    "bundle",
    "workspace",
    "attestation",
    "anchor",
    "domain",
)


class SchemaError(Exception):
    """Raised when a schema is missing or a validator is unavailable."""


def schema_path(name: str) -> Path:
    clean = name.replace(".schema.json", "").replace(".json", "")
    if clean not in _NAMES:
        raise SchemaError(f"unknown schema: {name!r}; known: {', '.join(_NAMES)}")
    path = SCHEMA_DIR / f"{clean}.schema.json"
    if not path.is_file():
        raise SchemaError(f"schema not shipped with this installation: {path}")
    return path


def schema_text(name: str) -> str:
    return schema_path(name).read_text(encoding="utf-8")


def schema_document(name: str) -> dict[str, Any]:
    return json.loads(schema_text(name))


def list_schemas() -> list[str]:
    return [name for name in _NAMES if (SCHEMA_DIR / f"{name}.schema.json").is_file()]


def validate_instance(instance: Any, name: str) -> list[str]:
    """Validate against one shipped schema when `jsonschema` is available."""
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise SchemaError(
            "jsonschema is not installed; install it with: pip install geoarg[schema]"
        ) from exc
    validator = jsonschema.Draft202012Validator(schema_document(name))
    problems = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path)):
        where = "/".join(str(part) for part in error.absolute_path) or "<root>"
        problems.append(f"{where}: {error.message}")
    return problems
