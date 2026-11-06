"""Tests for the paper bundle, the schema migration, and the CLI wiring."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from geoarg import cli
from geoarg.bundle import BUNDLE_SCHEMA_VERSION, build_bundle, render_bundle
from geoarg.migrate import migrate
from geoarg.contract import SCHEMA_VERSION

REPO = Path(__file__).resolve().parents[2]
CASES = REPO / "examples"


def _copy(name: str, target: Path) -> Path:
    destination = target / name
    shutil.copytree(CASES / name, destination)
    return destination


def _write_bundle(root: Path, claims: list[dict], schema: str = BUNDLE_SCHEMA_VERSION) -> Path:
    path = root / "bundle.yaml"
    payload = {"schema_version": schema, "id": "paper.test", "title": "Test paper", "claims": claims}
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def _defeated_copy(root: Path) -> Path:
    defeated = root / "defeated-case"
    shutil.copytree(CASES / "paper-demo", defeated)
    argument = defeated / "argument.yaml"
    payload = yaml.safe_load(argument.read_text(encoding="utf-8"))
    payload["inference"]["defeaters"][0]["state"] = "established"
    argument.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return defeated


class BundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        _copy("south-atlantic", self.root)
        _copy("paper-demo", self.root)

    def test_aggregate_takes_the_weakest_required_claim(self) -> None:
        _write_bundle(
            self.root,
            [
                {"case": "south-atlantic", "label": "tectonic reconstruction"},
                {"case": "paper-demo", "label": "timing"},
            ],
        )
        payload = build_bundle(self.root)
        self.assertTrue(payload["ok"], payload["problems"])
        verdicts = [row["verdict"] for row in payload["claims"]]
        self.assertEqual(verdicts, ["UNTESTED", "UNTESTED"])
        self.assertEqual(payload["aggregate"], "UNTESTED")

    def test_aggregate_takes_the_most_severe_required_claim(self) -> None:
        defeated = _defeated_copy(self.root)
        self.assertTrue(defeated.is_dir())
        _write_bundle(
            self.root,
            [
                {"case": "south-atlantic"},
                {"case": "defeated-case"},
            ],
        )
        payload = build_bundle(self.root)
        self.assertTrue(payload["ok"], payload["problems"])
        self.assertEqual([row["verdict"] for row in payload["claims"]], ["UNTESTED", "DEFEATED"])
        self.assertEqual(payload["aggregate"], "DEFEATED")

    def test_optional_claim_does_not_change_the_aggregate(self) -> None:
        _write_bundle(
            self.root,
            [
                {"case": "paper-demo"},
                {"case": "south-atlantic", "required": False},
            ],
        )
        payload = build_bundle(self.root)
        self.assertEqual(payload["aggregate"], "UNTESTED")

    def test_missing_case_is_a_problem(self) -> None:
        _write_bundle(self.root, [{"case": "no-such-case"}])
        payload = build_bundle(self.root)
        self.assertFalse(payload["ok"])
        self.assertIn("missing", payload["claims"][0]["verdict"])
        self.assertTrue(any("case not found" in problem for problem in payload["problems"]))

    def test_invalid_case_is_reported(self) -> None:
        _write_bundle(self.root, [{"case": "south-atlantic"}])
        argument = self.root / "south-atlantic" / "argument.yaml"
        text = argument.read_text(encoding="utf-8").replace('schema_version: geoarg/0.7', 'schema_version: geoarg/9.9')
        argument.write_text(text, encoding="utf-8")
        payload = build_bundle(self.root)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["claims"][0]["verdict"], "invalid")
        self.assertTrue(any("schema_version" in problem for problem in payload["problems"]))

    def test_bundle_schema_mismatch_is_a_problem(self) -> None:
        _write_bundle(self.root, [{"case": "south-atlantic"}], schema="geoarg/bundle/0.0")
        payload = build_bundle(self.root)
        self.assertFalse(payload["ok"])
        self.assertTrue(any("bundle schema" in problem for problem in payload["problems"]))

    def test_render_bundle_en_and_zh(self) -> None:
        _write_bundle(self.root, [{"case": "south-atlantic"}])
        english = render_bundle(self.root, "en")
        chinese = render_bundle(self.root, "zh")
        self.assertIn("Test paper", english)
        self.assertIn("bundle conclusion: UNTESTED", english)
        self.assertIn("论文结论", chinese)
        self.assertIn("未检验", chinese)

    def test_missing_bundle_file(self) -> None:
        payload = build_bundle(self.root / "empty")
        self.assertFalse(payload["ok"])
        self.assertTrue(any("no bundle.yaml" in problem for problem in payload["problems"]))


class MigrateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_migrate_is_idempotent_and_preserves_everything_else(self) -> None:
        case = _copy("south-atlantic", self.root)
        for name in ("argument.yaml", "evidence.yaml", "test.yaml"):
            path = case / name
            path.write_text(
                path.read_text(encoding="utf-8").replace(f"schema_version: {SCHEMA_VERSION}", "schema_version: geoarg/0.4"),
                encoding="utf-8",
            )
        before = (case / "argument.yaml").read_text(encoding="utf-8")
        rows = migrate(case, dry_run=True)
        self.assertTrue(all(row["changed"] for row in rows))
        self.assertEqual((case / "argument.yaml").read_text(encoding="utf-8"), before)
        migrate(case)
        after = (case / "argument.yaml").read_text(encoding="utf-8")
        old_line = f"schema_version: {SCHEMA_VERSION}"
        self.assertIn(old_line, after)
        again = migrate(case)
        self.assertTrue(all(not row["changed"] for row in again))

    def test_migration_changes_only_the_version_line(self) -> None:
        case = _copy("south-atlantic", self.root)
        path = case / "evidence.yaml"
        text = path.read_text(encoding="utf-8").replace(f"schema_version: {SCHEMA_VERSION}", "schema_version: geoarg/0.4", 1)
        path.write_text(text, encoding="utf-8")
        before = path.read_text(encoding="utf-8").splitlines()
        migrate(case)
        after = path.read_text(encoding="utf-8").splitlines()
        differences = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(len(differences), 1)
        self.assertIn("schema_version", differences[0][0])

    def test_migrate_bundle(self) -> None:
        _write_bundle(self.root, [{"case": "south-atlantic"}])
        path = self.root / "bundle.yaml"
        path.write_text(path.read_text(encoding="utf-8").replace(BUNDLE_SCHEMA_VERSION, "geoarg/bundle/0.0"), encoding="utf-8")
        rows = migrate(self.root)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["changed"])
        self.assertIn(BUNDLE_SCHEMA_VERSION, path.read_text(encoding="utf-8"))


class BundleCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        _copy("south-atlantic", self.root)

    def test_bundle_and_migrate_commands(self) -> None:
        _write_bundle(self.root, [{"case": "south-atlantic"}])
        self.assertEqual(cli.main(["bundle", str(self.root), "--json"]), 0)
        out = self.root / "bundle.md"
        self.assertEqual(cli.main(["bundle", str(self.root), "--out", str(out), "--lang", "zh"]), 0)
        self.assertIn("论文结论", out.read_text(encoding="utf-8"))
        fresh = _copy("paper-demo", self.root)
        (fresh / "test.yaml").write_text(
            (fresh / "test.yaml").read_text(encoding="utf-8").replace(f"schema_version: {SCHEMA_VERSION}", "schema_version: geoarg/0.4"),
            encoding="utf-8",
        )
        self.assertEqual(cli.main(["migrate", str(fresh)]), 0)
        self.assertIn(SCHEMA_VERSION, (fresh / "test.yaml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
