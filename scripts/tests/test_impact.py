"""Tests for the 1.3 decision-value layer (impact)."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from geoarg import impact
from geoarg.contract import ContractError

REPO = Path(__file__).resolve().parents[2]
PAPER = REPO / "examples" / "paper-demo"
WORKSPACE = REPO / "examples" / "workspace-demo"


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    from geoarg.cli import main

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class AblationTests(unittest.TestCase):
    def test_removing_evidence_changes_the_verdict(self) -> None:
        payload = impact.impact_report(PAPER)
        rows = {row["id"]: row for row in payload["ablation"]["evidence"]}
        self.assertEqual(rows["ev.dated.zircon"]["class"], "decisive")
        self.assertEqual(rows["ev.dated.zircon"]["verdict_without"], "DEFEATED")
        self.assertTrue(rows["ev.dated.zircon"]["referenced"])

    def test_test_classes_use_the_documented_vocabulary(self) -> None:
        payload = impact.impact_report(PAPER)
        allowed = {"decisive", "backing", "redundant", "untapped"}
        self.assertTrue(payload["ablation"]["tests"])
        for row in payload["ablation"]["tests"]:
            self.assertIn(row["class"], allowed)
            self.assertIn(row["verdict_without"], {"DEFEATED", "SUSPENDED", "UNTESTED", "UNDETERMINED", "SUPPORTED"})

    def test_report_has_remaining_and_independence(self) -> None:
        payload = impact.impact_report(PAPER)
        self.assertIn("pending", payload["remaining"])
        self.assertIn("gating", payload["remaining"])
        self.assertIsNotNone(payload["independence"]["before"].get("n_eff"))
        self.assertIn("no probability", " ".join(payload["limits"]))


class WhatIfTests(unittest.TestCase):
    def test_assumptions_move_the_verdict(self) -> None:
        payload = impact.impact_report(
            PAPER,
            assumptions=["test:T1=passed", "cp:CP1=holds"],
        )
        self.assertEqual(payload["before"]["verdict"], "UNTESTED")
        self.assertEqual(payload["after"]["verdict"], "UNDETERMINED")
        self.assertEqual(payload["value"]["class"], "decisive")
        self.assertEqual(payload["value"]["verdict_delta"], 1)
        self.assertEqual(len(payload["value"]["assumptions"]), 2)

    def test_unknown_assumption_kind_is_an_error(self) -> None:
        with self.assertRaises(ContractError):
            impact.impact_report(PAPER, assumptions=["weather:T1=rainy"])

    def test_malformed_assumption_is_an_error(self) -> None:
        with self.assertRaises(ContractError):
            impact.impact_report(PAPER, assumptions=["test:T1"])

    def test_evidence_status_assumption(self) -> None:
        payload = impact.impact_report(PAPER, assumptions=["evidence:ev.dated.zircon=retracted"])
        self.assertIn(payload["value"]["class"], {"decisive", "backing"})
        self.assertEqual(payload["after"]["verdict"], "DEFEATED")

    def test_render_english_and_chinese(self) -> None:
        payload = impact.impact_report(PAPER, assumptions=["test:T1=passed", "cp:CP1=holds"])
        english = impact.render_impact(payload, lang="en")
        chinese = impact.render_impact(payload, lang="zh")
        self.assertIn("# Decision value", english)
        self.assertIn("Leave-one-out: evidence", english)
        self.assertIn("# 决策价值", chinese)
        self.assertIn("留一法", chinese)


class ProspectiveEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-impact-"))

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unreferenced_evidence_is_redundant(self) -> None:
        record = {
            "id": "ev.new",
            "kind": "measurement",
            "layer": "L1",
            "statement": "A new measurement that no premise references yet.",
            "status": "undetermined",
        }
        payload = impact.impact_report(PAPER, add_evidence=[record])
        self.assertEqual(payload["before"]["verdict"], payload["after"]["verdict"])
        self.assertEqual(payload["value"]["class"], "redundant")
        self.assertEqual(payload["prospective_evidence"], ["ev.new"])

    def test_evidence_file_roundtrip_and_errors(self) -> None:
        path = self.tmp / "new.yaml"
        path.write_text(
            "records:\n- id: ev.new\n  kind: measurement\n  statement: A new measurement.\n",
            encoding="utf-8",
        )
        records = impact.load_evidence_file(path)
        self.assertEqual(records[0]["id"], "ev.new")
        self.assertEqual(records[0]["status"], "undetermined")
        with self.assertRaises(ContractError):
            impact.load_evidence_file(self.tmp / "missing.yaml")
        bad = self.tmp / "bad.yaml"
        bad.write_text("records:\n- kind: measurement\n  statement: no id\n", encoding="utf-8")
        with self.assertRaises(ContractError):
            impact.load_evidence_file(bad)
        duplicate = self.tmp / "dupe.yaml"
        duplicate.write_text(
            "records:\n- id: ev.x\n  statement: one\n- id: ev.x\n  statement: two\n",
            encoding="utf-8",
        )
        with self.assertRaises(ContractError):
            impact.load_evidence_file(duplicate)

    def test_workspace_impact_rows(self) -> None:
        payload = impact.workspace_impact(
            WORKSPACE,
            [{"id": "ev.geodetic", "kind": "measurement", "statement": "A geodetic rate.", "status": "undetermined"}],
        )
        self.assertEqual(len(payload["rows"]), 2)
        self.assertEqual(payload["changed"], 0)
        self.assertIn("does not change", payload["conclusion"])


class ImpactCliTests(unittest.TestCase):
    def test_impact_cli_json(self) -> None:
        code, out, err = run_cli(
            ["impact", str(PAPER), "--assume", "test:T1=passed", "--assume", "cp:CP1=holds", "--json"]
        )
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["value"]["class"], "decisive")

    def test_impact_cli_markdown_to_file(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="geoarg-impact-"))
        try:
            target = tmp / "impact.md"
            code, out, err = run_cli(["impact", str(PAPER), "--out", str(target), "--lang", "zh"])
            self.assertEqual(code, 0, err)
            self.assertIn("wrote", out)
            self.assertIn("决策价值", target.read_text(encoding="utf-8"))
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)

    def test_workspace_impact_requires_evidence(self) -> None:
        code, _, err = run_cli(["impact", str(WORKSPACE), "--workspace"])
        self.assertEqual(code, 2)
        self.assertIn("--add-evidence", err)

    def test_missing_case_is_an_error(self) -> None:
        code, _, err = run_cli(["impact", str(REPO / "examples" / "nope")])
        self.assertEqual(code, 2)
        self.assertIn("error:", err)


if __name__ == "__main__":
    unittest.main()
