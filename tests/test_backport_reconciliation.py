import unittest
from scripts.reconcile_backports import key_for, issue_body, audit_repo

class FakeClient:
    def __init__(self, candidates):
        self.candidates = candidates
    def pages(self, path, params=None, max_pages=20):
        if params.get("state") == "closed":
            yield {"number": 12, "html_url": "https://github.com/Aakvatech-Limited/demo/pull/12",
                   "merged_at": "2026-10-10T10:00:00Z", "updated_at": "2026-10-10T10:00:00Z",
                   "labels": [{"name": "backport-to-version-15-hotfix"},
                              {"name": "backport-to-version-16-hotfix"}]}
        else:
            yield from self.candidates.get(params.get("base"), [])

def backport(number, branch, merged=False):
    return {"number": number, "title": "[Backport " + branch + "] Fix",
            "body": "Backport of #12 to " + branch, "updated_at": "2026-10-11T10:00:00Z",
            "html_url": "https://github.com/Aakvatech-Limited/demo/pull/" + str(number),
            "state": "closed" if merged else "open",
            "merged_at": "2026-10-11T11:00:00Z" if merged else None}

class BackportReconciliationTests(unittest.TestCase):
    def audit(self, candidates):
        return audit_repo(FakeClient(candidates), "Aakvatech-Limited/demo",
                          "2026-10-01T00:00:00Z", "2026-10-13T00:00:00Z", set())
    def test_independent_branches(self):
        records = self.audit({"version-15-hotfix": [backport(34, "version-15-hotfix")],
                              "version-16-hotfix": [backport(35, "version-16-hotfix", True)]})
        self.assertEqual({r["branch"]: r["status"] for r in records},
                         {"version-15-hotfix": "awaiting_merge", "version-16-hotfix": "completed"})
    def test_absence_is_not_claimed_conflict(self):
        self.assertTrue(all(r["status"] == "unverified" for r in self.audit({})))
    def test_stable_issue_key(self):
        record = self.audit({})[0]
        self.assertIn("<!-- aakvatech-backport-exception:" + record["key"] + " -->", issue_body(record))
        self.assertEqual(key_for("a/b", 12, "v15"), "a/b#12@v15")

if __name__ == "__main__":
    unittest.main()
