"""Tests for deterministic SVG figures and their report/package wiring."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from geoarg import figstyle  # noqa: E402
from geoarg.cli import main  # noqa: E402
from geoarg.figures import MANIFEST_FILE, build_figures, load_figures  # noqa: E402

CASE = REPO / "examples" / "paper-demo"


def _run(argv: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(argv)
    return code, buffer.getvalue()


def _copy_case(tmp: Path) -> Path:
    dst = tmp / "case"
    shutil.copytree(CASE, dst)
    return dst


class FigureBuildTests(unittest.TestCase):
    def test_builds_four_deterministic_svgs(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            first = build_figures(CASE, tmp / "a", lang="en")
            second = build_figures(CASE, tmp / "b", lang="en")
            self.assertEqual(first["schema_version"], "geoarg/figures/0.1")
            self.assertEqual(len(first["figures"]), 4)
            hashes = [entry["sha256"] for entry in first["figures"]]
            self.assertEqual(hashes, [entry["sha256"] for entry in second["figures"]])
            for entry in first["figures"]:
                path = tmp / "a" / entry["file"]
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("<svg xmlns="))
                self.assertIn("<title>", text)
                self.assertIn("mm\"", text)
                self.assertNotIn('font-family=\"\"', text)
                self.assertIn("&quot;Helvetica Neue&quot;", text)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])

    def test_figures_use_landed_widths(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            build_figures(CASE, tmp, lang="en")
            status = (tmp / "argument-status.svg").read_text(encoding="utf-8")
            independence = (tmp / "independence.svg").read_text(encoding="utf-8")
            coverage = (tmp / "evidence-coverage.svg").read_text(encoding="utf-8")
            self.assertIn('width="180mm"', status)
            self.assertIn('width="88mm"', independence)
            self.assertIn('width="88mm"', coverage)

    def test_zh_titles(self):
        with tempfile.TemporaryDirectory() as raw:
            payload = build_figures(CASE, Path(raw), lang="zh")
            titles = [entry["title"] for entry in payload["figures"]]
            self.assertIn("论证状态", titles)


class FigureReportTests(unittest.TestCase):
    def test_report_html_embeds_figures(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            case = _copy_case(tmp)
            build_figures(case, case / "figures", lang="en")
            report = tmp / "report.html"
            code, _ = _run(["report", str(case), "--format", "html", "--out", str(report)])
            self.assertEqual(code, 0)
            text = report.read_text(encoding="utf-8")
            self.assertIn("Figures", text)
            self.assertEqual(text.count("<svg xmlns="), 4)

    def test_report_html_without_figures_has_no_svg(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            case = _copy_case(tmp)
            report = tmp / "plain.html"
            code, _ = _run(["report", str(case), "--format", "html", "--out", str(report)])
            self.assertEqual(code, 0)
            self.assertNotIn("<svg xmlns=", report.read_text(encoding="utf-8"))


class FigureCliTests(unittest.TestCase):
    def test_figures_cli_json(self):
        with tempfile.TemporaryDirectory() as raw:
            out = Path(raw) / "figs"
            code, stdout = _run(["figures", str(CASE), "--out", str(out), "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(stdout)
            self.assertEqual(len(payload["figures"]), 4)
            self.assertTrue((out / MANIFEST_FILE).is_file())

    def test_missing_case_returns_two(self):
        with tempfile.TemporaryDirectory() as raw:
            code, _ = _run(["figures", str(Path(raw) / "nope"), "--out", str(Path(raw) / "out")])
            self.assertEqual(code, 2)


class FigureStyleTests(unittest.TestCase):
    def test_grayscale_conflicts_for_similar_tones(self):
        conflicts = figstyle.grayscale_conflicts({"a": "#777777", "b": "#767676"})
        self.assertEqual(len(conflicts), 1)
        self.assertEqual({conflicts[0]["a"], conflicts[0]["b"]}, {"a", "b"})

    def test_palette_report_reports_contrast(self):
        report = figstyle.palette_report(figstyle.VERDICT_COLORS)
        self.assertEqual(len(report["colors"]), 5)
        self.assertIsNotNone(report["min_contrast"])

    def test_minimum_landed_font(self):
        self.assertEqual(figstyle.check_font(7.0), 7.0)
        with self.assertRaises(ValueError):
            figstyle.check_font(4.0)


class FigureLoadTests(unittest.TestCase):
    def test_load_absent_dir(self):
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(load_figures(Path(raw) / "missing"), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
