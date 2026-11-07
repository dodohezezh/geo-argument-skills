"""Conclusion pages: same facts, two readers, plain language."""

from __future__ import annotations

import contextlib
import hashlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geoarg import cli, terms  # noqa: E402
from geoarg.card import build_card, render_card  # noqa: E402
from geoarg.contract import load_case  # noqa: E402
from geoarg.hitting import decisive_events  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CASE = REPO / "examples" / "south-atlantic"


class CardModelTest(unittest.TestCase):
    def test_cards_agree_on_the_computed_facts(self) -> None:
        case = load_case(CASE)
        researcher = build_card(case, "en", "researcher")
        reviewer = build_card(case, "en", "reviewer")
        self.assertEqual(dict(researcher["meta"])["conclusion"], "not tested")
        self.assertEqual(dict(reviewer["meta"])["conclusion"], "not tested")
        self.assertEqual(dict(researcher["meta"])["reader"], "researcher (self-check)")
        self.assertEqual(dict(reviewer["meta"])["reader"], "reviewer (assessment)")

    def test_unknown_role_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_card(load_case(CASE), "en", "editor")


class ResearcherCardTest(unittest.TestCase):
    def test_researcher_card_puts_the_next_check_first(self) -> None:
        text = render_card(load_case(CASE), "en", "researcher")
        self.assertTrue(text.startswith("# GeoArg conclusion:"))
        self.assertIn("## Conclusion", text)
        self.assertIn("## What to check next", text)
        self.assertIn("## Numbers", text)
        self.assertIn("not tested", text)
        self.assertIn(
            "independent evidence: about 1.2 lines (out of 3 records; mean correlation 0.75)",
            text,
        )
        self.assertIn("T7", text)
        self.assertNotIn("## What would change the conclusion", text)
        self.assertNotIn("## Conclusion and reasons", text)

    def test_chinese_researcher_card(self) -> None:
        text = render_card(load_case(CASE), "zh", "researcher")
        self.assertIn("# GeoArg 结论", text)
        self.assertIn("## 接下来该做什么", text)
        self.assertIn("## 数字", text)
        self.assertIn("未检验", text)


class ReviewerCardTest(unittest.TestCase):
    def test_reviewer_card_itemises_reasons_and_full_paths(self) -> None:
        text = render_card(load_case(CASE), "en", "reviewer")
        self.assertIn("## Conclusion and reasons", text)
        self.assertIn("## Why the claim is not established", text)
        self.assertIn("## What would change the conclusion", text)
        self.assertIn("## Evidence and independence", text)
        self.assertIn("CP1:", text)
        self.assertIn("it has not been tested", text)
        events = decisive_events(load_case(CASE))["events"]
        for event in events:
            self.assertIn(str(event["id"]), text)  # every single-event path, not only the top three

    def test_chinese_reviewer_card(self) -> None:
        text = render_card(load_case(CASE), "zh", "reviewer")
        self.assertIn("## 结论与理由", text)
        self.assertIn("## 为什么还不能确认", text)
        self.assertIn("## 哪些结果会改变结论", text)
        self.assertIn("## 证据与独立性", text)
        self.assertIn("CP1：", text)
        self.assertIn("尚未检验", text)


class JudgementTest(unittest.TestCase):
    def test_judgement_paragraph_is_recorded_with_its_digest(self) -> None:
        judgment = "该主张目前无法判定：三项条件均未检验，因此结论停在未检验。"
        text = render_card(load_case(CASE), "zh", "reviewer", judgment=judgment)
        self.assertIn("## 评述", text)
        self.assertIn("评述：由模型撰写；对评述文字的 sha256：", text)

    def test_judgment_digest_is_full_and_recomputable_from_the_printed_text(self) -> None:
        judgment = "  第一段：判决未检验。\n\n  第二段：下一步应做 T2。  "
        text = render_card(load_case(CASE), "en", "reviewer", judgment=judgment)
        normalized = terms.normalize_judgment(judgment)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        self.assertEqual(len(digest), 64)
        self.assertIn(f"sha256 of the commentary text: {digest}", text)
        # The paragraph printed in the card is exactly the text that was hashed.
        for paragraph in normalized.split("\n\n"):
            self.assertIn(paragraph, text)

    def test_missing_judgment_is_marked(self) -> None:
        researcher = render_card(load_case(CASE), "en", "researcher")
        self.assertNotIn("## Commentary", researcher)
        reviewer = render_card(load_case(CASE), "en", "reviewer")
        self.assertIn("commentary: not provided", reviewer)


