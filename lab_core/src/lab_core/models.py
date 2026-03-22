from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Plan:
    mode: str
    title: str
    rationale: str
    expected_signal: str
    public_updates: list[str]
    adapter: str
    logging_focus: list[str] = field(default_factory=list)
    idea_source: Any = None
    idea_id: Any = None
    track: str = "mac_mini_official_like"


@dataclass
class Evaluation:
    score: float
    runtime_seconds: float
    passed: bool
    artifact_stats: dict[str, Any]
    needs_validation: bool
    higher_is_better: bool = True


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
