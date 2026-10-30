import datetime as dt

from opsdesk.bids import fetch as fetchmod
from opsdesk.bids import service
from opsdesk.bids.rank import fit, lane, merge, normalize
from opsdesk.profile import load_profile, save_profile
from opsdesk.workbench import get_item, workbench
from opsdesk.workflow import set_fields

TODAY = dt.date(2026, 10, 30)


def raw(i, amount=100000, end="2027-06-01", sub="Navy", rec="Incumbent LLC", set_aside=""):
    return {"generated_internal_id": f"CONT_{i}", "Award ID": f"A{i}", "Recipient Name": rec, "Award Amount": amount,
            "Awarding Agency": "DoD", "Awarding Sub Agency": sub, "Start Date": "2025-01-01", "End Date": end,
            "NAICS": {"code": "541511"}, "Set Aside Type": set_aside}


def test_merge_prefers_most_specific_tag():
    awards = merge([("any", [raw(1), raw(2)]), ("sb_set_aside", [raw(1)])])
    by = {a["id"]: a for a in awards}
    assert by["CONT_1"]["tag"] == "sb_set_aside" and by["CONT_2"]["tag"] == "any"


def test_lanes_and_eligibility():
    cert = normalize(raw(3, set_aside="WOSB"), "cert_required")
    assert lane(cert) == "blocked"
    assert lane(cert, ["wosb"]) == "cert_eligible"
    assert lane(cert, ["8a"]) == "check_certification"
    assert lane(normalize(raw(4, amount=5_000_000), "any")) == "subcontract"


def test_fit_is_bounded_and_explained():
    award = normalize(raw(5, amount=10000, end="2027-06-01"), "sb_set_aside")
    score, why = fit(award, {"Navy": 6}, TODAY)
    assert 0 < score <= 100 and "small-business set-aside" in why and any("repeat buyer" in w for w in why)
    blocked, reason = fit(normalize(raw(6), "cert_required"), {}, TODAY)
    assert blocked == 0 and "UNKNOWN" in reason[0]


def test_request_body_uses_profile_values():
    body = fetchmod.request_body("sb_set_aside", "2024-01-01", "2026-10-30", 1, ["541519"], "tx")
    assert body["filters"]["naics_codes"] == {"require": ["541519"]}
    assert body["filters"]["place_of_performance_locations"][0]["state"] == "TX"
    assert "set_aside_type_codes" in body["filters"]
    assert "set_aside_type_codes" not in fetchmod.request_body("any", "a", "b", 1, ["1"], "")["filters"]


def test_fetch_sync_idempotent_and_keeps_your_status(paths):
    pages = {"sb_set_aside": [raw(1)], "cert_required": [raw(2, set_aside="8A")], "any": [raw(1), raw(3)]}

    def fake_post(body):
        tag = "sb_set_aside" if body["filters"].get("set_aside_type_codes", [""])[0] == "SBA" else (
            "cert_required" if body["filters"].get("set_aside_type_codes") else "any")
        return {"results": pages[tag], "page_metadata": {"hasNext": False}}

    counts = service.fetch(paths, 3, post=fake_post, pause=0)
    assert counts == {"sb_set_aside": 1, "cert_required": 1, "any": 2}
    with workbench(paths) as conn:
        set_fields(conn, "bid:usaspending:CONT_1", status="pursue")
    assert service.sync(paths)["unchanged"] == 3
    with workbench(paths) as conn:
        assert get_item(conn, "bid:usaspending:CONT_1")["status"] == "pursue"
    report = service.report(paths)
    assert "not a chance of winning" in report and "Navy" in report
    assert all(r["lane"] != "blocked" for r in service.ranked(paths))


def test_fetch_requires_naics(paths):
    profile = load_profile(paths.profile_file)
    save_profile(profile.model_copy(update={"naics_codes": []}), paths.profile_file)
    try:
        service.fetch(paths, post=lambda b: {}, pause=0)
    except ValueError as exc:
        assert "NAICS" in str(exc)
    else:
        raise AssertionError("expected ValueError")
