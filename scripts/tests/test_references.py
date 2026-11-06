from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import yaml

from geoarg import cli, references

REPO = Path(__file__).resolve().parents[2]
CASE = REPO / "examples" / "paper-demo"


def _copy_case(dest: Path) -> Path:
    shutil.copytree(CASE, dest)
    return dest


def _edit_evidence(case: Path, mutate) -> None:
    path = case / "evidence.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for record in data["records"]:
        mutate(record)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class IdentifierTests(unittest.TestCase):
    def test_extracts_doi_pmcid_pmid_and_arxiv(self) -> None:
        citation = "Surovell et al. (2009), PNAS, PMC2775309; PMID: 19164576; arXiv: 2101.12345; doi:10.1073/pnas.0706977104."
        found = references.extract_identifiers(citation)
        kinds = {item["kind"]: item["value"] for item in found}
        self.assertEqual(kinds["doi"], "10.1073/pnas.0706977104")
        self.assertEqual(kinds["pmcid"], "PMC2775309")
        self.assertEqual(kinds["pmid"], "19164576")
        self.assertEqual(kinds["arxiv"], "2101.12345")

    def test_citation_without_identifier(self) -> None:
        self.assertEqual(references.extract_identifiers("Synthetic et al. (2026), paper-demo fixture"), [])


class SourceGapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.case = _copy_case(Path(self.tmp.name) / "case")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_paper_demo_cites_with_quotes_and_source(self) -> None:
        payload = references.source_gaps(self.case)
        self.assertEqual(payload["summary"]["citations"], 3)
        self.assertEqual(payload["summary"]["with_quote"], 3)
        self.assertEqual(payload["summary"]["without_quote"], 0)
        self.assertTrue(payload["source_present"])

    def test_require_quote_flags_citation_without_quote(self) -> None:
        _edit_evidence(self.case, lambda record: record.pop("source_locator", None))
        payload = references.source_gaps(self.case)
        problems = references.source_gap_problems(payload, require_quote=True)
        self.assertEqual(len(problems), 3)
        self.assertIn("has no quoted passage", problems[0])

    def test_require_source_flags_absent_ground_ledger(self) -> None:
        shutil.rmtree(self.case / ".geoarg")
        payload = references.source_gaps(self.case)
        problems = references.source_gap_problems(payload, require_source=True)
        self.assertEqual(len(problems), 1)
        self.assertIn("no grounding ledger", problems[0])

    def test_sources_cli_reports_and_fails_on_requirement(self) -> None:
        code, out, _ = _run(["sources", str(self.case)])
        self.assertEqual(code, 0)
        self.assertIn("Citation checks", out)
        _edit_evidence(self.case, lambda record: record.pop("source_locator", None))
        code, out, _ = _run(["sources", str(self.case), "--require-quote"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)


class VerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.case = _copy_case(Path(self.tmp.name) / "case")
        _edit_evidence(
            self.case,
            lambda record: record.__setitem__(
                "source", {"citation": "Synthetic et al. (2026), doi:10.1234/geoarg.test"}
            ),
        )
        self.remote = {
            "provider": "crossref",
            "title": "A synthetic test paper",
            "year": 2026,
            "first_author": "Synthetic",
            "authors": ["Synthetic", "Tester"],
            "container": "Journal of Tests",
            "retracted": False,
            "url": "https://example.invalid/10.1234/geoarg.test",
        }

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_verified_lookup_writes_snapshot(self) -> None:
        with mock.patch("geoarg.references._lookup", return_value=dict(self.remote)):
            payload = references.verify_references(self.case, pace=0)
        self.assertEqual(payload["summary"]["verified"], 3)
        snapshot = self.case / ".geoarg" / "references.json"
        self.assertTrue(snapshot.is_file())
        stored = json.loads(snapshot.read_text(encoding="utf-8"))
        self.assertEqual(stored["summary"]["verified"], 3)

    def test_mismatch_and_retracted(self) -> None:
        wrong_year = dict(self.remote, year=1999)
        with mock.patch("geoarg.references._lookup", return_value=wrong_year):
            payload = references.verify_references(self.case, pace=0)
        self.assertEqual(payload["summary"]["mismatch"], 3)

        retracted = dict(self.remote, retracted=True)
        with mock.patch("geoarg.references._lookup", return_value=retracted):
            payload = references.verify_references(self.case, refresh=True, pace=0)
        self.assertEqual(payload["summary"]["retracted"], 3)

    def test_not_found_and_unreachable(self) -> None:
        error = urllib.error.HTTPError("https://example.invalid", 404, "not found", {}, None)

        def missing(identifier, provider, timeout):
            raise error

        with mock.patch("geoarg.references._lookup", side_effect=missing):
            payload = references.verify_references(self.case, providers=("crossref",), pace=0)
        self.assertEqual(payload["summary"]["not-found"], 3)

        def unreachable(identifier, provider, timeout):
            raise urllib.error.URLError("network down")

        with mock.patch("geoarg.references._lookup", side_effect=unreachable):
            payload = references.verify_references(self.case, providers=("crossref",), refresh=True, pace=0)
        self.assertEqual(payload["summary"]["unverifiable"], 3)
        self.assertTrue(references.reference_requirements_met(payload))

    def test_offline_uses_cache_and_cli_paths(self) -> None:
        with mock.patch("geoarg.references._lookup", return_value=dict(self.remote)):
            payload = references.verify_references(self.case, pace=0)
        self.assertTrue(payload["summary"]["verified"])

        def must_not_call(*args, **kwargs):
            raise AssertionError("offline mode contacted a provider")

        with mock.patch("geoarg.references._lookup", side_effect=must_not_call):
            cached = references.verify_references(self.case, offline=True)
        self.assertEqual(cached["summary"]["verified"], 3)

        code, out, _ = _run(["references", str(self.case), "--offline"])
        self.assertEqual(code, 0)
        self.assertIn("Identifier verification", out)
        code, _, _ = _run(["references", str(self.case), "--offline", "--require-verified"])
        self.assertEqual(code, 0)

    def test_offline_without_snapshot_errors(self) -> None:
        code, _, err = _run(["references", str(self.case), "--offline"])
        self.assertEqual(code, 2)
        self.assertIn("no references snapshot", err)

    def test_require_verified_fails_on_unverified(self) -> None:
        def unreachable(identifier, provider, timeout):
            raise urllib.error.URLError("network down")

        with mock.patch("geoarg.references._lookup", side_effect=unreachable):
            code, out, _ = _run(["references", str(self.case), "--require-verified"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)


class RenderTests(unittest.TestCase):
    def test_render_both_languages(self) -> None:
        payload = {
            "schema_version": references.REFERENCE_SCHEMA_VERSION,
            "created_at": "2026-01-01T00:00:00+00:00",
            "summary": {"verified": 1, "mismatch": 0, "not-found": 0, "retracted": 0, "unverifiable": 0, "no-identifier": 0},
            "rows": [
                {
                    "evidence_id": "ev.x",
                    "citation": "Synthetic et al. (2026)",
                    "identifiers": [{"kind": "doi", "value": "10.1/x"}],
                    "status": "verified",
                    "provider": "crossref",
                    "remote": {"title": "A paper"},
                    "notes": [],
                }
            ],
        }
        self.assertIn("Citation checks", references.render_sources({"summary": {}, "rows": []}, "en"))
        self.assertIn("引用核验", references.render_sources({"summary": {}, "rows": []}, "zh"))
        self.assertIn("verified", references.render_references(payload, "en"))
        self.assertIn("已核验", references.render_references(payload, "zh"))


if __name__ == "__main__":
    unittest.main()
