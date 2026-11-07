"""Report rendering: one document model, Markdown and Word outputs."""

from __future__ import annotations

import contextlib
import hashlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geoarg import cli, terms  # noqa: E402
from geoarg.contract import load_case  # noqa: E402
from geoarg.report import build, render, render_docx  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CASE = REPO / "examples" / "south-atlantic"


class ReportModelTest(unittest.TestCase):
    def test_model_keeps_the_sections_the_audit_needs(self) -> None:
        model = build(load_case(CASE))
        headings = [section["heading"] for section in model["sections"]]
        for expected in (
            "Why this conclusion",
            "Are the evidence lines independent?",
            "Do the quotes match the source?",
            "What would change the conclusion",
        ):
            self.assertIn(expected, headings)
        self.assertEqual(dict(model["meta"])["conclusion"], "not tested")

    def test_markdown_renders_from_the_same_model(self) -> None:
        text = render(load_case(CASE))
        self.assertTrue(text.startswith("# GeoArg report:"))
        self.assertIn(
            "independent evidence: about 1.2 lines (out of 3 records; mean correlation 0.75)",
            text,
        )
        self.assertIn("| P1 ", text)

    def test_docx_contains_tables_and_the_title(self) -> None:
        from docx import Document

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.docx"
            written = render_docx(load_case(CASE), target)
            self.assertEqual(written, target)
            document = Document(str(target))
            paragraphs = "\n".join(paragraph.text for paragraph in document.paragraphs)
            self.assertIn("GeoArg report", paragraphs)
            self.assertGreaterEqual(len(document.tables), 5)
            cells = "\n".join(
                cell.text for table in document.tables for row in table.rows for cell in row.cells
            )
            self.assertIn("P1", cells)

    def test_cli_writes_word_by_default_and_markdown_on_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "south-atlantic"
            shutil.copytree(CASE, case_dir)

            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = cli.main(["report", str(case_dir)])
            self.assertEqual(code, 0)
            self.assertTrue((case_dir / "report.docx").exists())
            self.assertIn("report.docx", out.getvalue())

            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = cli.main(["report", str(case_dir), "--format", "md"])
            self.assertEqual(code, 0)
            self.assertIn("# GeoArg report:", out.getvalue())

    def test_chinese_report_translates_the_frame_only(self) -> None:
        text = render(load_case(CASE), lang="zh")
        self.assertIn("# GeoArg 报告", text)
        self.assertIn("## 为什么是这个结论", text)
        self.assertIn("## 前提", text)
        self.assertIn("## 哪些结果会改变结论", text)
        self.assertIn("独立证据：约 1.2 条", text)
        self.assertIn("| P1 ", text)


class PlainLanguageReportTest(unittest.TestCase):
    def test_chinese_report_uses_plain_headings(self) -> None:
        text = render(load_case(CASE), "zh")
        for heading in ("## 前提", "## 必须成立的条件", "## 反面证据", "## 必须成立的推论"):
            self.assertIn(heading, text)
        self.assertIn("未检验", text)
        self.assertNotIn("ceteris paribus", text)
        self.assertNotIn("## 适用条件", text)

    def test_report_does_not_print_raw_engine_flags(self) -> None:
        text = render(load_case(CASE), "zh")
        self.assertNotIn("blocking gap registered", text)
        self.assertNotIn("已登记阻塞性缺口", text)  # flags are no longer an output channel

    def test_report_verdict_explanation_matches_the_terms_module(self) -> None:
        text = render(load_case(CASE), "zh")
        self.assertIn(terms.status_explanation("UNTESTED", "zh"), text)

    def test_report_uses_the_authors_own_statements(self) -> None:
        text = render(load_case(CASE), "zh")
        cp_statement = terms.statement_of(load_case(CASE), "cp", "CP1")
        self.assertTrue(cp_statement)
        self.assertIn(cp_statement, text)


