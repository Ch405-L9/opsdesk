import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from badgr_funding import bidfetch, bids

TODAY = dt.date(2026, 10, 22)


def row(gid, amount, end, sub="Agency A", rec="Acme LLC"):
    # Synthetic rows shaped like USAspending spending_by_award results.
    return {"generated_internal_id": gid, "Award ID": gid, "Recipient Name": rec, "Award Amount": amount,
            "Awarding Agency": "Dept X", "Awarding Sub Agency": sub, "Start Date": "2025-01-01",
            "End Date": end, "NAICS": {"code": "541511", "description": "x"}}


class MergeTests(unittest.TestCase):
    def test_dedupe_keeps_most_specific_tag(self):
        a = bids.merge([("any", [row("1", 100, "2027-03-01")]), ("sb_set_aside", [row("1", 100, "2027-03-01")])])
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["tag"], "sb_set_aside")
        b = bids.merge([("sb_set_aside", [row("2", 5, "2027-01-01")]), ("cert_required", [row("2", 5, "2027-01-01")])])
        self.assertEqual(b[0]["tag"], "cert_required")

    def test_rows_without_id_are_skipped(self):
        r = row("", 1, "2027-01-01")
        r["Award ID"] = None
        self.assertEqual(bids.merge([("any", [r])]), [])


class LaneAndFitTests(unittest.TestCase):
    def test_cert_set_aside_is_blocked_and_scores_zero(self):
        a = bids.merge([("cert_required", [row("1", 50_000, "2027-03-01")])])[0]
        self.assertEqual(bids.lane(a), "blocked")
        self.assertEqual(bids.fit(a, {}, TODAY)[0], 0)

    def test_large_award_is_subcontract_lane(self):
        a = bids.merge([("sb_set_aside", [row("1", 5_000_000, "2027-03-01")])])[0]
        self.assertEqual(bids.lane(a), "subcontract")

    def test_small_set_aside_in_recompete_window_ranks_above_open_large(self):
        good = bids.merge([("sb_set_aside", [row("1", 120_000, "2027-04-01")])])[0]
        meh = bids.merge([("any", [row("2", 900_000, "2029-01-01")])])[0]
        self.assertGreater(bids.fit(good, {}, TODAY)[0], bids.fit(meh, {}, TODAY)[0])

    def test_deadline_windows(self):
        soon = bids.merge([("any", [row("1", 1, "2026-11-15")])])[0]
        _, why = bids.fit(soon, {}, TODAY)
        self.assertTrue(any("re-solicited" in w for w in why))
        window = bids.merge([("any", [row("2", 1, "2027-06-01")])])[0]
        self.assertTrue(any("recompete prep" in w for w in bids.fit(window, {}, TODAY)[1]))

    def test_score_capped_and_never_called_odds(self):
        a = bids.merge([("sb_set_aside", [row("1", 10_000, "2027-03-01")])])[0]
        score, why = bids.fit(a, {"Agency A": 9}, TODAY)
        self.assertLessEqual(score, 100)
        self.assertFalse(any("chance" in w or "probab" in w for w in why))


class ReportTests(unittest.TestCase):
    def test_report_excludes_ended_and_lists_blocked_separately(self):
        awards = bids.merge([("any", [row("1", 1000, "2025-01-01"), row("2", 2000, "2027-05-01")]),
                             ("cert_required", [row("3", 3000, "2027-05-01")])])
        text = bids.report(awards, ["synthetic"], TODAY)
        self.assertNotIn("| 2025-01-01 |", text)
        self.assertIn("Blocked: certification set-asides (1 active)", text)
        self.assertIn("not a chance of winning", text)

    def test_load_cache_uses_newest_file_per_tag(self):
        with tempfile.TemporaryDirectory() as d:
            for stamp, n in (("20261001T000000", 1), ("20261022T000000", 2)):
                doc = {"tag": "any", "source_url": "u", "fetched_at": stamp, "results": [row(str(i), 1, "2027-01-01") for i in range(n)]}
                Path(d, f"usaspending_{stamp}_any.json").write_text(json.dumps(doc))
            batches, prov = bids.load_cache(d)
            self.assertEqual(len(batches[0][1]), 2)
            self.assertIn("20261022", prov[0])


class FetchTests(unittest.TestCase):
    def test_request_body_filters(self):
        b = bidfetch.request_body("sb_set_aside", "2023-10-22", "2026-10-22", 1)
        self.assertEqual(b["filters"]["set_aside_type_codes"], list(bids.SB_SET_ASIDE))
        self.assertNotIn("set_aside_type_codes", bidfetch.request_body("any", "a", "b", 1)["filters"])

    def test_fetch_paginates_with_stub_and_no_network(self):
        pages = [{"results": [row("1", 1, "2027-01-01")], "page_metadata": {"hasNext": True}},
                 {"results": [row("2", 1, "2027-01-01")], "page_metadata": {"hasNext": False}}]
        calls = []
        rows, n = bidfetch.fetch("any", "a", "b", post=lambda body: calls.append(body) or pages[len(calls) - 1], pause=0)
        self.assertEqual(len(rows), 2)
        self.assertEqual([c["page"] for c in calls], [1, 2])

    def test_fetch_requires_explicit_flag(self):
        with self.assertRaises(SystemExit):
            bidfetch.main(["usaspending"])


if __name__ == "__main__":
    unittest.main()
