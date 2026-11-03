"""Tests for the self-contained HTML report and workspace page."""

from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml

from geoarg import attest, report as report_mod
from geoarg.chain import workspace_report
from geoarg.contract import load_case
from geoarg.html import render_html, render_workspace_html

REPO = Path(__file__).resolve().parents[2]
PAPER = REPO / "examples" / "paper-demo"
WORKSPACE = REPO / "examples" / "workspace-demo"


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    from geoarg.cli import main

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class ReportHtmlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-html-"))
        self.case = self.tmp / "paper"
        shutil.copytree(PAPER, self.case, ignore=shutil.ignore_patterns(".geoarg"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_report_html_is_self_contained_and_collapsible(self) -> None:
        model = report_mod.build(load_case(self.case), "zh")
        text = render_html(model, "zh")
        self.assertTrue(text.startswith("<!doctype html>"), text[:40])
        self.assertIn('<meta charset="utf-8">', text)
        self.assertIn("@media print", text)
        self.assertIn("<details open>", text)
        self.assertIn("为什么是这个结论", text)
        self.assertIn('class="table-wrap"', text)
        self.assertNotIn("<script", text.lower())

    def test_report_html_uses_english_headings(self) -> None:
        model = report_mod.build(load_case(self.case), "en")
        text = render_html(model, "en")
        self.assertIn("Why this conclusion", text)
        self.assertIn('lang="en"', text)

    def test_report_html_escapes_authored_text(self) -> None:
        path = self.case / "argument.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["claim"]["statement"] = '<script>alert("x")</script>'
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        text = render_html(report_mod.build(load_case(self.case), "zh"), "zh")
        self.assertIn("&lt;script&gt;", text)
        self.assertNotIn("<script>alert", text)

    def test_report_cli_writes_html_default_target(self) -> None:
        code, out, err = run_cli(["report", str(self.case), "--format", "html", "--lang", "zh"])
        self.assertEqual(code, 0, err)
        target = self.case / "report.html"
        self.assertTrue(target.exists())
        self.assertIn("wrote", out)
        text = target.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("<!doctype html>"))

    def test_report_cli_writes_explicit_out_and_brief(self) -> None:
        target = self.tmp / "brief.html"
        code, _, err = run_cli(
            ["report", str(self.case), "--format", "html", "--brief", "--out", str(target)]
        )
        self.assertEqual(code, 0, err)
        self.assertTrue(target.exists())
        self.assertIn("brief", target.read_text(encoding="utf-8").lower())


class WorkspaceHtmlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-ws-html-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_workspace_html_contains_the_audit_sections(self) -> None:
        payload = workspace_report(WORKSPACE)
        text = render_workspace_html(payload, "en")
        self.assertTrue(text.startswith("<!doctype html>"))
        self.assertIn("Argument chains", text)
        self.assertIn("basement-age", text)
        self.assertIn("<table>", text)
        zh = render_workspace_html(payload, "zh")
        self.assertIn("论证链", zh)
        self.assertIn('lang="zh-CN"', zh)

    def test_workspace_cli_writes_html(self) -> None:
        target = self.tmp / "workspace.html"
        code, out, err = run_cli(
            ["workspace", str(WORKSPACE), "--format", "html", "--out", str(target)]
        )
        self.assertEqual(code, 0, err)
        self.assertTrue(target.exists())
        self.assertIn("wrote", out)
        self.assertIn("<details open>", target.read_text(encoding="utf-8"))


class AttestPatternTests(unittest.TestCase):
    def test_html_report_is_in_the_default_binding_set(self) -> None:
        self.assertIn("report.html", attest.DEFAULT_PATTERNS)
        self.assertIn("report.*.html", attest.DEFAULT_PATTERNS)


if __name__ == "__main__":
    unittest.main()
