from __future__ import annotations

from collections.abc import Sequence
import json
from typing import Optional

from .config import load_runtime
from .models import Plan
from .services.codex_wrapper import CodexWrapper
from .state_store import StateStore


MODES = ["explore", "exploit", "validate", "research", "community"]


class Planner:
    def __init__(self, store: StateStore) -> None:
        self.store = store
        self.runtime = load_runtime(store.paths)
        self.codex = CodexWrapper()

    def choose_mode(self) -> str:
        state = self.store.current_state()
        community = self.store.community_queue()
        best_score = self.store.best_runs().get("best_score")

        if community:
            return "community"
        if best_score is None:
            return "explore"
        if state.get("last_status") == "failed":
            return "validate"
        cycle = len(self.store.best_runs().get("runs", [])) % len(MODES)
        return MODES[cycle]

    def _community_idea(self) -> dict:
        queue = self.store.community_queue()
        return queue[0] if queue else {}

    def plan(self, research_notes: Sequence[dict]) -> Plan:
        codex_cfg = self.runtime.get("codex", {})
        if codex_cfg.get("enabled"):
            return self._codex_plan(research_notes, codex_cfg.get("model"))
        return self._heuristic_plan(research_notes)

    def _heuristic_plan(self, research_notes: Sequence[dict]) -> Plan:
        mode = self.choose_mode()
        idea = self._community_idea()

        title_map = {
            "explore": "Probe a new optimizer setting with a low-cost local dummy run",
            "exploit": "Refine the current best direction with one tighter iteration",
            "validate": "Re-run the latest promising path to estimate variance",
            "research": "Convert local research snapshots into one concrete experiment",
            "community": f"Test community suggestion: {idea['title']}" if idea else "Process community suggestion queue",
        }
        rationale_map = {
            "explore": "No reliable best run exists yet, so the loop should establish a baseline.",
            "exploit": "A previous score exists, so incremental refinement is justified.",
            "validate": "Recent results need confirmation before the public ledger treats them as solid.",
            "research": "Research snapshots should periodically alter the agenda rather than remaining passive notes.",
            "community": "Outside suggestions are first-class inputs and should be tested visibly.",
        }
        expected_map = {
            "explore": "Obtain a first comparable score and artifact package.",
            "exploit": "Small score lift or a sharper understanding of the current frontier.",
            "validate": "Lower uncertainty about whether the current result is real.",
            "research": "One hypothesis grounded in a fetched source snapshot.",
            "community": "A public response tied to a concrete test or a documented rejection.",
        }

        updates = ["current_status", "agenda", "latest_thoughts", "leaderboard"]
        if mode == "community" and idea:
            updates.append("contributors")

        adapter = "parameter_golf" if mode in {"exploit", "validate"} else "dummy"
        if mode == "community" and idea and "parameter golf" in idea["title"].lower():
            adapter = "parameter_golf"

        return Plan(
            mode=mode,
            title=title_map[mode],
            rationale=rationale_map[mode],
            expected_signal=expected_map[mode],
            public_updates=updates,
            adapter=adapter,
            idea_source=idea.get("author") if idea else None,
        )

    def _codex_plan(self, research_notes: Sequence[dict], model: Optional[str]) -> Plan:
        state = self.store.current_state()
        best_runs = self.store.best_runs()
        community = self.store.community_queue()[:5]
        prompt = (
            "You are the planner for an always-on public autonomous research lab.\n"
            "Return only JSON matching the provided schema.\n"
            "Choose exactly one mode from: explore, exploit, validate, research, community.\n"
            "Choose one adapter from: dummy, parameter_golf.\n"
            "Prefer community mode only when a queued idea should actually be tested now.\n"
            "Prefer parameter_golf only for ideas clearly related to parameter golf.\n\n"
            f"Current state:\n{json.dumps(state, indent=2, sort_keys=True)}\n\n"
            f"Best runs:\n{json.dumps(best_runs, indent=2, sort_keys=True)}\n\n"
            f"Community queue:\n{json.dumps(community, indent=2, sort_keys=True)}\n\n"
            f"Research notes:\n{json.dumps(list(research_notes)[:3], indent=2, sort_keys=True)}\n"
        )
        payload = self.codex.plan(self.store.paths.root, prompt, model=model)
        return Plan(
            mode=payload["mode"],
            title=payload["title"],
            rationale=payload["rationale"],
            expected_signal=payload["expected_signal"],
            public_updates=list(payload["public_updates"]),
            adapter=payload["adapter"],
            idea_source=payload.get("idea_source"),
        )
