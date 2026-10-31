"""Tests for the GeoArg contract engine."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from geoarg.audit import commit, verify  # noqa: E402
from geoarg.contract import load_case, validate  # noqa: E402
from geoarg.hitting import decisive_events  # noqa: E402
from geoarg.independence import effective_n, report as independence_report  # noqa: E402
from geoarg.judge import judge  # noqa: E402

CASE = REPO / "examples" / "south-atlantic"


class ContractTests(unittest.TestCase):
    def test_example_case_is_clean(self) -> None:
        self.assertEqual(validate(load_case(CASE)), [])

    def test_missing_cp_test_is_reported(self) -> None:
        case = load_case(CASE)
        case.argument["inference"]["cp"][0]["test_ref"] = "T404"
        problems = validate(case)
        self.assertTrue(any("test_ref" in problem for problem in problems))

    def test_floating_premise_is_reported(self) -> None:
        case = load_case(CASE)
        case.argument["premises"][0]["evidence_refs"] = []
        problems = validate(case)
        self.assertTrue(any("evidence_refs" in problem for problem in problems))


class JudgeTests(unittest.TestCase):
    def test_example_is_untested(self) -> None:
        result = judge(load_case(CASE))
        self.assertEqual(result["verdict"], "UNTESTED")
        self.assertTrue(any("blocking gap" in flag for flag in result["flags"]))

    def test_fatal_defeater_defeats(self) -> None:
        result = judge(load_case(CASE), {("defeater", "D1"): "established"})
        self.assertEqual(result["verdict"], "DEFEATED")

    def test_failed_cp_defeats(self) -> None:
        result = judge(load_case(CASE), {("cp", "CP1"): "fails"})
        self.assertEqual(result["verdict"], "DEFEATED")

    def test_degrading_defeater_suspends(self) -> None:
        result = judge(load_case(CASE), {("defeater", "D2"): "established"})
        self.assertEqual(result["verdict"], "SUSPENDED")

    def test_supported_flags_low_power_tests(self) -> None:
        case = load_case(CASE)
        overrides: dict[tuple[str, str], str] = {}
        for cp in case.argument["inference"]["cp"]:
            overrides[("cp", cp["id"])] = "holds"
        for defeater in case.argument["inference"]["defeaters"]:
            overrides[("defeater", defeater["id"])] = "refuted"
        for entailment in case.argument["entailments"]:
            overrides[("entailment", entailment["id"])] = "passed"
        for test in case.tests["records"]:
            test["status"] = "passed"
        result = judge(case, overrides)
        self.assertEqual(result["verdict"], "SUPPORTED")
        self.assertTrue(any("discriminating power" in flag for flag in result["flags"]))


class IndependenceTests(unittest.TestCase):
    def test_effective_n_penalises_shared_calibration(self) -> None:
        report = independence_report(load_case(CASE))
        self.assertEqual(report["n_records"], 3)
        self.assertEqual(report["n_eff"], 1.2)
        self.assertEqual(report["mean_rho"], 0.75)
        self.assertTrue(report["warnings"])
        self.assertEqual(report["declared_calibration_not_attached"], ["plate-model-2024"])

    def test_effective_n_handles_empty_and_single(self) -> None:
        self.assertEqual(effective_n([]), (0.0, 0.0))
        self.assertEqual(effective_n([{"id": "x"}]), (1.0, 0.0))


class HittingTests(unittest.TestCase):
    def test_decisive_events_are_ranked_by_power(self) -> None:
        payload = decisive_events(load_case(CASE))
        self.assertEqual(payload["base_verdict"], "UNTESTED")
        self.assertEqual(len(payload["events"]), 13)
        outcomes = {event["resulting_verdict"] for event in payload["events"]}
        self.assertEqual(outcomes, {"DEFEATED", "SUSPENDED"})
        self.assertEqual(payload["events"][0]["power"], "high")


class AuditTests(unittest.TestCase):
    def test_commit_then_verify_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            import shutil

            shutil.copytree(CASE, case_dir)
            record, path = commit(case_dir)
            self.assertTrue(path.is_file())
            ok, problems, stored = verify(case_dir)
            self.assertTrue(ok, problems)
            self.assertEqual(stored["verdict"], record["verdict"])

    def test_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            import shutil

            shutil.copytree(CASE, case_dir)
            commit(case_dir)
            with (case_dir / "argument.yaml").open("a", encoding="utf-8") as fh:
                fh.write("\n# tampered\n")
            ok, problems, _ = verify(case_dir)
            self.assertFalse(ok)
            self.assertTrue(any("input changed" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()
