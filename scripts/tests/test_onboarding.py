"""Tests for the 1.3 onboarding layer: adopt, patterns, draft profile."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml

from geoarg import adopt, scaffold
from geoarg.contract import CASE_FILES, ContractError, load_case, validate

REPO = Path(__file__).resolve().parents[2]
CASES = REPO / "examples"


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    from geoarg.cli import main

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class PatternTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-pattern-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_patterns_are_listed(self) -> None:
        names = [row["name"] for row in scaffold.list_patterns()]
        self.assertIn("geochronology-age-bracket", names)
        self.assertIn("stratigraphy-sequence-boundary", names)
        self.assertIn("tectonics-slip-rate", names)

    def test_every_pattern_renders_a_valid_case(self) -> None:
        for row in scaffold.list_patterns():
            with self.subTest(pattern=row["name"]):
                payload = scaffold.new_case(self.tmp / row["name"], row["name"])
                self.assertEqual(payload["problems"], [])
                self.assertGreater(payload["todos"], 0)
                for name in CASE_FILES:
                    self.assertTrue((self.tmp / row["name"] / name).exists())
                case = load_case(self.tmp / row["name"])
                self.assertEqual(validate(case), [])

    def test_new_case_refuses_to_overwrite(self) -> None:
        scaffold.new_case(self.tmp / "demo", "geochronology-age-bracket")
        with self.assertRaises(ContractError):
            scaffold.new_case(self.tmp / "demo", "geochronology-age-bracket")
        scaffold.new_case(self.tmp / "demo", "geochronology-age-bracket", force=True)

    def test_new_case_cli_and_draft_check(self) -> None:
        target = self.tmp / "cli-case"
        code, out, err = run_cli(["new", str(target), "--pattern", "stratigraphy-sequence-boundary"])
        self.assertEqual(code, 0, err)
        self.assertIn("case created", out)
        code, out, _ = run_cli(["check", str(target), "--profile", "draft", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["profile"], "draft")
        self.assertTrue(any("TODO" in warning for warning in payload["warnings"]))

    def test_pattern_catalogue_cli(self) -> None:
        code, out, _ = run_cli(["patterns"])
        self.assertEqual(code, 0)
        self.assertIn("tectonics-slip-rate", out)
        code, out, _ = run_cli(["patterns", "--json"])
        self.assertEqual(code, 0)
        rows = json.loads(out)
        self.assertGreaterEqual(len(rows), 3)


class AdoptTests(unittest.TestCase):
    MARKDOWN = """# Claim
- C1: The fault scarp records a single earthquake rupture.

# Premises
- P1: The scarp height is 3.2 m along the mapped trace. (evidence: ev.height)
- P2: The colluvial wedge above the scarp is 1.1 ka old. (evidence: ev.age)

# Evidence
- ev.height: Surveyed scarp height along 12 km of the mapped trace.
  - source: Field survey 2026
  - page: 1
  - quote: The scarp height is 3.2 m along the mapped trace.
- ev.age: OSL age of the colluvial wedge above the scarp.
  - source: Lab report 2026

# Tests
- T1: Trench the scarp and log the colluvial wedge.
"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-adopt-"))
        self.source = self.tmp / "notes.md"
        self.source.write_text(self.MARKDOWN, encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_parse_markdown_recovers_sections(self) -> None:
        sections = adopt.parse_markdown(self.MARKDOWN)
        self.assertEqual([row["id"] for row in sections["premises"]], ["P1", "P2"])
        self.assertEqual([row["id"] for row in sections["evidence"]], ["ev.height", "ev.age"])
        self.assertEqual(sections["evidence"][0]["meta"]["source"], "Field survey 2026")
        self.assertEqual(sections["evidence"][0]["meta"]["page"], "1")

    def test_adopt_writes_a_valid_draft(self) -> None:
        payload = adopt.adopt_markdown(self.source, self.tmp / "case")
        self.assertEqual(payload["problems"], [])
        self.assertGreater(payload["todos"], 0)
        case = load_case(self.tmp / "case")
        self.assertEqual(validate(case), [])
        argument = yaml.safe_load((self.tmp / "case" / "argument.yaml").read_text(encoding="utf-8"))
        self.assertEqual(argument["claim"]["statement"], "The fault scarp records a single earthquake rupture.")
        self.assertEqual(argument["premises"][0]["evidence_refs"], ["ev.height"])
        evidence = yaml.safe_load((self.tmp / "case" / "evidence.yaml").read_text(encoding="utf-8"))
        locator = evidence["records"][0]["source_locator"]
        self.assertEqual(locator["page"], 1)
        self.assertIn("scarp height", locator["quote"])

    def test_adopt_cli_and_draft_profile(self) -> None:
        target = self.tmp / "cli-adopt"
        code, out, err = run_cli(["adopt", str(self.source), "--out", str(target)])
        self.assertEqual(code, 0, err)
        self.assertIn("draft written", out)
        code, out, _ = run_cli(["check", str(target), "--profile", "draft", "--explain", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        self.assertIn("profile", payload)

    def test_adopt_refuses_to_overwrite(self) -> None:
        adopt.adopt_markdown(self.source, self.tmp / "case")
        with self.assertRaises(ContractError):
            adopt.adopt_markdown(self.source, self.tmp / "case")
        adopt.adopt_markdown(self.source, self.tmp / "case", force=True)

    def test_missing_markdown_is_an_error(self) -> None:
        with self.assertRaises(ContractError):
            adopt.adopt_markdown(self.tmp / "missing.md", self.tmp / "case")


class DraftProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-draft-"))
        self.case_dir = self.tmp / "case"
        shutil.copytree(CASES / "workspace-demo" / "basement-age", self.case_dir)
        argument_path = self.case_dir / "argument.yaml"
        argument = yaml.safe_load(argument_path.read_text(encoding="utf-8"))
        argument["claim"].pop("scope", None)
        argument.pop("audit", None)
        argument_path.write_text(yaml.safe_dump(argument, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_strict_profile_reports_missing_fields(self) -> None:
        case = load_case(self.case_dir)
        problems = validate(case)
        self.assertTrue(any("scope" in problem for problem in problems))
        code, out, _ = run_cli(["check", str(self.case_dir), "--json"])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(out)["ok"])

    def test_draft_profile_downgrades_completeness_gaps(self) -> None:
        code, out, _ = run_cli(["check", str(self.case_dir), "--profile", "draft", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        self.assertTrue(any("scope" in warning for warning in payload["warnings"]))

    def test_explain_adds_a_hint(self) -> None:
        from geoarg.contract import explain

        rows = explain(["argument: missing required field 'scope'"])
        self.assertIn("->", rows[0])
        code, out, _ = run_cli(["check", str(self.case_dir), "--explain"])
        self.assertEqual(code, 1)
        self.assertIn("->", out)


if __name__ == "__main__":
    unittest.main()