class JudgementTest(unittest.TestCase):
    def test_judgment_paragraph_opens_the_report_and_is_audited(self) -> None:
        judgment = "  该主张目前无法判定。\n\n  四项条件尚未检验。  "
        text = render(load_case(CASE), "zh", judgment=judgment)
        digest = hashlib.sha256(terms.normalize_judgment(judgment).encode("utf-8")).hexdigest()
        self.assertIn("## 评述", text)
        self.assertLess(text.index("## 评述"), text.index("## 为什么是这个结论"))
        self.assertIn(f"sha256：{digest}", text)
        self.assertIn("四项条件尚未检验。", text)
        self.assertNotIn("评述：未提供", text)

    def test_report_without_judgment_says_so(self) -> None:
        text = render(load_case(CASE))
        self.assertIn("commentary: not provided", text)

    def test_cli_report_accepts_a_judgment_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "south-atlantic"
            shutil.copytree(CASE, case_dir)
            judgment = Path(tmp) / "judgment.md"
            judgment.write_text("该主张目前无法判定。", encoding="utf-8")
            target = Path(tmp) / "report.md"
            with contextlib.redirect_stdout(io.StringIO()):
                code = cli.main(
                    [
                        "report",
                        str(case_dir),
                        "--format",
                        "md",
                        "--judgment-file",
                        str(judgment),
                        "--out",
                        str(target),
                    ]
                )
            self.assertEqual(code, 0)
            text = target.read_text(encoding="utf-8")
            self.assertIn("## Commentary", text)
            self.assertIn("该主张目前无法判定。", text)

    def test_brief_can_carry_the_judgment(self) -> None:
        judgment = "第一段判断。\n\n第二段判断。"
        text = render(load_case(CASE), "en", brief=True, judgment=judgment)
        digest = hashlib.sha256(terms.normalize_judgment(judgment).encode("utf-8")).hexdigest()
        self.assertIn("## Commentary", text)
        self.assertIn(f"sha256: {digest}", text)
        self.assertIn("## Essentials", text)

    def test_cli_report_rejects_two_judgment_sources(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(
                ["report", str(CASE), "--format", "md", "--judgment", "a", "--judgment-file", "b.md"]
            )
        self.assertEqual(code, 2)


class PlainSemanticsTest(unittest.TestCase):
    def test_decisive_table_localises_power(self) -> None:
        text = render(load_case(CASE), "zh")
        self.assertIn("| 高 |", text)
        self.assertNotIn("| high |", text)

    def test_decided_report_does_not_claim_rows_that_keep_the_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "south-atlantic"
            shutil.copytree(CASE, case_dir)
            import yaml

            argument = yaml.safe_load((case_dir / "argument.yaml").read_text(encoding="utf-8"))
            argument["inference"]["defeaters"][0]["state"] = "established"
            (case_dir / "argument.yaml").write_text(
                yaml.safe_dump(argument, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            text = render(load_case(case_dir), "zh")
        self.assertIn("结论已经被推翻。", text)
        self.assertNotIn("如果 D1", text)

    def test_derived_premise_is_labelled_as_another_argument(self) -> None:
        case = load_case(CASE)
        case.argument["premises"].append(
            {
                "id": "P4",
                "statement": "另一条论证已经确立了这一点。",
                "kind": "derived",
                "argument_ref": "arg.other",
            }
        )
        text = render(case, "zh")
        self.assertIn("结论来自另一条论证", text)


class BriefReportTest(unittest.TestCase):
    def test_brief_is_one_page_markdown(self) -> None:
        text = render(load_case(CASE), brief=True)
        self.assertTrue(text.startswith("# GeoArg brief:"))
        self.assertIn("## Essentials", text)
        self.assertIn("Quotes matching the source", text)
        self.assertNotIn("## Premises", text)
        self.assertNotIn("--full", text)
        self.assertIn("geoarg report <case>", text)

    def test_full_report_keeps_the_tables(self) -> None:
        text = render(load_case(CASE))
        self.assertIn("## Premises", text)
        self.assertIn("| P1 ", text)

    def test_cli_defaults_to_full_and_brief_flag_shortens_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "south-atlantic"
            shutil.copytree(CASE, case_dir)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main(["report", str(case_dir), "--format", "md"]), 0)
            self.assertIn("## Premises", out.getvalue())
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main(["report", str(case_dir), "--format", "md", "--brief"]), 0)
            self.assertIn("## Essentials", out.getvalue())
            self.assertNotIn("## Premises", out.getvalue())


if __name__ == "__main__":
    unittest.main()
