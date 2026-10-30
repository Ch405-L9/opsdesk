"""Resume helper evidence: the user's approved facts, stored privately in the data dir.

evidence.yaml:
    items:
      - id: EV-001
        kind: skill            # skill | project | employment | training
        title: Python
        text: Built and maintain three production Flask apps.
        technologies: [Python, Flask]
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from opsdesk.paths import AppPaths

TIER = {"skill": 1.0, "project": 0.7, "employment": 0.5, "training": 0.3}
ALIASES = {
    "js": "javascript", "ts": "typescript", "py": "python", "k8s": "kubernetes", "postgres": "postgresql",
    "node": "node.js", "nodejs": "node.js", "react.js": "react", "reactjs": "react", "vue.js": "vue",
    "golang": "go", "ms excel": "excel", "gcp": "google cloud", "amazon web services": "aws",
}
EXAMPLE = """items:
  - id: EV-001
    kind: skill
    title: Python
    text: Write and maintain Python automation used every week by clients.
    technologies: [Python]
  - id: EV-002
    kind: project
    title: Small-business website rebuild
    text: Rebuilt a local business website; Lighthouse performance went from 41 to 96.
    technologies: [HTML, CSS, JavaScript, Lighthouse]
"""


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^EV-[A-Za-z0-9-]{1,20}$")
    kind: Literal["skill", "project", "employment", "training"]
    title: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=600)
    technologies: tuple[str, ...] = ()

    @field_validator("text")
    @classmethod
    def no_contact_data(cls, value: str) -> str:
        if re.search(r"[\w.+-]+@[\w-]+\.\w+|\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}", value):
            raise ValueError("evidence text must not contain email addresses or phone numbers")
        return value


def norm(term: str) -> str:
    t = re.sub(r"\s+", " ", term.strip().lower())
    return ALIASES.get(t, t)


def evidence_file(paths: AppPaths) -> Path:
    return paths.data_dir / "evidence.yaml"


def load(paths: AppPaths) -> list[EvidenceItem]:
    path = evidence_file(paths)
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        items = [EvidenceItem.model_validate(i) for i in raw.get("items", [])]
    except ValidationError as exc:
        raise ValueError(f"evidence.yaml is invalid: {exc}") from exc
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError("evidence.yaml has duplicate ids")
    return items


def init_file(paths: AppPaths) -> Path:
    path = evidence_file(paths)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(EXAMPLE, encoding="utf-8")
        path.chmod(0o600)
    return path


def index(items: list[EvidenceItem]) -> dict[str, list[EvidenceItem]]:
    out: dict[str, list[EvidenceItem]] = {}
    for item in items:
        terms = set(item.technologies) | ({item.title} if item.kind == "skill" else set())
        for term in terms:
            out.setdefault(norm(term), []).append(item)
    for key in out:
        out[key].sort(key=lambda i: -TIER[i.kind])
    return out
