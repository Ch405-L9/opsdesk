"""Risk flag detection (signatures only).

The flag set is closed: exactly the 24 flags in PROJECT_GUARDRAILS.md. No flag may be
invented. The compensation band 86,000-89,999 raises no flag and does not reuse
SALARY_CONFLICT (A-2).
"""

from vetted.core.config.schema import RiskFlagConfig
from vetted.core.domain.assessment import RiskFlagFinding
from vetted.core.domain.candidate import CandidateDossier
from vetted.core.domain.job import NormalizedJob

__all__ = ["detect_risk_flags"]


def detect_risk_flags(
    job: NormalizedJob,
    dossier: CandidateDossier,
    config: RiskFlagConfig,
) -> tuple[RiskFlagFinding, ...]:
    """Return every risk flag raised by this listing, each with its rationale."""
    raise NotImplementedError(
        "Risk flag detection is Phase 3 work and is not approved. Detection patterns are "
        "deliberately absent from config/risk_flags.yaml."
    )
