"""Report rendering: one document model, Markdown and Word outputs."""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geoarg import cli  # noqa: E402
from geoarg.contract import load_case  # noqa: E402
from geoarg.report import build, render, render_docx  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CASE = REPO / "examples" / "south-atlantic"


class ReportModelTest(unittest.TestCase):
    def test_model_keeps_the_sections_the_audit_needs(self) -> None:
        model = build(load_case(CASE))
        headings = [section["heading"] for section in model["sections"]]
        for expected in ("Why this verdict", "Independence", "Grounding", "Decisive tests"):
            self.assertIn(expected, headings)
        meta = dict(model["meta"])
        self.assertEqual(meta["verdict"], "UNTESTED")

    def test_markdown_renders_from_the_same_model(self) -> None:
        text = render(load_case(CASE))
        self.assertTrue(text.startswith("# GeoArg report:"))
        self.assertIn("n_eff = 1.2", text)
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
        self.assertIn("## 判决理由", text)
        self.assertIn("## 前提", text)
        self.assertIn("## 决定性检验", text)
        self.assertIn("n_eff = 1.2", text)
        self.assertIn("| P1 ", text)


if __name__ == "__main__":
    unittest.main()