class VerdictHeadingTest(unittest.TestCase):
    """The explanation section must describe the conclusion it actually holds."""

    def _case_copy(self) -> Path:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        case_dir = Path(tmp) / "case"
        shutil.copytree(CASE, case_dir)
        return case_dir

    def _satisfy(self, case_dir: Path) -> None:
        argument = yaml.safe_load((case_dir / "argument.yaml").read_text(encoding="utf-8"))
        for cp in argument["inference"]["cp"]:
            cp["state"] = "holds"
        for defeater in argument["inference"]["defeaters"]:
            defeater["state"] = "refuted"
        for entailment in argument["entailments"]:
            entailment["status"] = "passed"
        (case_dir / "argument.yaml").write_text(
            yaml.safe_dump(argument, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        tests = yaml.safe_load((case_dir / "test.yaml").read_text(encoding="utf-8"))
        for record in tests["records"]:
            record["status"] = "passed"
            if record["discriminating_power"] == "none":
                record["discriminating_power"] = "low"
        (case_dir / "test.yaml").write_text(
            yaml.safe_dump(tests, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def test_supported_card_explains_why_it_holds(self) -> None:
        case_dir = self._case_copy()
        self._satisfy(case_dir)
        text = render_card(load_case(case_dir), "en", "reviewer")
        self.assertIn("## Why it holds", text)
        self.assertNotIn("## Why the claim is not established", text)
        self.assertIn("tests that carry the conclusion:", text)

    def test_defeated_card_attributes_the_defeat(self) -> None:
        case_dir = self._case_copy()
        argument = yaml.safe_load((case_dir / "argument.yaml").read_text(encoding="utf-8"))
        argument["inference"]["defeaters"][0]["state"] = "established"
        (case_dir / "argument.yaml").write_text(
            yaml.safe_dump(argument, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        text = render_card(load_case(case_dir), "en", "reviewer")
        self.assertIn("## What refutes it", text)
        self.assertNotIn("## Why the claim is not established", text)
        self.assertIn("D1:", text)
        self.assertIn("it is established (fatal)", text)

    def test_defeated_card_does_not_list_outcomes_that_keep_the_same_verdict(self) -> None:
        case_dir = self._case_copy()
        argument = yaml.safe_load((case_dir / "argument.yaml").read_text(encoding="utf-8"))
        argument["inference"]["defeaters"][0]["state"] = "established"
        (case_dir / "argument.yaml").write_text(
            yaml.safe_dump(argument, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        text = render_card(load_case(case_dir), "en", "reviewer")
        self.assertIn("The conclusion is already refuted", text)
        self.assertNotIn("if this happens", text)
        # The fatal item explains the defeat once, not twice.
        self.assertNotIn("fatal issues:", text)
        self.assertEqual(text.count("D1:"), 1)

    def test_researcher_next_section_lists_unfinished_tests(self) -> None:
        text = render_card(load_case(CASE), "en", "researcher")
        next_block = text.split("## What to check next")[1].split("##")[0]
        self.assertIn("what it checks", next_block)
        self.assertNotIn("if the evidence for", next_block)
        self.assertRegex(next_block, r"\| T\d+ \|")

    def test_power_words_are_localised(self) -> None:
        zh = render_card(load_case(CASE), "zh", "researcher")
        self.assertIn("| 高 |", zh)
        self.assertNotIn("| high |", zh)


class CardCliTest(unittest.TestCase):
    def test_cli_writes_the_card_to_a_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "south-atlantic"
            shutil.copytree(CASE, case_dir)
            target = Path(tmp) / "card.md"
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = cli.main(
                    ["card", str(case_dir), "--for", "researcher", "--lang", "zh", "--out", str(target)]
                )
            self.assertEqual(code, 0)
            self.assertIn("wrote", out.getvalue())
            self.assertTrue(target.exists())
            self.assertIn("# GeoArg 结论", target.read_text(encoding="utf-8"))

    def test_cli_reads_the_judgment_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "south-atlantic"
            shutil.copytree(CASE, case_dir)
            judgment = Path(tmp) / "judgment.md"
            judgment.write_text("该主张目前无法判定。", encoding="utf-8")
            target = Path(tmp) / "card.md"
            with contextlib.redirect_stdout(io.StringIO()):
                code = cli.main(
                    [
                        "card",
                        str(case_dir),
                        "--for",
                        "reviewer",
                        "--lang",
                        "zh",
                        "--judgment-file",
                        str(judgment),
                        "--out",
                        str(target),
                    ]
                )
            self.assertEqual(code, 0)
            text = target.read_text(encoding="utf-8")
            self.assertIn("## 评述", text)
            self.assertIn("该主张目前无法判定。", text)

    def test_cli_rejects_two_judgment_sources(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(
                ["card", str(CASE), "--for", "researcher", "--judgment", "a", "--judgment-file", "b.md"]
            )
        self.assertEqual(code, 2)

    def test_cli_requires_a_reader(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.main(["card", str(CASE)])


if __name__ == "__main__":
    unittest.main()
