"""Load and structurally validate a GeoArg case directory."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .results import validate_result_block

SCHEMA_VERSION = "geoarg/0.6"
CASE_FILES = ("argument.yaml", "evidence.yaml", "test.yaml")

_DOMAINS = {"plate-tectonics", "stratigraphy", "petrology", "geomorphology", "geophysics", "other"}
_LAYERS = {"L0", "L1", "L2", "L3", "L4"}
_CLAIM_KINDS = {"reconstruction", "timing", "correlation", "mechanism", "existence", "classification"}
_PREMISE_STATUS = {"untested", "supported", "defeated", "undetermined"}
_CP_TYPES = {"structural", "temporal", "methodological", "calibration"}
_DEFEATER_TYPES = {"rebutting", "undercutting"}
_SEVERITIES = {"fatal", "degrading"}
_ENTAILMENT_KINDS = {"geometric-consistency", "quantitative", "blind-prediction", "spatial-pattern", "temporal-pattern"}
_RISKS = {"low", "medium", "high"}
_POWERS = {"none", "low", "medium", "high"}
_TEST_STATUS = {"planned", "running", "passed", "failed", "not-run"}
_METHOD_TYPES = {
    "geometric-consistency",
    "statistical",
    "blind-prediction",
    "field-check",
    "numerical-model",
    "literature-review",
}
_EVIDENCE_KINDS = {"observation", "measurement", "compilation", "model-output", "literature-derived"}
_EVIDENCE_LAYERS = {"L1", "L2", "L3"}
_EVIDENCE_STATUS = {"accepted", "disputed", "retracted", "superseded"}
_INDEPENDENCE_CLASSES = {"physical", "method", "data", "shared-calibration"}
_VERIFICATION_LEVELS = {"transcription", "measurement", "interpretation"}
_GAP_KINDS = {"cannot-express", "ambiguous", "missing-field", "overspecified", "other"}
_GAP_SEVERITIES = {"blocking", "annoying", "minor"}
_PROFILES = {"general-geology", "geochronology", "planetary-geology", "tectonics"}

# The complete enum inventory. A ``domain.yaml`` pack may widen the values in
# EXTENSIBLE_ENUM_KEYS; the structural enums stay fixed because the verdict
# rules interpret them (layers, statuses, powers, risks).
ENUMS = {
    "domains": _DOMAINS,
    "profiles": _PROFILES,
    "claim_kinds": _CLAIM_KINDS,
    "layers": _LAYERS,
    "premise_status": _PREMISE_STATUS,
    "cp_types": _CP_TYPES,
    "defeater_types": _DEFEATER_TYPES,
    "severities": _SEVERITIES,
    "entailment_kinds": _ENTAILMENT_KINDS,
    "risks": _RISKS,
    "powers": _POWERS,
    "test_status": _TEST_STATUS,
    "method_types": _METHOD_TYPES,
    "evidence_kinds": _EVIDENCE_KINDS,
    "evidence_layers": _EVIDENCE_LAYERS,
    "evidence_status": _EVIDENCE_STATUS,
    "independence_classes": _INDEPENDENCE_CLASSES,
    "verification_levels": _VERIFICATION_LEVELS,
    "gap_kinds": _GAP_KINDS,
    "gap_severities": _GAP_SEVERITIES,
}
EXTENSIBLE_ENUM_KEYS = (
    "domains",
    "profiles",
    "claim_kinds",
    "method_types",
    "entailment_kinds",
    "cp_types",
    "defeater_types",
    "evidence_kinds",
    "verification_levels",
    "independence_classes",
    "gap_kinds",
)


class ContractError(Exception):
    """Raised when a case cannot be loaded."""


@dataclass
class Case:
    root: Path
    argument: dict[str, Any]
    evidence: dict[str, Any]
    tests: dict[str, Any]
    chain: dict[str, Any] = field(default_factory=dict)
    domain_pack: dict[str, Any] | None = field(default=None)

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


def load_case(root: str | Path, attach_chain: bool = True) -> Case:
    """Load the three contract files from a case directory.

    With ``attach_chain`` the case also carries the resolved states of its
    derived premises (see ``chain.py``). Loading a referenced argument from
    inside the chain resolver passes ``attach_chain=False`` to avoid recursion.
    """
    root = Path(root)
    argument = _load_yaml(root / "argument.yaml")
    evidence = _load_yaml(root / "evidence.yaml")
    tests = _load_yaml(root / "test.yaml")
    for name, doc in zip(CASE_FILES, (argument, evidence, tests)):
        if not isinstance(doc, dict):
            raise ContractError(f"{name}: top level must be a mapping")
    case = Case(root=root, argument=argument, evidence=evidence, tests=tests)
    from . import domains  # local import keeps domains.py free to import this module

    case.domain_pack = domains.load_domain(root)
    if attach_chain:
        try:
            from . import chain

            case.chain = chain.load_chain(root)
        except Exception:  # a broken chain must not hide a broken case
            case.chain = {}
    return case


def _need(problems: list[str], where: str, mapping: Any, keys: tuple[str, ...]) -> None:
    if not isinstance(mapping, dict):
        problems.append(f"{where}: expected a mapping")
        return
    for key in keys:
        if key not in mapping or mapping[key] in (None, "", []):
            problems.append(f"{where}: missing required field '{key}'")


def _dups(problems: list[str], where: str, records: Any) -> None:
    """Flag duplicate ids inside one collection; every id is a key elsewhere."""
    if not isinstance(records, list):
        return
    seen: set[Any] = set()
    dupes: list[str] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        rid = rec.get("id")
        if rid is None:
            continue
        if rid in seen:
            dupes.append(str(rid))
        seen.add(rid)
    if dupes:
        problems.append(f"{where}: duplicate id(s) {sorted(set(dupes))}")


def _effective_enums(case: "Case") -> dict[str, set[str]]:
    """Built-in enums widened by the case's domain pack, if any."""
    from . import domains

    return domains.effective_enums(case.domain_pack)


