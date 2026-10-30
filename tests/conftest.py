from __future__ import annotations

import pytest

from opsdesk.db import migrate
from opsdesk.paths import AppPaths, ensure_directories
from opsdesk.profile import BusinessProfile, SalaryTargets, save_profile


@pytest.fixture
def paths(tmp_path, monkeypatch) -> AppPaths:
    monkeypatch.setenv("OPSDESK_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("OPSDESK_DATA_DIR", str(tmp_path / "data"))
    for var in ("GOOGLE_PLACES_API_KEY", "PAGESPEED_API_KEY", "SAM_GOV_API_KEY", "HUNTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    p = ensure_directories(AppPaths(tmp_path / "cfg", tmp_path / "data"))
    save_profile(BusinessProfile(business_name="Acme Web", owner_name="Sam Lee", home_city="Springfield",
                                 home_state="IL", naics_codes=["541511"], salary_targets=SalaryTargets(minimum=60000)),
                 p.profile_file)
    migrate(p.database_file)
    return p
