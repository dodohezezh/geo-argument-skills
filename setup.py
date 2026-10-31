"""Packaging hook: ship the skills inside the wheel.

Skills live at the repository root so agent plugin hosts can discover them.
``build_py`` copies that tree into the built package as ``geoarg/_skills`` so a
wheel install can run ``geoarg install-skills`` without the repository.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent


class BuildPyWithSkills(build_py):
    def run(self) -> None:
        super().run()
        target = Path(self.build_lib) / "geoarg" / "_skills"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(ROOT / "skills", target)


setup(cmdclass={"build_py": BuildPyWithSkills})
