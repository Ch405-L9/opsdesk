"""Hard spending limits for metered APIs.

The free allowances on Brave, SerpApi and Hunter are small, change without
notice, and are reported inconsistently even by the vendors themselves. So no
limit is hardcoded here: every number comes from config that the operator fills
in from their own dashboard, and this ledger refuses the call that would cross
the line rather than discovering the overage on an invoice.

Usage is counted on *attempt*, not on success, because providers generally bill
a request that errors after it reached them. Counting optimistically is how you
end up over the line.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


class BudgetExceeded(RuntimeError):
    """Raised instead of making a call that would exceed the monthly allowance."""

@dataclass(frozen=True)
class ProviderQuota:
    name: str
    monthly_limit: int      # the provider's free allowance, as verified on their dashboard
    unit: str               # "requests", "searches", "credits" - for honest reporting
    env_key: str            # environment variable holding the API key
    note: str = ""          # provenance: where this limit came from and when

def current_month() -> str:
    return _dt.datetime.now().strftime("%Y-%m")

class BudgetLedger:
    """Tracks metered API usage per provider per calendar month."""

    def __init__(self, state_path, quotas: dict[str, ProviderQuota],
                 spend_posture: float = 0.5, month: str | None = None):
        self.state_path = Path(state_path)
        self.quotas = quotas
        self.spend_posture = spend_posture
        self.month = month or current_month()

    # ---- allowance arithmetic -------------------------------------------------

    def usable(self, provider: str) -> int:
        """The allowance we permit ourselves: the free limit times the posture."""
        quota = self.quotas[provider]
        return int(quota.monthly_limit * self.spend_posture)

    def spent(self, provider: str) -> int:
        if provider not in self.quotas:
            raise KeyError(f"Unconfigured provider: {provider!r}")
        return self._load().get(self.month, {}).get(provider, 0)

    def remaining(self, provider: str) -> int:
        return max(0, self.usable(provider) - self.spent(provider))

    def can_spend(self, provider: str, units: int = 1) -> bool:
        return self.remaining(provider) >= units

    def spend(self, provider: str, units: int = 1) -> int:
        """Record consumption, refusing to record anything that crosses the cap."""
        if provider not in self.quotas:
            raise KeyError(f"Unconfigured provider: {provider!r}")

        quota = self.quotas[provider]
        state = self._load()
        month_usage = state.setdefault(self.month, {})
        already = month_usage.get(provider, 0)

        if already + units > self.usable(provider):
            raise BudgetExceeded(
                f"{provider}: {already}+{units} {quota.unit} would exceed this month's "
                f"self-imposed cap of {self.usable(provider)} "
                f"({int(self.spend_posture * 100)}% of {quota.monthly_limit}). "
                f"Raise spend_posture or monthly_limit in config if the dashboard disagrees."
            )

        month_usage[provider] = already + units
        self._save(state)
        return month_usage[provider]

    # ---- reporting ------------------------------------------------------------

    def report(self) -> dict:
        return {
            name: {
                "limit": quota.monthly_limit,
                "usable": self.usable(name),
                "spent": self.spent(name),
                "remaining": self.remaining(name),
                "unit": quota.unit,
                "key_present": bool(os.environ.get(quota.env_key)),
            }
            for name, quota in self.quotas.items()
        }

    # ---- persistence ----------------------------------------------------------

    def _load(self) -> dict:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A corrupt ledger must not silently reset the budget to zero spent.
            raise RuntimeError(
                f"Usage ledger at {self.state_path} is unreadable. Refusing to proceed, "
                "because treating it as empty would restart the monthly allowance."
            )

    def _save(self, state: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replace so an interrupted write cannot lose the running total.
        fd, tmp = tempfile.mkstemp(dir=self.state_path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.state_path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

def load_quotas(config_path) -> tuple:
    """Read provider quotas and spend posture from JSON config."""
    data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    quotas = {
        name: ProviderQuota(
            name=name,
            monthly_limit=int(spec["monthly_limit"]),
            unit=spec.get("unit", "requests"),
            env_key=spec["env_key"],
            note=spec.get("note", ""),
        )
        for name, spec in data["providers"].items()
    }
    return quotas, float(data.get("spend_posture", 0.5))
