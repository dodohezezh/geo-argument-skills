"""Tests for the trust layer: ledger, anchor, attestation, schemas, versions."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from geoarg import __version__, schemas  # noqa: E402
from geoarg.attest import attest, read_attestation  # noqa: E402
from geoarg.audit import (  # noqa: E402
    anchor,
    anchor_problems,
    commit,
    external_anchor_problems,
    ledger_entries,
    ledger_report,
    record_sha256,
    verify,
)
from geoarg.cli import main  # noqa: E402
from geoarg.contract import ContractError, load_case  # noqa: E402
from geoarg.report import render  # noqa: E402
from geoarg.safeio import LockError, atomic_write_text, case_lock  # noqa: E402

CASE = REPO / "examples" / "paper-demo"


def _case(tmp: Path) -> Path:
    dst = tmp / "case"
    shutil.copytree(CASE, dst)
    geo = dst / ".geoarg"
    geo.mkdir(exist_ok=True)
    shutil.rmtree(geo / "registry", ignore_errors=True)
    for name in ("ledger.jsonl", "anchor.json", "attestation.json"):
        path = geo / name
        if path.exists():
            path.unlink()
    return dst


def _quiet(argv: list[str]) -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return main(argv)


class LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-trust-"))
        self.case = _case(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_commit_appends_a_ledger_entry(self) -> None:
        record, path = commit(self.case)
        self.assertTrue(path.is_file())
        self.assertEqual(record["schema_version"], "geoarg/registry/0.6")
        entries, problems = ledger_entries(self.case)
        self.assertEqual(problems, [])
        self.assertEqual([entry["kind"] for entry in entries], ["commit"])
        self.assertEqual(entries[0]["record_sha256"], record_sha256(record))
        self.assertEqual(entries[0]["verdict"], record["verdict"])
        ok, problems, _ = verify(self.case)
        self.assertTrue(ok, problems)

    def test_ledger_report_summarises_entries(self) -> None:
        commit(self.case)
        report = ledger_report(self.case)
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["entries"]), 1)
        self.assertEqual(report["entries"][0]["kind"], "commit")
        self.assertEqual(report["head"], report["entries"][0]["sha256"])

    def test_unreadable_ledger_line_is_reported(self) -> None:
        commit(self.case)
        ledger = self.case / ".geoarg" / "ledger.jsonl"
        ledger.write_text(ledger.read_text(encoding="utf-8") + "not-json\n", encoding="utf-8")
        _, problems = ledger_entries(self.case)
        self.assertTrue(any("ledger line" in problem for problem in problems))
        ok, problems, _ = verify(self.case)
        self.assertFalse(ok)

    def test_edited_registry_record_is_not_the_committed_record(self) -> None:
        commit(self.case)
        record_path = next((self.case / ".geoarg" / "registry").glob("*.json"))
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["verdict"] = "SUPPORTED"
        atomic_write_text(record_path, json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        ok, problems, _ = verify(self.case)
        self.assertFalse(ok)
        self.assertTrue(any("ledger has no entry for this record" in problem for problem in problems))


class AnchorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-anchor-"))
        self.case = _case(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_anchor_round_trip(self) -> None:
        record, _ = commit(self.case)
        payload, path = anchor(self.case)
        self.assertTrue(path.is_file())
        self.assertEqual(payload["record_sha256"], record_sha256(record))
        self.assertEqual(payload["ledger_count"], 1)  # checkpointed before its own ledger entry
        self.assertEqual(len(payload["anchor_sha256"]), 64)
        entries, problems = ledger_entries(self.case)
        self.assertEqual(problems, [])
        self.assertEqual([entry["kind"] for entry in entries], ["commit", "anchor"])
        ok, problems, _ = verify(self.case)
        self.assertTrue(ok, problems)

    def test_edited_anchor_is_reported(self) -> None:
        record, _ = commit(self.case)
        anchor(self.case)
        path = self.case / ".geoarg" / "anchor.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["note"] = "rewritten later"
        atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        problems = anchor_problems(self.case, record)
        self.assertTrue(any("anchor file was edited" in problem for problem in problems))
        ok, problems, _ = verify(self.case)
        self.assertFalse(ok)

    def test_unreadable_anchor_is_reported(self) -> None:
        from geoarg import audit

        record, _ = commit(self.case)
        anchor(self.case)
        path = self.case / ".geoarg" / "anchor.json"
        path.write_text("\ufeffnot json", encoding="utf-8")
        problems = audit.anchor_problems(self.case, record)
        self.assertTrue(any("anchor file is unreadable" in problem for problem in problems), problems)
        ok, problems, _ = verify(self.case)
        self.assertFalse(ok)
        self.assertTrue(any("anchor file is unreadable" in problem for problem in problems))

    def test_external_anchor_is_checked(self) -> None:
        record, _ = commit(self.case)
        anchor(self.case)
        external = self.tmp / "external-anchor.json"
        shutil.copy(self.case / ".geoarg" / "anchor.json", external)
        self.assertEqual(external_anchor_problems(self.case, record, external), [])
        payload = json.loads(external.read_text(encoding="utf-8"))
        payload["note"] = "edited outside"
        atomic_write_text(external, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        problems = external_anchor_problems(self.case, record, external)
        self.assertTrue(any("digest does not match" in problem for problem in problems), problems)
        missing = self.tmp / "missing-anchor.json"
        problems = external_anchor_problems(self.case, record, missing)
        self.assertTrue(any("missing" in problem for problem in problems))

    def test_verify_cli_checks_external_anchor(self) -> None:
        commit(self.case)
        anchor(self.case)
        external = self.tmp / "external-anchor.json"
        shutil.copy(self.case / ".geoarg" / "anchor.json", external)
        self.assertEqual(_quiet(["verify", str(self.case), "--anchor", str(external)]), 0)
        payload = json.loads(external.read_text(encoding="utf-8"))
        payload["ledger_count"] = 99
        atomic_write_text(external, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        self.assertEqual(_quiet(["verify", str(self.case), "--anchor", str(external)]), 1)

    def test_anchor_requires_a_commit(self) -> None:
        with self.assertRaises(ContractError):
            anchor(self.case)


class AttestationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-attest-"))
        self.case = _case(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_attest_binds_report_and_judgment(self) -> None:
        commit(self.case)
        report = self.case / "report.md"
        report.write_text(render(load_case(self.case), "en"), encoding="utf-8")
        judgment = self.case / "judgment.md"
        judgment.write_text("This argument is not yet tested.", encoding="utf-8")
        payload, path = attest(self.case, judgment_files=[str(judgment)])
        self.assertTrue(path.is_file())
        self.assertEqual(payload["record_sha256"], record_sha256(json.loads(
            next((self.case / ".geoarg" / "registry").glob("*.json")).read_text(encoding="utf-8")
        )))
        stored = read_attestation(self.case)
        self.assertEqual(stored["deliverables"][0]["path"], "report.md")
        self.assertEqual(stored["judgment"][0]["path"], "judgment.md")
        ok, problems, _ = verify(self.case)
        self.assertTrue(ok, problems)

    def test_edited_deliverable_is_reported(self) -> None:
        commit(self.case)
        report = self.case / "report.md"
        original = render(load_case(self.case), "en")
        report.write_text(original, encoding="utf-8")
        attest(self.case)
        report.write_text(original + "\nlate addition\n", encoding="utf-8")
        ok, problems, _ = verify(self.case)
        self.assertFalse(ok)
        self.assertTrue(any("deliverable changed since attestation: report.md" in problem for problem in problems))
        report.write_text(original, encoding="utf-8")
        ok, problems, _ = verify(self.case)
        self.assertTrue(ok, problems)

    def test_unreadable_attestation_is_reported(self) -> None:
        commit(self.case)
        report = self.case / "report.md"
        report.write_text("attested body", encoding="utf-8")
        attest(self.case)
        (self.case / ".geoarg" / "attestation.json").write_text("\ufeffnot json", encoding="utf-8")
        ok, problems, _ = verify(self.case)
        self.assertFalse(ok)
        self.assertTrue(any("attestation file is unreadable" in problem for problem in problems), problems)

    def test_attestation_requires_a_commit(self) -> None:
        report = self.case / "report.md"
        report.write_text("stale", encoding="utf-8")
        with self.assertRaises(ContractError):
            attest(self.case)


class SafeIOTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-io-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_atomic_write_replaces_without_leftovers(self) -> None:
        path = self.tmp / "value.txt"
        atomic_write_text(path, "one")
        atomic_write_text(path, "two")
        self.assertEqual(path.read_text(encoding="utf-8"), "two")
        names = sorted(child.name for child in self.tmp.iterdir())
        self.assertEqual(names, ["value.txt"])

    def test_case_lock_is_exclusive(self) -> None:
        with case_lock(self.tmp):
            with self.assertRaises(LockError):
                with case_lock(self.tmp, timeout=0.2):
                    pass
        with case_lock(self.tmp, timeout=0.2):
            pass


class SchemaTests(unittest.TestCase):
    def test_all_schemas_are_packaged(self) -> None:
        names = schemas.list_schemas()
        expected = {
            "argument",
            "evidence",
            "test",
            "bundle",
            "workspace",
            "attestation",
            "anchor",
            "domain",
        }
        self.assertEqual(set(names), expected)

    def test_example_argument_matches_its_schema(self) -> None:
        argument = yaml.safe_load((CASE / "argument.yaml").read_text(encoding="utf-8"))
        try:
            problems = schemas.validate_instance(argument, "argument")
        except schemas.SchemaError as exc:
            if "jsonschema is not installed" in str(exc):
                self.skipTest("jsonschema is not installed")
            raise
        self.assertEqual(problems, [])
        try:
            problems = schemas.validate_instance({"schema_version": "geoarg/0.6"}, "argument")
        except schemas.SchemaError as exc:
            if "jsonschema is not installed" in str(exc):
                self.skipTest("jsonschema is not installed")
            raise
        self.assertTrue(problems)

    def test_examples_validate_against_shipped_schemas(self) -> None:
        examples = sorted(path.parent for path in (REPO / "examples").rglob("argument.yaml"))
        self.assertTrue(examples, "no example case found")
        try:
            schemas.list_schemas()
            problems: list[str] = []
            for case in examples:
                for document, name in (
                    ("argument.yaml", "argument"),
                    ("evidence.yaml", "evidence"),
                    ("test.yaml", "test"),
                ):
                    payload = yaml.safe_load((case / document).read_text(encoding="utf-8"))
                    problems += [f"{case.name}/{document}: {item}" for item in schemas.validate_instance(payload, name)]
        except schemas.SchemaError as exc:
            if "jsonschema is not installed" in str(exc):
                self.skipTest("jsonschema is not installed")
            raise
        self.assertEqual(problems, [])

    def test_cli_schema_validate(self) -> None:
        self.assertEqual(_quiet(["schema", "argument", "--validate", str(CASE / "argument.yaml")]), 0)
        broken = Path(tempfile.mkdtemp(prefix="geoarg-schema-"))
        try:
            bad = broken / "argument.yaml"
            bad.write_text("schema_version: geoarg/0.6\n", encoding="utf-8")
            self.assertEqual(_quiet(["schema", "argument", "--validate", str(bad)]), 1)
            self.assertEqual(_quiet(["schema", "nope", "--validate", str(bad)]), 2)
        finally:
            shutil.rmtree(broken, ignore_errors=True)


class VersionTests(unittest.TestCase):
    def test_version_agrees_across_files(self) -> None:
        pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'version = "{__version__}"', pyproject)
        plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["version"], __version__)
        from geoarg.install import REQUIRED_ENGINE

        self.assertEqual(REQUIRED_ENGINE, __version__)

    def test_cli_trust_commands_smoke(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="geoarg-cli-trust-"))
        try:
            case = _case(tmp)
            commit(case)
            self.assertEqual(_quiet(["ledger", str(case), "--json"]), 0)
            self.assertEqual(_quiet(["anchor", str(case), "--json"]), 0)
            self.assertEqual(_quiet(["schema", "--list", "--json"]), 0)
            self.assertEqual(_quiet(["attest", str(case), "--json"]), 2)  # no deliverables yet
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
