from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Plan:
    mode: str
    title: str
    rationale: str
    expected_signal: str
    public_updates: list[str]
    adapter: str
    idea_source: Any = None


@dataclass
class Evaluation:
    score: float
    runtime_seconds: float
    passed: bool
    artifact_stats: dict[str, Any]
    needs_validation: bool


@dataclass
class RunResult:
    run_id: str
    started_at: str
    finished_at: str
    plan: Plan
    evaluation: Evaluation
    patch: str
    summary: str
    logs: list[str] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["plan"] = asdict(self.plan)
        data["evaluation"] = asdict(self.evaluation)
        return data
