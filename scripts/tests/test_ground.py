"""Tests for the quote check (grounding gate)."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from geoarg.audit import commit, verify  # noqa: E402
from geoarg.cli import main  # noqa: E402
from geoarg.contract import load_case, validate  # noqa: E402
from geoarg.ground import (  # noqa: E402
    GROUND_SCHEMA_VERSION,
    ground_records,
    load_ledger,
    normalize,
    validate_grounding,
    write_ledger,
)
from pdf_fixture import build_pdf  # noqa: E402

CASE = REPO / "examples" / "south-atlantic"

QUOTES = [
    "The basal unconformity is dated at 12.3 Ma by zircon U-Pb.",
    "The unconformity is traceable across the basin for 180 km.",
    "Bioturbated silts above the surface indicate a marine flooding event.",
]
PAGES = [[QUOTES[0]], [QUOTES[1]], [QUOTES[2]]]


def _write_yaml(path: Path, doc: object) -> None:
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")


def make_case(tmp: Path) -> Path:
    dst = tmp / "case"
    shutil.copytree(CASE, dst)
    evidence = yaml.safe_load((dst / "evidence.yaml").read_text(encoding="utf-8"))
    for index, record in enumerate(evidence["records"]):
        record["verification"] = {"level": "transcription"}
        record["status"] = "accepted"
        record["source_locator"] = {"page": index + 1, "quote": QUOTES[index]}
    _write_yaml(dst / "evidence.yaml", evidence)
    return dst


def write_pdf(tmp: Path, pages: list[list[str]] | None = None, name: str = "paper.pdf") -> Path:
    path = tmp / name
    path.write_bytes(build_pdf(pages if pages is not None else PAGES))
    return path


def edit_evidence(case: Path, mutate) -> None:
    evidence = yaml.safe_load((case / "evidence.yaml").read_text(encoding="utf-8"))
    mutate(evidence["records"])
    _write_yaml(case / "evidence.yaml", evidence)


class NormalizeTests(unittest.TestCase):
    def test_joins_hyphenated_line_break(self) -> None:
        self.assertEqual(normalize("trans-\nform"), "transform")

    def test_collapses_whitespace_and_case(self) -> None:
        self.assertEqual(normalize("  The  BASAL\n unconformity "), "the basal unconformity")


class GroundingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-ground-"))
        self.case = make_case(self.tmp)
        self.pdf = write_pdf(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_all_quotes_grounded(self) -> None:
        ledger = ground_records(load_case(self.case), self.pdf)
        self.assertEqual(ledger["schema_version"], GROUND_SCHEMA_VERSION)
        self.assertEqual(ledger["drafted"], 3)
        self.assertEqual(ledger["grounded"], 3)
        self.assertEqual(ledger["acceptance_rate"], 1.0)
        for record in ledger["records"].values():
            self.assertEqual(record["status"], "grounded")

    def test_wrong_page_is_page_mismatch_with_strict_exit(self) -> None:
        edit_evidence(self.case, lambda records: records[1].update(source_locator={"page": 3, "quote": QUOTES[1]}))
        ledger = ground_records(load_case(self.case), self.pdf)
        record = ledger["records"]["ev.fz"] if "ev.fz" in ledger["records"] else list(ledger["records"].values())[1]
        self.assertEqual(record["status"], "page-mismatch")
        self.assertEqual(record["found_page"], 2)
        self.assertEqual(main(["ground", str(self.case), "--pdf", str(self.pdf), "--json"]), 1)
        # Fail-closed by default: a declared quote that did not ground stops the run.
        self.assertEqual(main(["ground", str(self.case), "--pdf", str(self.pdf), "--json"]), 1)
        self.assertEqual(
            main(["ground", str(self.case), "--pdf", str(self.pdf), "--allow-partial", "--json"]), 0
        )

    def test_fabricated_quote_is_not_found(self) -> None:
        edit_evidence(
            self.case,
            lambda records: records[0].update(source_locator={"page": 1, "quote": "The surface is 400 Ma old."}),
        )
        ledger = ground_records(load_case(self.case), self.pdf)
        self.assertEqual(list(ledger["records"].values())[0]["status"], "not-found")
        self.assertEqual(ledger["acceptance_rate"], 0.667)
        self.assertEqual(main(["ground", str(self.case), "--pdf", str(self.pdf), "--json"]), 1)

    def test_pdf_without_text_layer_is_not_groundable(self) -> None:
        empty_pdf = write_pdf(self.tmp, pages=[[""], [""], [""]], name="empty.pdf")
        ledger = ground_records(load_case(self.case), empty_pdf)
        self.assertFalse(ledger["extracted"]["text_layer"])
        self.assertTrue(all(record["status"] == "not-groundable" for record in ledger["records"].values()))
        self.assertEqual(ledger["grounded"], 0)

    def test_plain_text_docx_and_html_sources_ground(self) -> None:
        edit_evidence(
            self.case,
            lambda records: [
                record.update(source_locator={"page": 1, "quote": quote})
                for record, quote in zip(records, QUOTES)
            ],
        )
        txt = self.tmp / "paper.txt"
        txt.write_text("\n".join(QUOTES), encoding="utf-8")
        ledger = ground_records(load_case(self.case), txt)
        self.assertEqual(ledger["pdf"]["format"], "txt")
        self.assertEqual(ledger["grounded"], 3)
        self.assertEqual(main(["ground", str(self.case), "--source", str(txt), "--json"]), 0)

        import docx

        document = docx.Document()
        for quote in QUOTES:
            document.add_paragraph(quote)
        docx_path = self.tmp / "paper.docx"
        document.save(docx_path)
        ledger = ground_records(load_case(self.case), docx_path)
        self.assertEqual(ledger["grounded"], 3)

        html = self.tmp / "paper.html"
        html.write_text("<p>" + "</p><p>".join(QUOTES) + "</p>", encoding="utf-8")
        ledger = ground_records(load_case(self.case), html)
        self.assertEqual(ledger["grounded"], 3)

    def test_record_without_locator_is_listed_not_drafted(self) -> None:
        edit_evidence(
            self.case,
            lambda records: records[2].update(status="disputed", verification={"level": "transcription"}, source_locator=None),
        )
        ledger = ground_records(load_case(self.case), self.pdf)
        self.assertEqual(list(ledger["records"].values())[2]["status"], "no-locator")
        self.assertEqual(ledger["drafted"], 2)

    def test_stale_quote_after_contract_edit_is_reported(self) -> None:
        ledger = ground_records(load_case(self.case), self.pdf)
        write_ledger(load_case(self.case), ledger)
        edit_evidence(
            self.case,
            lambda records: records[0]["source_locator"].update(quote=QUOTES[0] + " revised"),
        )
        problems, _ = validate_grounding(load_case(self.case), load_ledger(self.case))
        self.assertTrue(any("stale" in problem for problem in problems), problems)
        self.assertEqual(main(["check", str(self.case)]), 1)

    def test_accepted_transcription_must_be_grounded(self) -> None:
        ledger = ground_records(load_case(self.case), self.pdf)
        ledger["records"] = {key: dict(value) for key, value in ledger["records"].items()}
        first_key = list(ledger["records"])[0]
        ledger["records"][first_key]["status"] = "not-found"
        ledger["records"][first_key]["grounded"] = False
        write_ledger(load_case(self.case), ledger)
        problems, _ = validate_grounding(load_case(self.case), load_ledger(self.case))
        self.assertTrue(any("not grounded" in problem for problem in problems), problems)
        self.assertEqual(main(["check", str(self.case)]), 1)

    def test_commit_stores_grounding_digest_and_verify_detects_change(self) -> None:
        ledger = ground_records(load_case(self.case), self.pdf)
        write_ledger(load_case(self.case), ledger)
        registry = self.tmp / "registry"
        record, _ = commit(self.case, registry)
        self.assertIsNotNone(record["grounding"])
        self.assertEqual(record["grounding"]["acceptance_rate"], 1.0)
        ok, problems, _ = verify(self.case, registry)
        self.assertTrue(ok, problems)

        other_pdf = write_pdf(self.tmp, name="other.pdf")
        write_ledger(load_case(self.case), ground_records(load_case(self.case), other_pdf))
        ok, problems, _ = verify(self.case, registry)
        self.assertFalse(ok)
        self.assertTrue(any("grounding ledger changed" in problem for problem in problems), problems)

    def test_ground_refuses_invalid_contract(self) -> None:
        argument = yaml.safe_load((self.case / "argument.yaml").read_text(encoding="utf-8"))
        argument["premises"][0].pop("statement")
        _write_yaml(self.case / "argument.yaml", argument)
        self.assertEqual(main(["ground", str(self.case), "--pdf", str(self.pdf)]), 2)

    def test_example_south_atlantic_is_still_clean(self) -> None:
        self.assertEqual(validate(load_case(CASE)), [])
        self.assertIsNone(load_ledger(CASE))
        problems, _ = validate_grounding(load_case(CASE), None)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
