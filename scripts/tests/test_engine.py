"""Tests for the GeoArg contract engine."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import yaml  # noqa: E402

from geoarg import terms  # noqa: E402
from geoarg.audit import commit, verify  # noqa: E402
from geoarg.contract import ContractError, load_case, validate  # noqa: E402
from geoarg.ground import ground_records, validate_grounding  # noqa: E402
from geoarg.hitting import decisive_events  # noqa: E402
from geoarg.independence import effective_n, report as independence_report  # noqa: E402
from geoarg.judge import judge  # noqa: E402
from geoarg.report import render  # noqa: E402

CASE = REPO / "examples" / "south-atlantic"
PAPER = REPO / "examples" / "paper-demo"


def _satisfy_all(case) -> dict[tuple[str, str], str]:
    """Every condition satisfied, without touching any test record."""
    overrides: dict[tuple[str, str], str] = {}
    for cp in case.argument["inference"]["cp"]:
        overrides[("cp", cp["id"])] = "holds"
    for defeater in case.argument["inference"]["defeaters"]:
        overrides[("defeater", defeater["id"])] = "refuted"
    for entailment in case.argument["entailments"]:
        overrides[("entailment", entailment["id"])] = "passed"
    return overrides


class ContractTests(unittest.TestCase):
    def test_example_case_is_clean(self) -> None:
        self.assertEqual(validate(load_case(CASE)), [])

    def test_grounded_example_is_clean(self) -> None:
        self.assertEqual(validate(load_case(PAPER)), [])

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

    def test_duplicate_evidence_id_is_reported(self) -> None:
        case = load_case(CASE)
        records = case.evidence["records"]
        records.append(dict(records[0], statement="a contradictory duplicate"))
        problems = validate(case)
        self.assertTrue(any("duplicate id" in problem for problem in problems))

    def test_unknown_evidence_status_is_reported(self) -> None:
        case = load_case(CASE)
        case.evidence["records"][0]["status"] = "accept"
        problems = validate(case)
        self.assertTrue(any("status must be accepted" in problem for problem in problems))

    def test_untyped_test_cost_is_reported(self) -> None:
        case = load_case(CASE)
        case.tests["records"][0]["cost"] = "cheap"
        problems = validate(case)
        self.assertTrue(any("cost must be a non-negative number" in problem for problem in problems))


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

    def test_satisfied_states_without_passed_tests_cannot_support(self) -> None:
        case = load_case(CASE)
        result = judge(case, _satisfy_all(case))
        self.assertEqual(result["verdict"], "UNTESTED")
        self.assertIn("cp CP1", result["unbacked"][0])
        self.assertTrue(any("no referenced test has passed" in item for item in result["unbacked"]))
        self.assertTrue(any("claims holds but" in reason for reason in result["reasons"]["pending"]))

    def test_passed_test_with_no_power_does_not_support(self) -> None:
        case = load_case(CASE)
        for test in case.tests["records"]:
            test["status"] = "passed"
        result = judge(case, _satisfy_all(case))
        self.assertEqual(result["verdict"], "UNDETERMINED")
        self.assertTrue(any("cp CP2" in item for item in result["unbacked"]))
        self.assertTrue(any("discriminating power none" in item for item in result["unbacked"]))

    def test_supported_flags_low_power_tests(self) -> None:
        case = load_case(CASE)
        for test in case.tests["records"]:
            test["status"] = "passed"
        # T5 is the "passing changes nothing" test; give it low power so the
        # contract can still reach SUPPORTED, then check the flag.
        case.tests_by_id["T5"]["discriminating_power"] = "low"
        result = judge(case, _satisfy_all(case))
        self.assertEqual(result["verdict"], "SUPPORTED")
        self.assertTrue(any("discriminating power" in flag for flag in result["flags"]))

    def test_disputed_evidence_demotes_premise(self) -> None:
        case = load_case(CASE)
        case.evidence["records"][0]["status"] = "disputed"
        result = judge(case)
        statuses = {p["id"]: p["status"] for p in result["premises"]}
        self.assertEqual(statuses["P1"], "disputed")
        self.assertFalse(any(reason.startswith("premise P1") and "supported" in reason for reason in result["reasons"]["pending"]))
        self.assertTrue(result["verdict"] != "SUPPORTED")

    def test_derived_premise_stays_undetermined(self) -> None:
        case = load_case(CASE)
        case.argument["premises"].append(
            {
                "id": "P4",
                "statement": "Depends on another argument.",
                "kind": "derived",
                "layer": "L1",
                "status": "untested",
                "argument_ref": "arg.other",
            }
        )
        for test in case.tests["records"]:
            test["status"] = "passed"
        result = judge(case, _satisfy_all(case))
        self.assertEqual(result["verdict"], "UNDETERMINED")
        self.assertTrue(any("derived premise P4" in flag for flag in result["flags"]))


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

    def test_non_accepted_records_are_excluded(self) -> None:
        case = load_case(CASE)
        case.evidence["records"][0]["status"] = "retracted"
        report = independence_report(case)
        self.assertEqual(report["n_records"], 2)
        self.assertEqual(report["excluded_records"], [{"id": "ev.airmag.sa-1997.m-series", "status": "retracted"}])

    def test_duplicate_refs_count_once(self) -> None:
        case = load_case(CASE)
        case.argument["premises"][0]["evidence_refs"].append("ev.airmag.sa-1997.m-series")
        report = independence_report(case)
        self.assertEqual(report["n_records"], 3)


class HittingTests(unittest.TestCase):
    def test_decisive_events_are_ranked_by_power(self) -> None:
        payload = decisive_events(load_case(CASE))
        self.assertEqual(payload["base_verdict"], "UNTESTED")
        self.assertEqual(len(payload["events"]), 13)
        outcomes = {event["resulting_verdict"] for event in payload["events"]}
        self.assertEqual(outcomes, {"DEFEATED", "SUSPENDED"})
        self.assertEqual(payload["events"][0]["power"], "high")

    def test_decisive_events_carry_cost(self) -> None:
        payload = decisive_events(load_case(CASE))
        self.assertEqual(payload["events"][0]["cost"], 3)
        self.assertTrue(all("cost" in event for event in payload["events"]))


class GroundingTests(unittest.TestCase):
    def test_quote_spanning_a_page_break_grounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "fake.pdf"
            pdf.write_bytes(b"%PDF-1.4 fake")
            case = load_case(CASE)
            record = case.evidence["records"][0]
            record["source_locator"] = {"page": 1, "quote": "the boundary quote starts here"}
            pages = ["aaa the boundary quote", "starts here bbb"]
            metadata = {"extractor": "fake", "pages": 2, "chars": 50, "text_layer": True}
            with mock.patch("geoarg.ground.extract_document", return_value=(pages, metadata)):
                ledger = ground_records(case, pdf)
            entry = ledger["records"][record["id"]]
            self.assertEqual(entry["status"], "grounded")
            self.assertEqual(entry["found_page"], 1)

    def test_old_ledger_schema_is_rejected(self) -> None:
        problems, _ = validate_grounding(load_case(CASE), {"schema_version": "geoarg/ground/0.2", "records": {}})
        self.assertTrue(any("grounding ledger schema" in problem for problem in problems))


class ReportTests(unittest.TestCase):
    def test_brief_does_not_advertise_a_missing_flag(self) -> None:
        brief = render(load_case(CASE), "en", brief=True)
        self.assertNotIn("--full", brief)
        self.assertIn("geoarg report <case>", brief)

    def test_full_report_has_no_none_cells(self) -> None:
        markdown = render(load_case(CASE), "en")
        self.assertNotIn("None", markdown)

    def test_full_report_carries_engine_and_ledger_digests(self) -> None:
        markdown = render(load_case(CASE), "en")
        self.assertIn("checker version:", markdown)
        self.assertIn("quote-check format:", markdown)


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

    def test_commit_refuses_unbacked_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            import shutil

            shutil.copytree(CASE, case_dir)
            case = load_case(case_dir)
            for cp in case.argument["inference"]["cp"]:
                cp["state"] = "holds"
            for defeater in case.argument["inference"]["defeaters"]:
                defeater["state"] = "refuted"
            for entailment in case.argument["entailments"]:
                entailment["status"] = "passed"
            (case_dir / "argument.yaml").write_text(
                yaml.safe_dump(case.argument, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            with self.assertRaises(ContractError):
                commit(case_dir)

    def test_ambiguous_registry_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            import shutil

            shutil.copytree(CASE, case_dir)
            commit(case_dir)
            registry = case_dir / ".geoarg" / "registry"
            (registry / "C0.json").write_text('{"claim_id": "C0", "verdict": "DEFEATED"}\n', encoding="utf-8")
            ok, problems, _ = verify(case_dir)
            self.assertFalse(ok)
            self.assertTrue(any("ambiguous registry" in problem for problem in problems))

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


class ProfileContractTests(unittest.TestCase):
    def test_omitted_profile_is_valid(self) -> None:
        case = load_case(CASE)
        case.argument.pop("profile")
        self.assertEqual(validate(case), [])

    def test_unknown_primary_profile_is_reported(self) -> None:
        case = load_case(CASE)
        case.argument["profile"]["primary"] = "mining"
        self.assertTrue(any("argument.profile" in problem for problem in validate(case)))

    def test_secondary_must_not_repeat_primary(self) -> None:
        case = load_case(CASE)
        case.argument["profile"] = {"primary": "tectonics", "secondary": ["tectonics"]}
        self.assertTrue(any("must not repeat the primary" in problem for problem in validate(case)))

    def test_duplicate_secondary_profile_is_reported(self) -> None:
        case = load_case(CASE)
        case.argument["profile"] = {"primary": "tectonics", "secondary": ["geochronology", "geochronology"]}
        self.assertTrue(any("duplicate secondary" in problem for problem in validate(case)))


class PlainWordingTests(unittest.TestCase):
    def test_status_labels_and_explanations_are_plain(self) -> None:
        self.assertEqual(terms.status_label("UNTESTED", "zh"), "未检验")
        self.assertEqual(terms.status_label("UNTESTED", "en"), "not tested")
        explanations = {
            terms.status_explanation(verdict, "zh")
            for verdict in ("UNTESTED", "UNDETERMINED", "SUSPENDED", "DEFEATED", "SUPPORTED")
        }
        self.assertEqual(len(explanations), 5)
        self.assertTrue(all(explanations))

    def test_condition_sentence_uses_the_authors_statement(self) -> None:
        case = load_case(CASE)
        result = judge(case)
        item = next(
            item for item in result["reason_items"] if item["kind"] == "cp" and item["state"] == "unknown"
        )
        sentence = terms.item_sentence(case, item, "zh")
        self.assertIn("尚未检验", sentence)
        self.assertIn(terms.statement_of(case, "cp", item["id"]), sentence)

    def test_declared_field_label_and_omitted_field_label(self) -> None:
        case = load_case(CASE)
        self.assertEqual(terms.profile_label(case, "zh"), "构造地质学")
        self.assertEqual(terms.profile_label(case, "en"), "tectonics")
        bare = load_case(CASE)
        bare.argument.pop("profile")
        self.assertEqual(terms.profile_label(bare, "zh"), "未声明")
        self.assertEqual(terms.profile_label(bare, "en"), "not declared")

    def test_judgment_is_normalised_before_hashing(self) -> None:
        raw = "  第一段。\n\n\n第二段  "
        self.assertEqual(terms.normalize_judgment(raw), "第一段。\n\n第二段")
        self.assertEqual(terms.normalize_judgment(raw), terms.normalize_judgment("第一段。\n\n第二段"))
        self.assertEqual(len(terms.judgment_digest(raw)), 64)
        self.assertNotEqual(terms.judgment_digest(raw), terms.judgment_digest("第一段。"))

    def test_power_label_is_localised(self) -> None:
        self.assertEqual(terms.power_label("high", "zh"), "高")
        self.assertEqual(terms.power_label("medium", "zh"), "中")
        self.assertEqual(terms.power_label("low", "zh"), "低")
        self.assertEqual(terms.power_label("none", "zh"), "无")
        self.assertEqual(terms.power_label("high", "en"), "high")
        self.assertEqual(terms.power_label(None, "zh"), "-")

    def test_unbacked_entailment_wording_does_not_contradict_itself(self) -> None:
        case = load_case(CASE)
        case.argument["entailments"][0]["status"] = "passed"
        result = judge(case)
        item = next(
            item for item in result["reason_items"] if item["kind"] == "entailment" and item["state"] == "passed"
        )
        sentence = terms.item_sentence(case, item, "zh")
        self.assertIn("还没有检验结果支撑它", sentence)
        self.assertNotIn("但还没有检验通过", sentence)

    def test_reason_sentence_adds_one_stop(self) -> None:
        case = load_case(CASE)
        item = {"kind": "premise", "id": "P1", "state": "undetermined", "bucket": "pending"}
        sentence = terms.item_sentence(case, item, "zh")
        self.assertNotIn("。；", sentence)
        self.assertTrue(sentence.endswith("。"))


class ReasonItemTests(unittest.TestCase):
    def test_judge_returns_structured_reason_items(self) -> None:
        result = judge(load_case(CASE))
        self.assertTrue(result["reason_items"])
        for item in result["reason_items"]:
            self.assertIn(item["bucket"], {"hard", "soft", "pending"})
            self.assertIn(item["kind"], {"premise", "cp", "defeater", "entailment"})


class PlainReportTests(unittest.TestCase):
    def test_report_headings_are_plain_and_use_no_tool_jargon(self) -> None:
        markdown = render(load_case(CASE), "zh")
        self.assertIn("## 为什么是这个结论", markdown)
        self.assertIn("## 必须成立的条件", markdown)
        self.assertIn("## 反面证据", markdown)
        self.assertIn("## 必须成立的推论", markdown)
        self.assertNotIn("ceteris paribus", markdown)
        self.assertNotIn("## 适用条件", markdown)

    def test_report_does_not_print_raw_engine_flags(self) -> None:
        markdown = render(load_case(CASE), "zh")
        self.assertNotIn("blocking gap registered", markdown)
        self.assertNotIn("已登记阻塞性缺口", markdown)

    def test_report_verdict_explanation_matches_the_terms_module(self) -> None:
        markdown = render(load_case(CASE), "zh")
        self.assertIn(terms.status_explanation("UNTESTED", "zh"), markdown)


if __name__ == "__main__":
    unittest.main()
