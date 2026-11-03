"""Form editor: page rendering, form merging, and the local HTTP round trip."""

import shutil
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from geoarg.contract import load_case, validate
from geoarg.editor import apply_form, model, render_page, serve

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "examples" / "workspace-demo" / "basement-age"


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="geoarg-editor-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.case = self.tmp / "case"
        shutil.copytree(SOURCE, self.case)
        shutil.rmtree(self.case / ".geoarg", ignore_errors=True)

    def _post(self, url, token, fields=None):
        payload = {"_token": token}
        payload.update(fields or {})
        request = urllib.request.Request(
            url + "edit",
            data=urllib.parse.urlencode(payload).encode("utf-8"),
            method="POST",
        )
        return urllib.request.urlopen(request, timeout=5)

    def test_page_contains_the_form(self):
        page = render_page(self.case, "page-token")
        for needle in (
            "claim.statement",
            "premises.0.id",
            "evidence.1.id",
            "tests.1.id",
            'name="domain"',
            'name="_token"',
            "Save and validate",
        ):
            self.assertIn(needle, page)
        self.assertEqual(model(self.case)["problems"], [])

    def test_apply_form_updates_claim_and_keeps_other_rows(self):
        problems = apply_form(self.case, {"claim.statement": ["A different claim."]})
        self.assertEqual(problems, [])
        case = load_case(self.case)
        self.assertEqual(case.argument["claim"]["statement"], "A different claim.")
        self.assertEqual(len(case.argument["premises"]), 1)
        self.assertEqual(len(case.tests["records"]), 1)

    def test_blank_rows_are_dropped(self):
        form = {
            "premises.0.id": ["P1"],
            "premises.0.statement": ["Edited premise."],
            "premises.0.kind": ["evidenced"],
            "premises.0.status": ["supported"],
            "premises.0.layer": ["L1"],
            "premises.0.evidence_refs": ["ev.zircon.age"],
            "premises.0.argument_ref": [""],
            "premises.1.id": [""],
        }
        problems = apply_form(self.case, form)
        self.assertEqual(problems, [])
        case = load_case(self.case)
        self.assertEqual(len(case.argument["premises"]), 1)
        self.assertEqual(case.argument["premises"][0]["statement"], "Edited premise.")
        self.assertEqual(validate(case), [])

    def test_http_round_trip(self):
        httpd, thread, url = serve(self.case, token="http-token")
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                body = response.read().decode("utf-8")
            self.assertIn("geoarg edit", body)
            with self._post(
                url, "http-token", {"claim.statement": "Edited over HTTP."}
            ) as response:
                html = response.read().decode("utf-8")
            self.assertIn("Edited over HTTP.", html)
            self.assertEqual(
                load_case(self.case).argument["claim"]["statement"],
                "Edited over HTTP.",
            )
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self._post(url, "wrong-token")
            self.assertEqual(raised.exception.code, 403)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
