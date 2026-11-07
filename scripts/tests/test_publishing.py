"""Publication gates: drafts cannot be committed and the shipped demo chain verifies."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from geoarg.cli import main
from geoarg.contract import load_case
from geoarg.draft import draft_markers
from geoarg.scaffold import new_case

REPO = Path(__file__).resolve().parents[2]


class DraftGateTests(unittest.TestCase):
    def test_clean_example_has_no_markers(self) -> None:
        self.assertEqual(draft_markers(load_case(REPO / "examples" / "paper-demo")), [])

    def test_scaffold_commit_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "draft-case"
            new_case(
                target,
                "geochronology-age-bracket",
                case_id="draft-case",
                title="Draft case",
                claim="A draft claim.",
            )
            self.assertTrue(draft_markers(load_case(target)))
            self.assertEqual(main(["check", str(target)]), 1)
            self.assertEqual(main(["check", str(target), "--profile", "draft"]), 0)
            self.assertEqual(main(["commit", str(target)]), 2)
            self.assertFalse((target / ".geoarg" / "registry").exists())


class DemoChainTests(unittest.TestCase):
    def test_paper_demo_demo_chain_verifies(self) -> None:
        self.assertEqual(main(["verify", str(REPO / "examples" / "demo-trust-chain")]), 0)


class PublishingDocsTests(unittest.TestCase):
    def test_quickstart_is_runnable(self) -> None:
        for name in ("README.md", "README.en.md"):
            text = (REPO / name).read_text(encoding="utf-8")
            self.assertNotIn("git clone <your-fork-url>", text)
            self.assertIn("geoarg verify examples/demo-trust-chain", text)

    def test_changelog_top_matches_version(self) -> None:
        from geoarg import __version__

        changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
        first = next(line for line in changelog.splitlines() if line.startswith("## "))
        self.assertTrue(first.startswith(f"## {__version__}"), first)
