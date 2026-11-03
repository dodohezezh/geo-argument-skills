"""Tests for result binding: pass rules, computed statuses, and the registry."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from geoarg import results
from geoarg.audit import commit, record_sha256, verify
from geoarg.contract import load_case
from geoarg.judge import judge

REPO = Path(__file__).resolve().parents[2]
CASE = REPO / "examples" / "south-atlantic"


def _load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _dump(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _copy_case(root: Path) -> Path:
    target = root / "case"
    shutil.copytree(CASE, target)
    return target


def _set_result(case: Path, test_id: str, result: dict, rule: dict) -> None:
    tests = _load(case / "test.yaml")
    record = next(item for item in tests["records"] if item["id"] == test_id)
    record["result"] = result
    record["pass_rule"] = rule
    record.pop("status", None)
    _dump(case / "test.yaml", tests)


class PassRuleTest(unittest.TestCase):
    def _test(self, result: dict, rule: dict) -> dict:
        return {"id": "T1", "result": result, "pass_rule": rule}

    def test_valid_rule_shapes(self) -> None:
        cases = [
            ({"value": 2.0}, {"op": "ge", "value": 1.0}),
            ({"value": 0.04}, {"op": "le", "value": 0.05}),
            ({"value": 2.0}, {"op": "between", "low": 1.9, "high": 2.1}),
            ({"value": 2.0, "uncertainty": {"kind": "ci95", "low": 1.8, "high": 2.2}}, {"op": "within_ci", "target": 2.0}),
            ({"value": 20.0}, {"op": "ratio", "target": 20.0, "tolerance": 0.1}),
        ]
        for result, rule in cases:
            with self.subTest(rule=rule["op"]):
                self.assertEqual(results.validate_result_block(self._test(result, rule)), [])

    def test_structural_errors(self) -> None:
        bad = [
            ({"value": 2.0}, {"op": "ge"}),
            ({"value": 2.0}, {"op": "between", "low": 3.0, "high": 1.0}),
            ({"value": 2.0}, {"op": "within_ci", "target": 2.0}),
            ({"value": 2.0}, {"op": "ratio", "target": 0, "tolerance": 0.1}),
            ({"value": 2.0}, {"op": "ratio", "target": 2.0, "tolerance": -1}),
            ({"value": 2.0}, {"op": "nope"}),
            ({"value": "high"}, {"op": "ge", "value": 1.0}),
        ]
        for result, rule in bad:
            with self.subTest(rule=rule):
                self.assertTrue(results.validate_result_block(self._test(result, rule)))
        self.assertTrue(results.validate_result_block({"id": "T1", "pass_rule": {"op": "ge", "value": 1.0}}))

    def test_compute_status(self) -> None:
        passed = results.compute_status(self._test({"value": 1.6}, {"op": "ge", "value": 1.5}))
        self.assertEqual(passed["status"], "passed")
        failed = results.compute_status(self._test({"value": 1.4}, {"op": "ge", "value": 1.5}))
        self.assertEqual(failed["status"], "failed")
        bounded = results.compute_status(self._test({"value": 2.5}, {"op": "between", "low": 1.0, "high": 2.0}))
        self.assertEqual(bounded["status"], "failed")
        ratio = results.compute_status(self._test({"value": 21.0}, {"op": "ratio", "target": 20.0, "tolerance": 0.1}))
        self.assertEqual(ratio["status"], "passed")
        self.assertIsNone(results.compute_status({"id": "T1"}))

    def test_effective_status_prefers_computed(self) -> None:
        test = {"id": "T1", "status": "passed", "result": {"value": 1.0}, "pass_rule": {"op": "ge", "value": 2.0}}
        effective = results.effective_status(test)
        self.assertEqual((effective["status"], effective["source"], effective["declared"]), ("failed", "computed", "passed"))
        declared = results.effective_status({"id": "T2", "status": "running"})
        self.assertEqual((declared["status"], declared["source"]), ("running", "declared"))
        summary = results.test_status_summary([test, {"id": "T2", "status": "running"}])
        self.assertEqual(summary["T1"]["source"], "computed")
        self.assertEqual(summary["T2"]["source"], "declared")


class ResultJudgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.case = _copy_case(Path(self.temp.name))

    def _set_cp(self, cp_id: str, state: str) -> None:
        argument = _load(self.case / "argument.yaml")
        condition = next(item for item in argument["inference"]["cp"] if item["id"] == cp_id)
        condition["state"] = state
        _dump(self.case / "argument.yaml", argument)

    def test_computed_failure_leaves_satisfied_state_unbacked(self) -> None:
        self._set_cp("CP1", "holds")
        _set_result(self.case, "T4", {"value": 1.0}, {"op": "ge", "value": 2.0})
        result = judge(load_case(self.case))
        self.assertEqual(result["verdict"], "UNDETERMINED")
        self.assertTrue(any("CP1" in item for item in result["unbacked"]))
        self.assertEqual(result["test_status"]["T4"]["status"], "failed")

    def test_computed_pass_backs_a_satisfied_state(self) -> None:
        self._set_cp("CP1", "holds")
        _set_result(self.case, "T4", {"value": 3.0}, {"op": "ge", "value": 2.0})
        result = judge(load_case(self.case))
        self.assertFalse(any("CP1" in item for item in result["unbacked"]))
        self.assertEqual(result["test_status"]["T4"]["status"], "passed")

    def test_declared_versus_computed_mismatch_is_flagged(self) -> None:
        tests = _load(self.case / "test.yaml")
        record = next(item for item in tests["records"] if item["id"] == "T1")
        record["result"] = {"value": 3.0}
        record["pass_rule"] = {"op": "ge", "value": 2.0}
        _dump(self.case / "test.yaml", tests)
        result = judge(load_case(self.case))
        self.assertTrue(any("declares planned" in flag for flag in result["flags"]))
        gating = {item["id"]: item for item in result["gating_tests"]}
        self.assertEqual(gating["T1"]["source"], "computed")

    def test_result_without_rule_is_flagged(self) -> None:
        tests = _load(self.case / "test.yaml")
        record = next(item for item in tests["records"] if item["id"] == "T1")
        record["result"] = {"value": 3.0}
        _dump(self.case / "test.yaml", tests)
        result = judge(load_case(self.case))
        self.assertTrue(any("has no pass_rule" in flag for flag in result["flags"]))


class ResultAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.case = _copy_case(Path(self.temp.name))

    def test_commit_records_computed_status_and_verify_detects_edit(self) -> None:
        _set_result(self.case, "T4", {"value": 3.0}, {"op": "ge", "value": 2.0})
        record, _ = commit(self.case)
        self.assertEqual(record["test_status"], {"T4": {"status": "passed", "source": "computed"}})
        ok, problems, _ = verify(self.case)
        self.assertTrue(ok, problems)
        _set_result(self.case, "T4", {"value": 1.0}, {"op": "ge", "value": 2.0})
        ok, problems, _ = verify(self.case)
        self.assertFalse(ok)
        self.assertTrue(any("computed test statuses changed" in problem for problem in problems))

    def test_ledger_is_append_only_and_checked(self) -> None:
        record, _ = commit(self.case)
        ledger = self.case / ".geoarg" / "ledger.jsonl"
        lines = ledger.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertIsNone(entry["prev"])
        self.assertEqual(entry["record_sha256"], record_sha256(record))
        ok, problems, _ = verify(self.case)
        self.assertTrue(ok, problems)
        entry["record_sha256"] = "0" * 64
        ledger.write_text(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        ok, problems, _ = verify(self.case)
        self.assertFalse(ok)
        self.assertTrue(any("ledger" in problem for problem in problems))

    def test_two_commits_chain(self) -> None:
        first, _ = commit(self.case)
        second, _ = commit(self.case)
        ledger = self.case / ".geoarg" / "ledger.jsonl"
        entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["prev"], entries[0]["sha256"])
        self.assertEqual(entries[0]["record_sha256"], record_sha256(first))
        self.assertEqual(entries[1]["record_sha256"], record_sha256(second))
        ok, problems, _ = verify(self.case)
        self.assertTrue(ok, problems)


if __name__ == "__main__":
    unittest.main()
