"""counter_evidence: contract validation, judge output, independence, impact, report."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from geoarg import contract, independence, judge, migrate
from geoarg.cli import main
from geoarg.impact import impact_report

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"


def make_case(target: Path) -> Path:
    root = target / "case"
    shutil.copytree(EXAMPLES / "paper-demo", root)
    return root


def add_counter(root: Path, kind: str, item_id: str, refs: list[str]) -> None:
    data = contract.yaml.safe_load((root / "argument.yaml").read_text(encoding="utf-8"))
    if kind == "defeater":
        rows = data["inference"]["defeaters"]
    else:
        rows = data["entailments"]
    for row in rows:
        if row.get("id") == item_id:
            row["counter_evidence"] = refs
            break
    else:
        raise AssertionError(f"no {kind} {item_id}")
    (root / "argument.yaml").write_text(
        contract.yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


class CounterEvidenceTests(unittest.TestCase):
    def test_judge_reports_counter_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_case(Path(tmp))
            add_counter(root, "defeater", "D1", ["ev.dated.zircon"])
            add_counter(root, "entailment", "E1", ["ev.extent.mapping"])
            case = contract.load_case(root)
            self.assertEqual(contract.validate(case), [])
            result = judge.judge(case)
            defeaters = {row["id"]: row for row in result["defeaters"]}
            entailments = {row["id"]: row for row in result["entailments"]}
            self.assertEqual(defeaters["D1"]["counter_evidence"], ["ev.dated.zircon"])
            self.assertEqual(entailments["E1"]["counter_evidence"], ["ev.extent.mapping"])
            self.assertEqual(defeaters["D2"]["counter_evidence"], [])

    def test_independence_reports_counter_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_case(Path(tmp))
            add_counter(root, "defeater", "D1", ["ev.dated.zircon"])
            add_counter(root, "defeater", "D2", ["ev.extent.mapping"])
            case = contract.load_case(root)
            payload = independence.report(case)
            counter = payload["counter"]
            self.assertEqual(counter["n_records"], 2)
            self.assertEqual(counter["ids"], ["ev.dated.zircon", "ev.extent.mapping"])
            self.assertLessEqual(counter["n_eff"], 2)
            self.assertGreaterEqual(counter["n_eff"], 1)
            self.assertIn("not counted as support", counter["note"])

    def test_impact_marks_counter_evidence_as_referenced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_case(Path(tmp))
            add_counter(root, "defeater", "D1", ["ev.dated.zircon"])
            case = contract.load_case(root)
            payload = impact_report(case)
            rows = {row["id"]: row for row in payload["ablation"]["evidence"]}
            row = rows["ev.dated.zircon"]
            self.assertTrue(row["referenced"])
            self.assertTrue(row["counter"])
            self.assertNotEqual(row["class"], "unused")
            self.assertEqual(payload["counter_evidence"], ["ev.dated.zircon"])

    def test_report_has_counter_evidence_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_case(Path(tmp))
            add_counter(root, "defeater", "D1", ["ev.dated.zircon"])
            out = Path(tmp) / "report.md"
            self.assertEqual(main(["report", str(root), "--format", "md", "--out", str(out)]), 0)
            text = out.read_text(encoding="utf-8")
            self.assertIn("Counter-evidence records", text)
            self.assertIn("ev.dated.zircon", text)

    def test_unknown_counter_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_case(Path(tmp))
            add_counter(root, "defeater", "D1", ["ev.not.real"])
            problems = contract.validate(contract.load_case(root))
            self.assertTrue(any("unknown counter_evidence" in problem for problem in problems))

    def test_duplicate_counter_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_case(Path(tmp))
            add_counter(root, "entailment", "E1", ["ev.dated.zircon", "ev.dated.zircon"])
            problems = contract.validate(contract.load_case(root))
            self.assertTrue(any("duplicate ids" in problem for problem in problems))

    def test_non_list_counter_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_case(Path(tmp))
            add_counter(root, "defeater", "D1", "ev.dated.zircon")  # type: ignore[arg-type]
            problems = contract.validate(contract.load_case(root))
            self.assertTrue(any("must be a list of evidence ids" in problem for problem in problems))

    def test_shipped_schema_accepts_counter_evidence(self) -> None:
        schema_path = REPO / "scripts" / "geoarg" / "_schema" / "argument.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        found = False

        def walk(node):
            nonlocal found
            if isinstance(node, dict):
                props = node.get("properties")
                if isinstance(props, dict) and "counter_evidence" in props:
                    found = True
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(schema)
        self.assertTrue(found)

    def test_migrate_bumps_old_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_case(Path(tmp))
            argument = root / "argument.yaml"
            text = argument.read_text(encoding="utf-8").replace("geoarg/0.7", "geoarg/0.6", 1)
            argument.write_text(text, encoding="utf-8")
            changed = migrate.migrate(root)
            self.assertTrue(changed)
            self.assertIn("geoarg/0.7", argument.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