def validate(case: Case) -> list[str]:
    """Return every structural problem found. An empty list means the contract loads."""
    problems: list[str] = []
    enum_values = _effective_enums(case)
    _DOMAINS = enum_values["domains"]
    _LAYERS = enum_values["layers"]
    _CLAIM_KINDS = enum_values["claim_kinds"]
    _PREMISE_STATUS = enum_values["premise_status"]
    _CP_TYPES = enum_values["cp_types"]
    _DEFEATER_TYPES = enum_values["defeater_types"]
    _SEVERITIES = enum_values["severities"]
    _ENTAILMENT_KINDS = enum_values["entailment_kinds"]
    _RISKS = enum_values["risks"]
    _POWERS = enum_values["powers"]
    _TEST_STATUS = enum_values["test_status"]
    _METHOD_TYPES = enum_values["method_types"]
    _EVIDENCE_KINDS = enum_values["evidence_kinds"]
    _EVIDENCE_LAYERS = enum_values["evidence_layers"]
    _EVIDENCE_STATUS = enum_values["evidence_status"]
    _INDEPENDENCE_CLASSES = enum_values["independence_classes"]
    _VERIFICATION_LEVELS = enum_values["verification_levels"]
    _GAP_KINDS = enum_values["gap_kinds"]
    _GAP_SEVERITIES = enum_values["gap_severities"]
    argument = case.argument
    _need(
        problems,
        "argument",
        argument,
        ("schema_version", "id", "title", "domain", "claim", "premises", "inference", "audit"),
    )
    if argument.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"argument: schema_version must be {SCHEMA_VERSION}")
    if argument.get("domain") and argument["domain"] not in _DOMAINS:
        problems.append(f"argument: unknown domain {argument['domain']!r}")
    profile = argument.get("profile")
    if profile is not None:
        if not isinstance(profile, dict):
            problems.append("argument.profile: expected a mapping")
        else:
            primary = profile.get("primary")
            if primary not in _PROFILES:
                problems.append(f"argument.profile: primary must be one of {sorted(_PROFILES)}")
            secondary = profile.get("secondary")
            if secondary is not None and not isinstance(secondary, list):
                problems.append("argument.profile: secondary must be a list")
            elif secondary:
                seen: set[str] = set()
                dupes: list[str] = []
                for item in secondary:
                    if item not in _PROFILES:
                        problems.append(f"argument.profile: unknown secondary profile {item!r}")
                    if item == primary:
                        problems.append("argument.profile: secondary must not repeat the primary profile")
                    if item in seen:
                        dupes.append(str(item))
                    seen.add(item)
                if dupes:
                    problems.append(f"argument.profile: duplicate secondary profile(s) {sorted(set(dupes))}")
            rationale = profile.get("rationale")
            if rationale is not None and not isinstance(rationale, str):
                problems.append("argument.profile: rationale must be a string")
    audit = argument.get("audit", {})
    _need(problems, "argument.audit", audit, ("author", "created", "updated", "version"))

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
    _dups(problems, "premises", premises)
    for p in premises:
        where = f"premise {p.get('id')}"
        _need(problems, where, p, ("id", "statement", "kind", "layer", "status"))
        if p.get("layer") and p["layer"] not in _LAYERS:
            problems.append(f"{where}: unknown layer {p['layer']!r}")
        if p.get("status") and p["status"] not in _PREMISE_STATUS:
            problems.append(f"{where}: unknown status {p['status']!r}")
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
    _dups(problems, "inference.cp", inference.get("cp"))
    for c in inference.get("cp", []):
        where = f"cp {c.get('id')}"
        _need(problems, where, c, ("id", "statement", "cp_type", "state"))
        if c.get("cp_type") not in _CP_TYPES:
            problems.append(f"{where}: unknown cp_type {c.get('cp_type')!r}")
        if c.get("state") not in {"unknown", "holds", "fails"}:
            problems.append(f"{where}: state must be unknown, holds, or fails")
        if c.get("test_ref") not in test_ids:
            problems.append(f"{where}: every ceteris paribus condition needs a test_ref into test.yaml")
    _dups(problems, "inference.defeaters", inference.get("defeaters"))
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
    _dups(problems, "entailments", entailments)
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
    if not isinstance(argument.get("gaps"), list):
        problems.append("argument: gaps must be a list (declare [] when the contract has no gaps)")

    for gap in argument.get("gaps", []):
        where = f"gap {gap.get('kind')}"
        _need(problems, where, gap, ("kind", "description", "severity"))
        if gap.get("kind") not in _GAP_KINDS:
            problems.append(f"{where}: unknown gap kind {gap.get('kind')!r}")
        if gap.get("severity") not in _GAP_SEVERITIES:
            problems.append(f"{where}: unknown gap severity {gap.get('severity')!r}")

    condition_ids: set[Any] = set()
    for collection in (premises, inference.get("cp", []), inference.get("defeaters", []), entailments):
        for item in collection or []:
            if isinstance(item, dict) and item.get("id") is not None:
                condition_ids.add(item.get("id"))

    _dups(problems, "evidence", case.evidence.get("records"))
    for rec in case.evidence.get("records", []):
        where = f"evidence {rec.get('id')}"
        _need(
            problems,
            where,
            rec,
            ("id", "kind", "layer", "statement", "source", "coverage", "independence", "verification", "status"),
        )
        if rec.get("kind") and rec["kind"] not in _EVIDENCE_KINDS:
            problems.append(f"{where}: unknown kind {rec['kind']!r}")
        if rec.get("layer") and rec["layer"] not in _EVIDENCE_LAYERS:
            problems.append(f"{where}: layer must be L1, L2, or L3")
        if rec.get("status") and rec["status"] not in _EVIDENCE_STATUS:
            problems.append(f"{where}: status must be accepted, disputed, retracted, or superseded")
        source = rec.get("source")
        if not isinstance(source, dict) or not str(source.get("citation") or "").strip():
            problems.append(f"{where}: source.citation is required")
        coverage = rec.get("coverage", {})
        for key in ("spatial_extent", "coverage_fraction", "detectability"):
            if coverage.get(key) in (None, ""):
                problems.append(f"{where}: coverage.{key} is required (absence of evidence needs a coverage field)")
        for key in ("coverage_fraction", "detectability"):
            value = coverage.get(key)
            if isinstance(value, (int, float)) and not 0 <= value <= 1:
                problems.append(f"{where}: coverage.{key} must be between 0 and 1")
        independence = rec.get("independence", {})
        if independence.get("family") in (None, ""):
            problems.append(f"{where}: independence.family is required")
        if independence.get("independence_class") not in _INDEPENDENCE_CLASSES:
            problems.append(
                f"{where}: independence.independence_class must be physical, method, data, or shared-calibration"
            )
        level = (rec.get("verification") or {}).get("level")
        if level not in _VERIFICATION_LEVELS:
            problems.append(f"{where}: verification.level must be transcription, measurement, or interpretation")
        locator = rec.get("source_locator")
        if locator is not None:
            if not isinstance(locator, dict):
                problems.append(f"{where}: source_locator must be a mapping")
            else:
                page = locator.get("page")
                quote = locator.get("quote")
                if not isinstance(page, int) or page < 1:
                    problems.append(f"{where}: source_locator.page must be a positive integer")
                if not isinstance(quote, str) or not quote.strip():
                    problems.append(f"{where}: source_locator.quote must be a non-empty string")
        if level == "transcription" and rec.get("status") == "accepted":
            if not isinstance(locator, dict) or not locator.get("quote"):
                problems.append(
                    f"{where}: accepted transcription-level evidence needs source_locator with page and quote"
                )

    _dups(problems, "tests", case.tests.get("records"))
    for test in case.tests.get("records", []):
        where = f"test {test.get('id')}"
        _need(problems, where, test, ("id", "name", "checks", "method", "discriminating_power"))
        name = test.get("name")
        if isinstance(name, str) and len(name.strip()) < 3:
            problems.append(f"{where}: name must be at least 3 characters")
        checks = test.get("checks")
        if not isinstance(checks, list) or not checks:
            problems.append(f"{where}: checks must list at least one condition id")
        else:
            for check in checks:
                if check not in condition_ids:
                    problems.append(f"{where}: unknown condition in checks: {check!r}")
        method = test.get("method")
        _need(problems, f"{where}.method", method, ("type", "description"))
        if isinstance(method, dict) and method.get("type") not in _METHOD_TYPES:
            problems.append(f"{where}: method.type must be one of {sorted(_METHOD_TYPES)}")
        blind = test.get("blind")
        if not isinstance(blind, dict) or "is_blind" not in blind:
            problems.append(f"{where}: blind.is_blind is required")
        cost = test.get("cost")
        if cost is not None and (not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0):
            problems.append(f"{where}: cost must be a non-negative number")
        if test.get("discriminating_power") not in _POWERS:
            problems.append(f"{where}: discriminating_power must be none, low, medium, or high")
        problems.extend(validate_result_block(test))
        status = test.get("status")
        if status is not None and status not in _TEST_STATUS:
            problems.append(f"{where}: unknown status {status!r}")
        elif status is None and not (isinstance(test.get("result"), dict) and isinstance(test.get("pass_rule"), dict)):
            problems.append(f"{where}: status is required when no result/pass_rule pair is given")

    return problems


