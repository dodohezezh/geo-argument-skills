"""Tests for 0.9 workspaces and argument chains."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from geoarg import chain, terms
from geoarg.audit import commit, verify
from geoarg.cli import main
from geoarg.contract import ContractError, load_case
from geoarg.judge import judge
from geoarg.migrate import migrate

REPO = Path(__file__).resolve().parents[2]
CASES = REPO / "examples"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _dump(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _copy(dest: Path, name: str = "paper-demo", argument_id: str | None = None) -> Path:
    shutil.copytree(CASES / name, dest)
    if argument_id:
        arg_path = dest / "argument.yaml"
        argument = _load(arg_path)
        argument["id"] = argument_id
        _dump(arg_path, argument)
    return dest


def _derive(case_dir: Path, argument_ref: str, premise_id: str = "P3") -> None:
    path = case_dir / "argument.yaml"
    argument = _load(path)
    for premise in argument["premises"]:
        if premise["id"] == premise_id:
            premise["kind"] = "derived"
            premise["argument_ref"] = argument_ref
            premise.pop("evidence_refs", None)
            premise.pop("test_refs", None)
    _dump(path, argument)


def _workspace(root: Path, mapping: dict[str, str]) -> None:
    payload = {
        "schema_version": "geoarg/workspace/0.1",
        "arguments": [{"id": key, "case": value} for key, value in mapping.items()],
    }
    (root / "workspace.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def _supported_case(dest: Path) -> Path:
    """A copy of south-atlantic forced to a SUPPORTED verdict."""
    case_dir = _copy(dest, "south-atlantic", argument_id="arg.a")
    arg_path = case_dir / "argument.yaml"
    argument = _load(arg_path)
    for cp in argument["inference"]["cp"]:
        cp["state"] = "holds"
    for defeater in argument["inference"]["defeaters"]:
        defeater["state"] = "refuted"
    for entailment in argument["entailments"]:
        entailment["status"] = "passed"
    _dump(arg_path, argument)
    test_path = case_dir / "test.yaml"
    tests = _load(test_path)
    for record in tests["records"]:
        record["status"] = "passed"
        if record["id"] == "T5":
            record["discriminating_power"] = "low"
    _dump(test_path, tests)
    return case_dir


class ChainResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.case_a = _copy(self.root / "case-a", argument_id="arg.a")
        self.case_b = _copy(self.root / "case-b", argument_id="arg.b")
        _derive(self.case_b, "arg.a")
        _workspace(self.root, {"arg.a": "case-a", "arg.b": "case-b"})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_resolved_chain_is_used_by_judge(self) -> None:
        case_b = load_case(self.case_b)
        result = judge(case_b)
        premises = {item["id"]: item for item in result["premises"]}
        self.assertEqual(premises["P3"]["status"], "chain-undetermined")
        self.assertEqual(premises["P3"]["chain"]["ref"], "arg.a")
        self.assertEqual(premises["P3"]["chain"]["verdict"], "UNTESTED")
        summary = chain.chain_summary(self.case_b)
        self.assertEqual(summary["entries"][0]["status"], "resolved")
        self.assertEqual(chain.chain_problems(self.case_b), [])

    def test_unresolved_reference_is_reported(self) -> None:
        _derive(self.case_b, "arg.missing")
        problems = chain.chain_problems(self.case_b)
        self.assertTrue(any("cannot be resolved" in problem for problem in problems))
        result = judge(load_case(self.case_b))
        self.assertTrue(any("not resolved in the workspace" in flag for flag in result["flags"]))
        self.assertEqual(result["verdict"], "UNTESTED")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["check", str(self.case_b), "--json"])
        self.assertEqual(code, 1)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(any("cannot be resolved" in problem for problem in payload["problems"]))

    def test_cycle_is_reported(self) -> None:
        _derive(self.case_a, "arg.b")
        _derive(self.case_b, "arg.a")
        problems = chain.chain_problems(self.case_a)
        self.assertTrue(any("cycle" in problem for problem in problems))
        result = judge(load_case(self.case_a))
        self.assertTrue(any("argument chain cycle" in flag for flag in result["flags"]))
        self.assertEqual(result["verdict"], "UNTESTED")

    def test_plain_language_for_chain_states(self) -> None:
        result = judge(load_case(self.case_b))
        item = next(
            entry for entry in result["reason_items"] if entry.get("kind") == "premise" and entry.get("chain")
        )
        sentence_zh = terms.item_sentence(load_case(self.case_b), item, "zh")
        self.assertIn("结论来自另一条论证", sentence_zh)
        self.assertNotIn("chain-", sentence_zh)
        _derive(self.case_b, "arg.missing")
        result = judge(load_case(self.case_b))
        item = next(
            entry for entry in result["reason_items"] if entry.get("kind") == "premise" and entry.get("chain")
        )
        self.assertIn("找不到被引用的论证", terms.item_sentence(load_case(self.case_b), item, "zh"))


class JudgeChainStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.case_a = _supported_case(self.root / "case-a")
        self.case_b = _copy(self.root / "case-b", argument_id="arg.b")
        _derive(self.case_b, "arg.a")
        _workspace(self.root, {"arg.a": "case-a", "arg.b": "case-b"})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_supported_target_lifts_a_derived_premise(self) -> None:
        self.assertEqual(judge(load_case(self.case_a))["verdict"], "SUPPORTED")
        result = judge(load_case(self.case_b))
        premises = {item["id"]: item for item in result["premises"]}
        self.assertEqual(premises["P3"]["status"], "chain-supported")
        self.assertFalse(any(entry.get("id") == "P3" for entry in result["reason_items"]))


class AuditChainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.case_a = _copy(self.root / "case-a", argument_id="arg.a")
        self.case_b = _copy(self.root / "case-b", argument_id="arg.b")
        _derive(self.case_b, "arg.a")
        _workspace(self.root, {"arg.a": "case-a", "arg.b": "case-b"})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_commit_records_chain_and_verify_detects_drift(self) -> None:
        record, _ = commit(self.case_b)
        self.assertIn("chain", record)
        self.assertEqual(record["chain"]["entries"], 1)
        ok, problems, _ = verify(self.case_b)
        self.assertTrue(ok, problems)
        _derive(self.case_b, "arg.missing")
        ok, problems, _ = verify(self.case_b)
        self.assertFalse(ok)
        self.assertTrue(any("argument chain changed since commit" in problem for problem in problems))
        self.assertTrue(any("cannot be resolved" in problem for problem in problems))

    def test_commit_refuses_an_unresolved_chain(self) -> None:
        _derive(self.case_b, "arg.missing")
        with self.assertRaises(ContractError) as caught:
            commit(self.case_b)
        self.assertIn("cannot be resolved", str(caught.exception))


class WorkspaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _copy(self.root / "case-a", argument_id="arg.a")
        case_b = _copy(self.root / "case-b", argument_id="arg.b")
        _derive(case_b, "arg.a")
        _workspace(self.root, {"arg.a": "case-a", "arg.b": "case-b"})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_workspace_report_and_markdown(self) -> None:
        report = chain.workspace_report(self.root)
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual(len(report["cases"]), 2)
        self.assertEqual(len(report["chains"]), 1)
        self.assertEqual(report["chains"][0]["status"], "resolved")
        markdown = chain.render_workspace(report, "zh")
        self.assertIn("论证链", markdown)
        self.assertIn("案例", markdown)

    def test_cli_workspace_json(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["workspace", str(self.root), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["cases"]), 2)

    def test_migrate_workspace_file(self) -> None:
        workspace_file = self.root / "workspace.yaml"
        old = workspace_file.read_text(encoding="utf-8").replace("geoarg/workspace/0.1", "geoarg/workspace/0.0")
        workspace_file.write_text(old, encoding="utf-8")
        rows = migrate(self.root)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["changed"])
        self.assertIn("geoarg/workspace/0.1", workspace_file.read_text(encoding="utf-8"))
        again = migrate(self.root)
        self.assertFalse(again[0]["changed"])


class WorkspaceExampleTests(unittest.TestCase):
    def test_bundled_workspace_example_is_consistent(self) -> None:
        report = chain.workspace_report(CASES / "workspace-demo")
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual(len(report["cases"]), 2)
        self.assertEqual(len(report["chains"]), 1)
        entry = report["chains"][0]
        self.assertEqual(entry["status"], "resolved")
        self.assertEqual(entry["target_argument"], "basement-age")

    def test_bundled_workspace_example_cli(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["workspace", str(CASES / "workspace-demo"), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
