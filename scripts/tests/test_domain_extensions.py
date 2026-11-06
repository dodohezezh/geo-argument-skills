"""Domain-pack extension points and workspace drift reporting (YDIH pilot findings)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from geoarg import audit, chain, contract, domains, schemas

REPO = Path(__file__).resolve().parents[2]
PACK = {
    "schema_version": "geoarg/domain/0.1",
    "name": "quaternary-geology",
    "enums": {
        "domains": ["quaternary-geology"],
        "profiles": ["quaternary-geology"],
    },
}


class PackProfileTests(unittest.TestCase):
    def _case(self, tmp: Path) -> Path:
        dst = tmp / "case"
        shutil.copytree(REPO / "examples" / "workspace-demo" / "basement-age", dst)
        (dst / "domain.yaml").write_text(yaml.safe_dump(PACK, sort_keys=False), encoding="utf-8")
        arg = yaml.safe_load((dst / "argument.yaml").read_text(encoding="utf-8"))
        arg["domain"] = "quaternary-geology"
        arg["profile"]["primary"] = "quaternary-geology"
        (dst / "argument.yaml").write_text(yaml.safe_dump(arg, sort_keys=False), encoding="utf-8")
        return dst

    def test_pack_extends_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_root = self._case(Path(tmp))
            case = contract.load_case(case_root)
            self.assertIsNotNone(case.domain_pack)
            self.assertEqual(contract.validate(case), [])

    def test_shipped_schemas_accept_pack_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_root = self._case(Path(tmp))
            case = contract.load_case(case_root)
            schemas.validate_instance(case.argument, "argument")
            schemas.validate_instance(case.evidence, "evidence")
            schemas.validate_instance(case.tests, "test")

    def test_pack_digest_covers_enums(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_root = self._case(Path(tmp))
            first = domains.domain_digest(case_root)["sha256"]
            pack = yaml.safe_load((case_root / "domain.yaml").read_text(encoding="utf-8"))
            pack["enums"]["profiles"].append("glacial-geology")
            (case_root / "domain.yaml").write_text(yaml.safe_dump(pack, sort_keys=False), encoding="utf-8")
            second = domains.domain_digest(case_root)["sha256"]
            self.assertNotEqual(first, second)


class WorkspaceDriftTests(unittest.TestCase):
    def test_drift_section_reports_a_committed_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_root = Path(tmp) / "case"
            shutil.copytree(REPO / "examples" / "workspace-demo" / "basement-age", case_root)
            audit.commit(case_root)
            report = chain.workspace_report(Path(tmp))
            self.assertEqual(len(report["drift"]), 1)
            self.assertTrue(report["drift"][0]["ok"], report["drift"][0])
            text = chain.render_workspace(report, "en")
            self.assertIn("Committed-record drift", text)
            self.assertIn("OK", text)

    def test_drift_section_flags_an_edited_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_root = Path(tmp) / "case"
            shutil.copytree(REPO / "examples" / "workspace-demo" / "basement-age", case_root)
            audit.commit(case_root)
            evidence_path = case_root / "evidence.yaml"
            evidence = yaml.safe_load(evidence_path.read_text(encoding="utf-8"))
            evidence["records"][0]["statement"] += " (edited after commit)"
            evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8")
            report = chain.workspace_report(Path(tmp))
            self.assertEqual(len(report["drift"]), 1)
            self.assertFalse(report["drift"][0]["ok"])
            self.assertFalse(report["ok"])
            text = chain.render_workspace(report, "en")
            self.assertIn("MISMATCH", text)

    def test_uncommitted_workspace_has_no_drift_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_root = Path(tmp) / "case"
            shutil.copytree(REPO / "examples" / "workspace-demo" / "basement-age", case_root)
            report = chain.workspace_report(Path(tmp))
            self.assertEqual(report["drift"], [])
            self.assertIn("No committed cases", chain.render_workspace(report, "en"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