# Draft profile and fix hints ------------------------------------------------

_DRAFT_SOFT_MARKERS = (
    "missing required field 'scope'",
    "missing required field 'layer'",
    "missing required field 'audit'",
    "missing required field 'author'",
    "missing required field 'created'",
    "missing required field 'updated'",
    "missing required field 'version'",
    "missing required field 'gaps'",
    "missing required field 'dependencies'",
    "missing required field 'profile'",
    "missing required field 'rationale'",
    "missing required field 'spatial_extent'",
    "missing required field 'coverage_fraction'",
    "missing required field 'detectability'",
    "missing required field 'family'",
    "missing required field 'independence_class'",
    "missing required field 'derived_from'",
    "missing required field 'shared_sources'",
    "missing required field 'verification'",
    "missing required field 'level'",
    "missing required field 'source'",
    "missing required field 'citation'",
    "lists no evidence_refs",
    "at least one entailment is required",
)


def split_draft(problems: list[str]) -> tuple[list[str], list[str]]:
    """Split structural problems into draft errors and completeness warnings.

    The draft profile keeps every cross-reference and enum as an error: a typo
    is still a typo. It only softens fields that a first draft can reasonably
    leave incomplete (scope text, audit block, coverage numbers, optional
    rationale) and the "add at least one entailment" completeness rule.
    """
    errors: list[str] = []
    warnings: list[str] = []
    for problem in problems:
        if any(marker in problem for marker in _DRAFT_SOFT_MARKERS):
            warnings.append(problem)
        else:
            errors.append(problem)
    return errors, warnings


