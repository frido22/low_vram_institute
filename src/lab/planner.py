from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from .config import load_runtime
from .models import Plan
from .services.codex_wrapper import CodexWrapper
from .state_store import StateStore


class Planner:
    def __init__(self, store: StateStore) -> None:
        self.store = store
        self.runtime = load_runtime(store.paths)
        self.codex = CodexWrapper()
        self.track = self.runtime.get("parameter_golf", {}).get("local_track", "mac_mini_official_like")

    def choose_mode(self) -> str:
        if self.store.best_score() is None:
            return "explore"
        return "exploit"

    def plan(
        self,
        research_notes: Sequence[dict],
        community_ideas: Sequence[dict] | None = None,
        run_errors: Sequence[str] | None = None,
    ) -> Plan:
        codex_cfg = self.runtime.get("codex", {})
        if codex_cfg.get("enabled"):
            return self._codex_plan(research_notes, community_ideas or [], codex_cfg.get("model"), run_errors=run_errors)
        return self._heuristic_plan()

    def _heuristic_plan(self) -> Plan:
        mode = self.choose_mode()
        modified_script = self.store.best_script() if mode == "exploit" else None
        return Plan(
            mode=mode,
            title="Establish baseline" if mode == "explore" else "Refine current best",
            rationale="Baseline needed." if mode == "explore" else "Exploiting current best direction.",
            expected_signal="First comparable score." if mode == "explore" else "Score delta.",
            public_updates=["overview"],
            adapter="parameter_golf",
            track=self.track,
            modified_script=modified_script,
        )

    def _rules_text(self) -> str:
        rules_path = self.store.paths.config_dir / "parameter_golf_rules.md"
        if rules_path.exists():
            return rules_path.read_text().strip()
        return ""

    def _training_script_content(self) -> str:
        workspace = self.runtime.get("parameter_golf", {}).get("workspace", "")
        script_path = Path(workspace) / "train_gpt_mlx.py"
        if script_path.exists():
            try:
                return script_path.read_text()
            except OSError:
                return "(script could not be read)"
        return "(script not available)"

    def _format_community(self, community: Sequence[dict]) -> str:
        if not community:
            return "- none"
        lines = []
        for item in community[:5]:
            lines.append(f"- @{item.get('author', '?')}: {item.get('title', 'untitled')}")
        return "\n".join(lines)

    def _format_research(self, research: Sequence[dict]) -> str:
        if not research:
            return "- none"
        lines = []
        for note in list(research)[:3]:
            body = " ".join(str(note.get("body", "")).split())
            if len(body) > 400:
                body = body[:397] + "..."
            lines.append(f"- {note.get('title', 'untitled')}: {body}")
        return "\n".join(lines)

    def _codex_plan(
        self,
        research_notes: Sequence[dict],
        community_ideas: Sequence[dict],
        model: Optional[str],
        run_errors: Sequence[str] | None = None,
    ) -> Plan:
        script_content = self._training_script_content()
        run_context = self.store.render_context()

        # Best diff
        best_diff = self.store.best_diff().strip()
        best_diff_section = ""
        if best_diff:
            best_diff_section = f"## Current Best Changes\n```diff\n{best_diff}\n```\n\n"

        prompt = (
            "You are the autonomous planner for a public research lab on a Mac mini M4 (16GB).\n"
            "Return only JSON matching the provided schema.\n\n"
            "## Modes\n"
            "- explore: baselines (only when no data exists)\n"
            "- exploit: compound on current best\n"
            "- research: try something new\n"
            "- community: test an external suggestion\n\n"
            "## Output\n"
            "Return `modified_script`: the COMPLETE modified `train_gpt_mlx.py`.\n"
            "EVERY run must change something. Null is only acceptable for the very first baseline.\n"
            "To compound: incorporate the best diff below and add your changes.\n"
            "Original is always restored after each run — be fearless.\n\n"
            f"{self._rules_text()}\n\n"
            "## Run History\n"
            f"{run_context}\n\n"
            f"{best_diff_section}"
            "## Community Ideas\n"
            f"{self._format_community(community_ideas)}\n\n"
            "## Research Notes\n"
            f"{self._format_research(research_notes)}\n\n"
            "## Original train_gpt_mlx.py\n\n"
            f"```python\n{script_content}\n```\n"
        )
        if run_errors:
            prompt += (
                "\n## Previous Run Errors\n\n"
                "Your previous attempts failed. Fix the issue or try a different approach.\n\n"
            )
            for i, err in enumerate(run_errors):
                prompt += f"- Attempt {i + 1}: {err}\n"

        payload = self.codex.plan(self.store.paths.root, prompt, model=model)
        return Plan(
            mode=payload["mode"],
            title=payload["title"],
            rationale=payload["rationale"],
            expected_signal=payload["expected_signal"],
            public_updates=list(payload["public_updates"]),
            adapter="parameter_golf",
            logging_focus=list(payload.get("logging_focus") or []),
            idea_source=payload.get("idea_source"),
            idea_id=payload.get("idea_id"),
            track=self.track,
            modified_script=payload.get("modified_script") or None,
        )
