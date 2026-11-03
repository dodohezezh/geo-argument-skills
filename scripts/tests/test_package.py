"""Tests for portable evidence packages (geoarg package / verify-package)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from geoarg.cli import main
from geoarg.contract import ContractError, load_case
from geoarg.judge import judge
from geoarg.package import (
    MANIFEST_FILE,
    PACKAGE_SCHEMA_VERSION,
    RO_CRATE_FILE,
    build_package,
    verify_package,
)
from geoarg.scaffold import new_case


def make_case(tmp: Path, *, attested: bool = True) -> Path:
    root = tmp / "case"
    new_case(
        root,
        "stratigraphy-sequence-boundary",
        case_id="pkg.demo",
        title="Packaging demo",
        claim="A flooding surface is a 12.3 Ma sequence boundary.",
    )
    (root / "report.md").write_text("# Report\n\nA demo deliverable for packaging.\n", encoding="utf-8")
    assert main(["commit", str(root)]) == 0
    if attested:
        assert main(["attest", str(root), "--include", "report.md"]) == 0
        assert main(["anchor", str(root)]) == 0
    return root


class PackageTests(unittest.TestCase):
    def test_package_roundtrip_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            case_root = make_case(tmp_path)
            out = tmp_path / "package"
            manifest = build_package(case_root, out, lang="en")
            self.assertEqual(manifest["schema_version"], PACKAGE_SCHEMA_VERSION)
            self.assertEqual(manifest["verdict"], "UNTESTED")
            roles = {entry["role"] for entry in manifest["files"]}
            for role in ("contract", "deliverable", "report", "record", "ledger", "attestation", "anchor"):
                self.assertIn(role, roles)
            self.assertTrue((out / MANIFEST_FILE).is_file())
            self.assertTrue((out / RO_CRATE_FILE).is_file())
            self.assertTrue((out / "README.md").is_file())
            ro_crate = json.loads((out / RO_CRATE_FILE).read_text(encoding="utf-8-sig"))
            ids = {node.get("@id") for node in ro_crate["@graph"]}
            self.assertIn("./", ids)
            dataset = next(node for node in ro_crate["@graph"] if node.get("@id") == "./")
            parts = {part.get("@id") for part in dataset["hasPart"]}
            self.assertIn("manifest.json", parts)
            package_case = load_case(out)
            self.assertEqual(judge(package_case)["verdict"], manifest["verdict"])
            report = verify_package(out)
            self.assertTrue(report["ok"], report["problems"])

    def test_edited_deliverable_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            case_root = make_case(tmp_path)
            out = tmp_path / "package"
            manifest = build_package(case_root, out)
            deliverable = out / manifest["attestation"]["deliverables"][0]["package_path"]
            deliverable.write_text("edited after packaging\n", encoding="utf-8")
            report = verify_package(out)
            self.assertFalse(report["ok"])
            self.assertTrue(any("attested deliverable changed" in problem for problem in report["problems"]))

    def test_edited_ledger_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            case_root = make_case(tmp_path)
            out = tmp_path / "package"
            build_package(case_root, out)
            ledger = out / ".geoarg" / "ledger.jsonl"
            lines = ledger.read_text(encoding="utf-8").splitlines()
            first = json.loads(lines[0])
            first["record_sha256"] = "0" * 64
            lines[0] = json.dumps(first)
            ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
            report = verify_package(out)
            self.assertFalse(report["ok"])
            self.assertTrue(any("ledger" in problem for problem in report["problems"]))

    def test_commit_without_attestation_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            case_root = make_case(tmp_path, attested=False)
            with self.assertRaises(ContractError):
                build_package(case_root, tmp_path / "package")

    def test_cli_package_and_verify_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            case_root = make_case(tmp_path)
            out = tmp_path / "package"
            self.assertEqual(main(["package", str(case_root), "--out", str(out), "--json"]), 0)
            self.assertTrue((out / MANIFEST_FILE).is_file())
            self.assertEqual(main(["verify-package", str(out)]), 0)
            deliverable = next((out / "files" / "deliverables").iterdir())
            deliverable.write_text("tampered\n", encoding="utf-8")
            self.assertEqual(main(["verify-package", str(out)]), 1)


if __name__ == "__main__":
    unittest.main()
