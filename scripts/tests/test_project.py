"""Tests for the project installer, doctor, and packaged skills."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from geoarg import install

REPO = Path(__file__).resolve().parents[2]


class InstallTests(unittest.TestCase):
    def test_source_contains_the_two_skills(self):
        source = install.source_root(None)
        self.assertEqual([path.name for path in install.skill_dirs(source)], ["geo-arg-audit", "geo-arg-register"])

    def test_install_apply_and_check(self):
        source = install.source_root(None)
        with tempfile.TemporaryDirectory() as tmp:
            targets = [("dest", Path(tmp))]
            rows = install.apply(install.plan(source, targets))
            self.assertEqual(len(rows), 2)
            statuses = install.check(source, targets)
            self.assertTrue(all(row["status"] == "ok" for row in statuses))
            (Path(tmp) / "geo-arg-audit" / "SKILL.md").write_text("edited", encoding="utf-8")
            self.assertEqual(install.check(source, targets)[0]["status"], "modified")

    def test_missing_target_reports_missing(self):
        source = install.source_root(None)
        with tempfile.TemporaryDirectory() as tmp:
            rows = install.check(source, [("dest", Path(tmp))])
            self.assertTrue(all(row["status"] == "missing" for row in rows))

    def test_resolve_targets_honours_dest(self):
        with tempfile.TemporaryDirectory() as tmp:
            targets = install.resolve_targets([tmp])
            self.assertEqual(targets, [("dest", Path(tmp).resolve())])

    def test_engine_version_satisfies_the_skills(self):
        from geoarg import __version__

        self.assertGreaterEqual(install._version_tuple(__version__), install._version_tuple(install.REQUIRED_ENGINE))

    def test_environment_reports_required_checks(self):
        names = [check["name"] for check in install.environment()]
        for expected in ("engine", "python", "PyYAML", "pypdf", "python-docx", "skills source", "installed skills"):
            self.assertIn(expected, names)


class SkillHandshakeTests(unittest.TestCase):
    def test_both_skills_start_with_the_engine_check(self):
        for skill in ("geo-arg-register", "geo-arg-audit"):
            text = (REPO / "skills" / "geology" / skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("geoarg --version", text)


class PackagingTests(unittest.TestCase):
    def test_build_py_ships_skills_inside_the_package(self):
        try:
            import setuptools  # noqa: F401
        except ImportError:
            self.skipTest("setuptools is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp) / "lib"
            result = subprocess.run(
                [sys.executable, "setup.py", "build_py", "--build-lib", str(lib)],
                cwd=REPO,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr[-2000:])
            skill = lib / "geoarg" / "_skills" / "geology" / "geo-arg-register" / "SKILL.md"
            self.assertTrue(skill.is_file())