_HELP = (
    ("missing required field", "add the field with a real value; contract-fields.md lists the shape", "补上这个字段并给出真实内容；字段形状见 contract-fields.md"),
    ("expected a mapping", "use a YAML mapping here (key: value pairs)", "这里需要 YAML 映射（key: value 形式）"),
    ("unknown kind", "use one of the kinds listed in contract-fields.md", "从 contract-fields.md 列出的取值里选一个"),
    ("unknown status", "use one of the statuses listed in contract-fields.md", "从 contract-fields.md 列出的状态里选一个"),
    ("unknown state", "use one of the states listed in contract-fields.md", "从 contract-fields.md 列出的状态里选一个"),
    ("duplicate id", "give every record a unique id", "每个记录的 id 必须唯一"),
    ("gaps must be a list", "write [] when the contract has no gaps", "没有缺口时也要写 []"),
    ("lists no evidence_refs", "point the premise at an evidence id, or mark it derived", "给这条前提至少一个证据 id，或把它标成 derived"),
    ("at least one entailment", "add an entailment: a prediction that fails if the claim is wrong", "补一条推论：如果结论错了，它应该失败"),
    ("test_ref", "point the condition at an existing test id", "让这个条件指向一个已存在的测试 id"),
    ("must reference", "make the id point at a record that exists in this case", "让这个 id 指向本案例里确实存在的记录"),
)


def explain(problems: list[str], lang: str = "en") -> list[str]:
    """Attach one fix hint to each validation problem."""
    zh = str(lang).lower().startswith("zh")
    rows: list[str] = []
    for problem in problems:
        hint = ""
        for needle, en_hint, zh_hint in _HELP:
            if needle in problem:
                hint = zh_hint if zh else en_hint
                break
        rows.append(f"{problem} -> {hint}" if hint else problem)
    return rows

