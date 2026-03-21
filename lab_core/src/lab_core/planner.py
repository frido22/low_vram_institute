from __future__ import annotations

from collections.abc import Sequence

from .models import Plan
from .state_store import StateStore


MODES = ["explore", "exploit", "validate", "research", "community"]


class Planner:
    def __init__(self, store: StateStore) -> None:
        self.store = store

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
