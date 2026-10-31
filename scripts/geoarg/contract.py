"""Load and structurally validate a GeoArg case directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "geoarg/0.1"
CASE_FILES = ("argument.yaml", "evidence.yaml", "test.yaml")

_LAYERS = {"L0", "L1", "L2", "L3", "L4"}
_CLAIM_KINDS = {"reconstruction", "timing", "correlation", "mechanism", "existence", "classification"}
_CP_TYPES = {"structural", "temporal", "methodological", "calibration"}
_DEFEATER_TYPES = {"rebutting", "undercutting"}
_SEVERITIES = {"fatal", "degrading"}
_ENTAILMENT_KINDS = {"geometric-consistency", "quantitative", "blind-prediction", "spatial-pattern", "temporal-pattern"}
_RISKS = {"low", "medium", "high"}
_POWERS = {"none", "low", "medium", "high"}
_TEST_STATUS = {"planned", "running", "passed", "failed", "not-run"}
_GAP_KINDS = {"cannot-express", "ambiguous", "missing-field", "overspecified", "other"}
_GAP_SEVERITIES = {"blocking", "annoying", "minor"}


class ContractError(Exception):
    """Raised when a case cannot be loaded."""


@dataclass
class Case:
    root: Path
    argument: dict[str, Any]
    evidence: dict[str, Any]
    tests: dict[str, Any]

    @property
    def claim(self) -> dict[str, Any]:
        return self.argument.get("claim", {})

    @property
    def evidence_by_id(self) -> dict[str, dict[str, Any]]:
        return {r.get("id"): r for r in self.evidence.get("records", [])}

    @property
    def tests_by_id(self) -> dict[str, dict[str, Any]]:
        return {r.get("id"): r for r in self.tests.get("records", [])}


def _load_yaml(path: Path) -> Any:
    if not path.is_file():
        raise ContractError(f"missing file: {path.name} (expected in {path.parent})")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_case(root: str | Path) -> Case:
    """Load the three contract files from a case directory."""
    root = Path(root)
    argument = _load_yaml(root / "argument.yaml")
    evidence = _load_yaml(root / "evidence.yaml")
    tests = _load_yaml(root / "test.yaml")
    for name, doc in zip(CASE_FILES, (argument, evidence, tests)):
        if not isinstance(doc, dict):
            raise ContractError(f"{name}: top level must be a mapping")
    return Case(root=root, argument=argument, evidence=evidence, tests=tests)


def _need(problems: list[str], where: str, mapping: Any, keys: tuple[str, ...]) -> None:
    if not isinstance(mapping, dict):
        problems.append(f"{where}: expected a mapping")
        return
    for key in keys:
        if key not in mapping or mapping[key] in (None, "", []):
            problems.append(f"{where}: missing required field '{key}'")


def validate(case: Case) -> list[str]:
    """Return every structural problem found. An empty list means the contract loads."""
    problems: list[str] = []
    argument = case.argument
    _need(problems, "argument", argument, ("schema_version", "id", "title", "claim", "premises", "inference"))
    if argument.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"argument: schema_version must be {SCHEMA_VERSION}")

    claim = argument.get("claim", {})
    _need(problems, "claim", claim, ("id", "statement", "kind", "layer", "scope"))
    if claim.get("layer") and claim["layer"] not in _LAYERS:
        problems.append(f"claim: unknown layer {claim['layer']!r}")
    if claim.get("kind") and claim["kind"] not in _CLAIM_KINDS:
        problems.append(f"claim: unknown kind {claim['kind']!r}")

    evidence_ids = set(case.evidence_by_id)
    test_ids = set(case.tests_by_id)

    premises = argument.get("premises", [])
    if not premises:
        problems.append("argument: at least one premise is required")
    for p in premises:
        where = f"premise {p.get('id')}"
        _need(problems, where, p, ("id", "statement", "kind", "layer", "status"))
        kind = p.get("kind")
        if kind == "evidenced":
            refs = p.get("evidence_refs") or []
            if not refs:
                problems.append(f"{where}: an evidenced premise needs evidence_refs")
            for ref in refs:
                if ref not in evidence_ids:
                    problems.append(f"{where}: unknown evidence_ref {ref!r}")
        elif kind == "derived":
            if not p.get("argument_ref"):
                problems.append(f"{where}: a derived premise needs argument_ref")
        else:
            problems.append(f"{where}: kind must be 'evidenced' or 'derived'")
        for ref in p.get("test_refs") or []:
            if ref not in test_ids:
                problems.append(f"{where}: unknown test_ref {ref!r}")

    inference = argument.get("inference", {})
    _need(problems, "inference", inference, ("rule_id", "warrant"))
    for c in inference.get("cp", []):
        where = f"cp {c.get('id')}"
        _need(problems, where, c, ("id", "statement", "cp_type", "state"))
        if c.get("cp_type") not in _CP_TYPES:
            problems.append(f"{where}: unknown cp_type {c.get('cp_type')!r}")
        if c.get("state") not in {"unknown", "holds", "fails"}:
            problems.append(f"{where}: state must be unknown, holds, or fails")
        if c.get("test_ref") not in test_ids:
            problems.append(f"{where}: every ceteris paribus condition needs a test_ref into test.yaml")
    for d in inference.get("defeaters", []):
        where = f"defeater {d.get('id')}"
        _need(problems, where, d, ("id", "type", "statement", "severity", "state"))
        if d.get("type") not in _DEFEATER_TYPES:
            problems.append(f"{where}: type must be rebutting or undercutting")
        if d.get("severity") not in _SEVERITIES:
            problems.append(f"{where}: severity must be fatal or degrading")
        if d.get("state") not in {"unknown", "established", "refuted"}:
            problems.append(f"{where}: state must be unknown, established, or refuted")
        if d.get("test_ref") not in test_ids:
            problems.append(f"{where}: a defeat condition without a test is rhetoric; add test_ref")

    entailments = argument.get("entailments", [])
    if not entailments:
        problems.append("argument: at least one entailment is required")
    for e in entailments:
        where = f"entailment {e.get('id')}"
        _need(problems, where, e, ("id", "statement", "kind", "risk", "status"))
        if e.get("kind") not in _ENTAILMENT_KINDS:
            problems.append(f"{where}: unknown kind {e.get('kind')!r}")
        if e.get("risk") not in _RISKS:
            problems.append(f"{where}: risk must be low, medium, or high")
        if e.get("test_ref") not in test_ids:
            problems.append(f"{where}: an entailment without a test cannot be verified")

    _need(problems, "dependencies", argument.get("dependencies", {}), ())

    for gap in argument.get("gaps", []):
        where = f"gap {gap.get('kind')}"
        _need(problems, where, gap, ("kind", "description", "severity"))
        if gap.get("kind") not in _GAP_KINDS:
            problems.append(f"{where}: unknown gap kind {gap.get('kind')!r}")
        if gap.get("severity") not in _GAP_SEVERITIES:
            problems.append(f"{where}: unknown gap severity {gap.get('severity')!r}")

    for rec in case.evidence.get("records", []):
        where = f"evidence {rec.get('id')}"
        _need(problems, where, rec, ("id", "kind", "layer", "statement", "source", "coverage", "independence", "status"))
        coverage = rec.get("coverage", {})
        for key in ("spatial_extent", "coverage_fraction", "detectability"):
            if coverage.get(key) in (None, ""):
                problems.append(f"{where}: coverage.{key} is required (absence of evidence needs a coverage field)")
        for key in ("coverage_fraction", "detectability"):
            value = coverage.get(key)
            if isinstance(value, (int, float)) and not 0 <= value <= 1:
                problems.append(f"{where}: coverage.{key} must be between 0 and 1")
        if rec.get("independence", {}).get("family") in (None, ""):
            problems.append(f"{where}: independence.family is required")

    for test in case.tests.get("records", []):
        where = f"test {test.get('id')}"
        _need(problems, where, test, ("id", "method", "discriminating_power", "status"))
        if test.get("discriminating_power") not in _POWERS:
            problems.append(f"{where}: discriminating_power must be none, low, medium, or high")
        if test.get("status") not in _TEST_STATUS:
            problems.append(f"{where}: unknown status {test.get('status')!r}")

    return problems
