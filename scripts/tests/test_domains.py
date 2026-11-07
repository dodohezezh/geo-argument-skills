"""Domain packs: discovery, widening, digest, and the domains CLI."""

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from geoarg import audit, domains
from geoarg.cli import main
from geoarg.contract import ContractError, load_case, validate

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"
DOMAIN_DEMO = EXAMPLES / "domain-demo"


def canonical(path):
    """A comparison key that ignores Windows 8.3 short-name aliases.

    ``tempfile.gettempdir()`` can return the short ``RUNNER~1`` form on Windows
    CI runners, while ``Path.resolve`` expands it to the long form. Comparing
    the canonical paths keeps the test about pack discovery, not about which
    spelling of the same directory the platform happened to hand us.
    """
    return os.path.normcase(os.path.realpath(str(path)))


class DomainPackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-domain-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.case = self.tmp / "case"
        shutil.copytree(DOMAIN_DEMO, self.case)
        shutil.rmtree(self.case / ".geoarg", ignore_errors=True)

    def test_builtin_enums_are_unchanged(self):
        effective = domains.effective_enums(None)
        self.assertIn("plate-tectonics", effective["domains"])
        self.assertNotIn("age-model", effective["claim_kinds"])
        self.assertNotIn("tephrochronology", effective["method_types"])

    def test_pack_widens_effective_enums(self):
        pack = domains.load_domain(self.case)
        self.assertIsNotNone(pack)
        self.assertEqual(pack["name"], "quaternary")
        effective = domains.effective_enums(pack)
        self.assertIn("quaternary-geology", effective["domains"])
        self.assertIn("age-model", effective["claim_kinds"])
        self.assertIn("tephrochronology", effective["method_types"])
        self.assertEqual(validate(load_case(self.case)), [])

    def test_without_the_pack_the_case_is_rejected(self):
        (self.case / "domain.yaml").unlink()
        problems = validate(load_case(self.case))
        self.assertTrue(
            any("unknown domain" in problem for problem in problems),
            problems,
        )

    def test_nearest_parent_pack_is_found(self):
        pack_file = self.case / "domain.yaml"
        pack_file.rename(self.tmp / "domain.yaml")
        pack = domains.load_domain(self.case)
        self.assertIsNotNone(pack)
        self.assertEqual(canonical(pack["path"]), canonical(self.tmp / "domain.yaml"))

    def test_unknown_enum_key_is_rejected(self):
        (self.case / "domain.yaml").write_text(
            "schema_version: geoarg/domain/0.1\n"
            "name: bad\n"
            "enums:\n"
            "  colors: [red]\n",
            encoding="utf-8",
        )
        with self.assertRaises(ContractError) as raised:
            domains.load_domain(self.case)
        self.assertIn("cannot extend", str(raised.exception))

    def test_missing_env_override_is_rejected(self):
        previous = os.environ.get("GEOARG_DOMAIN_FILE")
        os.environ["GEOARG_DOMAIN_FILE"] = str(self.tmp / "missing.yaml")
        self.addCleanup(
            lambda: os.environ.__setitem__("GEOARG_DOMAIN_FILE", previous)
            if previous is not None
            else os.environ.pop("GEOARG_DOMAIN_FILE", None)
        )
        with self.assertRaises(ContractError) as raised:
            domains.load_domain(self.case)
        self.assertIn("GEOARG_DOMAIN_FILE", str(raised.exception))

    def test_commit_records_the_pack_and_verify_detects_a_change(self):
        record, path = audit.commit(self.case)
        self.assertEqual(record["domain"]["name"], "quaternary")
        stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(stored["domain"]["sha256"], record["domain"]["sha256"])
        ok, problems, _ = audit.verify(self.case)
        self.assertTrue(ok, problems)
        pack_file = self.case / "domain.yaml"
        pack_file.write_text(
            pack_file.read_text(encoding="utf-8").replace(
                "  - tephrochronology\n",
                "  - tephrochronology\n  - lithostratigraphy\n",
            ),
            encoding="utf-8",
        )
        ok, problems, _ = audit.verify(self.case)
        self.assertFalse(ok)
        self.assertTrue(
            any("domain pack changed since commit" in problem for problem in problems),
            problems,
        )

    def test_cli_lists_the_effective_pack(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["domains", str(self.case), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["pack"]["name"], "quaternary")
        self.assertIn("quaternary-geology", payload["effective"]["domains"])
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["domains", str(self.case)])
        self.assertEqual(code, 0)
        self.assertIn("quaternary", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
