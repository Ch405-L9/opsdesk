"""Tests for the API budget ledger - the thing that stops us blowing the free tier."""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from icp.budget import BudgetExceeded, BudgetLedger, ProviderQuota


@pytest.fixture
def ledger(tmp_path):
    quotas = {
        "brave": ProviderQuota(name="brave", monthly_limit=1000, unit="requests", env_key="BRAVE_API_KEY"),
        "hunter": ProviderQuota(name="hunter", monthly_limit=50, unit="credits", env_key="HUNTER_API_KEY"),
    }
    return BudgetLedger(state_path=tmp_path / "usage.json", quotas=quotas, spend_posture=0.5, month="2026-10")


def test_usable_budget_applies_spend_posture(ledger):
    # 50% posture on a 1000 request allowance
    assert ledger.usable("brave") == 500
    assert ledger.usable("hunter") == 25


def test_fresh_ledger_has_full_remaining(ledger):
    assert ledger.remaining("brave") == 500
    assert ledger.spent("brave") == 0


def test_spend_decrements_remaining(ledger):
    ledger.spend("brave", 3)
    assert ledger.spent("brave") == 3
    assert ledger.remaining("brave") == 497


def test_spend_persists_across_instances(ledger, tmp_path):
    ledger.spend("hunter", 4)
    reopened = BudgetLedger(state_path=tmp_path / "usage.json", quotas=ledger.quotas,
                            spend_posture=0.5, month="2026-10")
    assert reopened.spent("hunter") == 4
    assert reopened.remaining("hunter") == 21


def test_can_spend_is_false_at_the_ceiling(ledger):
    ledger.spend("hunter", 25)
    assert ledger.remaining("hunter") == 0
    assert ledger.can_spend("hunter") is False


def test_spend_past_ceiling_raises_and_does_not_record(ledger):
    ledger.spend("hunter", 24)
    with pytest.raises(BudgetExceeded) as exc:
        ledger.spend("hunter", 5)
    assert "hunter" in str(exc.value)
    # the refused call must not be counted
    assert ledger.spent("hunter") == 24


def test_budget_is_tracked_per_calendar_month(ledger, tmp_path):
    ledger.spend("brave", 100)
    next_month = BudgetLedger(state_path=tmp_path / "usage.json", quotas=ledger.quotas,
                              spend_posture=0.5, month="2026-11")
    assert next_month.spent("brave") == 0, "a new month must start from a clean allowance"
    # and the old month's record survives for auditing
    assert json.loads((tmp_path / "usage.json").read_text())["2026-10"]["brave"] == 100


def test_unknown_provider_is_rejected_loudly(ledger):
    with pytest.raises(KeyError):
        ledger.spend("clearbit", 1)


def test_full_posture_allows_entire_allowance(tmp_path):
    quotas = {"serpapi": ProviderQuota(name="serpapi", monthly_limit=100, unit="searches", env_key="SERPAPI_KEY")}
    full = BudgetLedger(state_path=tmp_path / "u.json", quotas=quotas, spend_posture=1.0, month="2026-10")
    assert full.usable("serpapi") == 100


def test_report_summarises_every_provider(ledger):
    ledger.spend("brave", 10)
    report = ledger.report()
    assert report["brave"]["spent"] == 10
    assert report["brave"]["remaining"] == 490
    assert report["brave"]["limit"] == 1000
    assert report["hunter"]["spent"] == 0
