"""Richer domain packs: field guidance, pack patterns and advise."""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from geoarg import domains
from geoarg.advise import advise, advise_problems, render_advise
from geoarg.cli import main
from geoarg.contract import ContractError, load_case, validate
from geoarg.scaffold import all_patterns, list_patterns, new_case
from geoarg.schemas import validate_instance

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"
PACKS = EXAMPLES / "domain-packs"
GEO = PACKS / "geochronology"


def _pack(name):
    return domains.load_domain(PACKS / name)


class PackFieldsTests(unittest.TestCase):
    def test_pack_carries_field_guidance(self):
        pack = _pack("geochronology")
        self.assertEqual(pack["name"], "geochronology")
        self.assertEqual(len(pack["patterns"]), 1)
        self.assertIn("eruption-age", pack["test_suggestions"])
        self.assertEqual(pack["default_profile"]["primary"], "geochronology")
        self.assertEqual([row["name"] for row in pack["evidence_families"]], ["tephrochronology", "stratigraphy"])
        self.assertEqual(pack["grounding"]["formats"], ["pdf", "docx"])

    def test_pack_widens_enums(self):
        effective = domains.effective_enums(_pack("geochronology"))
        self.assertIn("tephrochronology", effective["method_types"])
        self.assertIn("eruption-age", effective["claim_kinds"])

    def test_all_example_packs_validate_against_the_schema(self):
        for path in sorted(PACKS.glob("*/domain.yaml")):
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(validate_instance(document, "domain"), [], path)

    def test_pack_rejects_unknown_enum_and_bad_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp) / "pack"
            pack_dir.mkdir()
            (pack_dir / "domain.yaml").write_text(
                "schema_version: geoarg/domain/0.1\nname: bad\nenums:\n  colour:\n  - red\n",
                encoding="utf-8",
            )
            with self.assertRaises(ContractError) as caught:
                domains.load_domain(pack_dir)
            self.assertIn("cannot extend", str(caught.exception))
            (pack_dir / "domain.yaml").write_text(
                "schema_version: geoarg/domain/0.1\nname: bad\nenums:\n  claim_kinds:\n  - age-model\n"
                "test_suggestions:\n  age-model:\n  - not-a-method\n",
                encoding="utf-8",
            )
            with self.assertRaises(ContractError) as caught:
                domains.load_domain(pack_dir)
            self.assertIn("not an effective method type", str(caught.exception))


class PackPatternTests(unittest.TestCase):
    def test_pack_patterns_are_listed_with_their_source(self):
        pack = _pack("geochronology")
        rows = {row["name"]: row for row in list_patterns(pack)}
        self.assertIn("geochronology-age-bracket", rows)
        self.assertEqual(rows["geochronology-age-bracket"]["source"], "pack:geochronology")
        self.assertIn("builtin", {row["source"] for row in all_patterns(pack)})

    def test_new_case_uses_the_pack_pattern(self):
        pack = _pack("geochronology")
        with tempfile.TemporaryDirectory() as tmp:
            payload = new_case(Path(tmp) / "eruption", "geochronology-age-bracket", pack=pack)
            self.assertEqual(payload["pack"], "geochronology")
            self.assertEqual(payload["problems"], [])
            case = load_case(payload["root"])
            self.assertEqual(case.claim["kind"], "eruption-age")

    def test_new_case_without_pack_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = new_case(Path(tmp) / "plain", "geochronology-age-bracket")
            self.assertIsNone(payload["pack"])
            self.assertEqual(payload["problems"], [])


class AdviseTests(unittest.TestCase):
    def setUp(self):
        self.case = GEO / "age-bracket"

    def test_advise_payload_marks_present_and_missing(self):
        payload = advise(self.case)
        self.assertEqual(payload["pack"]["name"], "geochronology")
        tests = {row["method"]: row for row in payload["recommended_tests"]}
        self.assertTrue(tests["tephrochronology"]["present"])
        self.assertFalse(tests["cosmogenic-nuclide"]["present"])
        families = {row["name"]: row for row in payload["evidence_families"]}
        self.assertIn("tephrochronology", families)
        self.assertTrue(any("suggested test method" in line for line in advise_problems(payload)))

    def test_advise_render_zh(self):
        text = render_advise(advise(self.case), lang="zh")
        self.assertIn("领域建议", text)
        self.assertIn("建议的检验", text)
        self.assertIn("不改变判决", text)

    def test_advise_without_pack(self):
        payload = advise(EXAMPLES / "workspace-demo" / "basement-age")
        self.assertIsNone(payload["pack"])
        self.assertIn("no domain pack", payload["notes"])

    def test_cli_advise_json(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["advise", str(self.case), "--json"])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["pack"]["name"], "geochronology")

    def test_check_advise_warns_about_missing_suggestions(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            code = main(["check", str(self.case), "--advise"])
        text = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("WARNING: suggested test method 'cosmogenic-nuclide'", text)


class PackDigestTests(unittest.TestCase):
    def test_digest_changes_when_a_bundled_pattern_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp) / "pack"
            shutil.copytree(GEO, pack_dir)
            first = domains.domain_digest(pack_dir)
            self.assertIsNotNone(first)
            pattern = next(pack_dir.glob("patterns/*.yaml"))
            pattern.write_text(pattern.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
            second = domains.domain_digest(pack_dir)
            self.assertNotEqual(first["sha256"], second["sha256"])
            self.assertEqual(first["patterns"], second["patterns"])

    def test_case_inside_pack_sees_the_pack(self):
        case = GEO / "age-bracket"
        pack = domains.load_domain(case)
        self.assertIsNotNone(pack)
        self.assertEqual(validate(load_case(case)), [])


if __name__ == "__main__":
    unittest.main()
