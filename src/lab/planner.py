from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from .config import load_runtime
from .models import COMMUNITY_TITLE_PREFIX, Plan
from .services.codex_wrapper import CodexWrapper
from .state_store import StateStore


class Planner:
    def __init__(self, store: StateStore) -> None:
        self.store = store
        self.runtime = load_runtime(store.paths)
        self.codex = CodexWrapper()
        self.track = self.runtime.get("parameter_golf", {}).get("local_track", "mac_mini_official_like")

    def choose_mode(self) -> str:
        """Weak advisory hint — Codex decides the actual mode."""
        best_score = self.store.best_runs().get("best_score")
        if best_score is None:
            return "explore"
        return "exploit"

    def _community_idea(self) -> dict:
        queue = self.store.community_queue()
        return queue[0] if queue else {}

    def _upstream_records_text(self) -> str:
        """Read upstream Parameter Golf records directly for full context."""
        records_root = self.store.paths.root / "third_party" / "parameter-golf" / "records" / "track_10min_16mb"
        if not records_root.exists():
            return ""
        blocks: list[str] = []
        for readme in sorted(records_root.glob("*/README.md")):
            try:
                text = readme.read_text()
                name = readme.parent.name
                blocks.append(f"### {name}\n{text[:2000]}")
            except OSError:
                continue
        return "\n\n".join(blocks[:10])

    def _format_best_runs(self, best_runs: dict) -> str:
        rows = best_runs.get("runs", [])[:6]
        if not rows:
            return "- none"
        lines = []
        for row in rows:
            lines.append(
                f"- {row['run_id']} | {row['score']:.4f} | {row['mode']} | {row['title']}"
            )
        return "\n".join(lines)

    def _format_community_queue(self, community: Sequence[dict]) -> str:
        if not community:
            return "- none"
        lines = []
        for item in community[:5]:
            idea_id = item.get("id", "unknown")
            title = item.get("title", "untitled")
            author = item.get("author", "unknown")
            lines.append(f"- {idea_id} | @{author} | {title}")
        return "\n".join(lines)

    def _format_research_notes(self, research_notes: Sequence[dict]) -> str:
        if not research_notes:
            return "- none"
        lines = []
        for note in list(research_notes)[:3]:
            title = note.get("title") or note.get("source") or "untitled"
            body = " ".join(str(note.get("body", "")).split())
            if len(body) > 400:
                body = body[:397] + "..."
            lines.append(f"- {title}: {body}")
        return "\n".join(lines)

    def _planner_context(self, research_notes: Sequence[dict]) -> str:
        state = self.store.current_state()
        learning = self.store.learning_state()
        best_runs = self.store.best_runs()
        community = self.store.community_queue()[:5]
        lessons = self.store.lessons_text().strip() or "# Lessons\n- none"
        recent = learning.get("recent_runs", [])[:12]
        recent_titles = [row.get("title", "") for row in recent[:4]]
        consecutive_same_title = 1
        if recent_titles:
            first_title = recent_titles[0]
            for title in recent_titles[1:]:
                if title == first_title and title:
                    consecutive_same_title += 1
                else:
                    break
        recent_modes = [row.get("mode", "") for row in recent[:4]]
        consecutive_same_mode = 1
        if recent_modes:
            first_mode = recent_modes[0]
            for mode in recent_modes[1:]:
                if mode == first_mode and mode:
                    consecutive_same_mode += 1
                else:
                    break

        recent_lines = []
        for row in recent:
            status = "improved" if row.get("improved_best") else "flat"
            mod_tag = " | modified" if row.get("has_modified_script") else ""
            recent_lines.append(
                f"- {row['run_id']} | {row['score']:.4f} | {row['mode']} | {status}{mod_tag} | {row.get('title', '')}"
            )
        recent_block = "\n".join(recent_lines) if recent_lines else "- none"

        # Best changes as unified diff
        best_diff = self.store.best_diff().strip()
        best_diff_section = ""
        if best_diff:
            best_diff_section = (
                "## Current Best Changes\n"
                f"```diff\n{best_diff}\n```\n\n"
            )

        # Upstream records
        upstream = self._upstream_records_text()
        upstream_section = ""
        if upstream:
            upstream_section = f"## Upstream Records\n{upstream}\n\n"

        return (
            "## State\n"
            f"- best_score: {best_runs.get('best_score', 'none')}\n"
            f"- last: {state.get('last_run_id', 'none')} {state.get('last_score', '')} ({state.get('last_status', '')})\n"
            f"- plateau_count: {learning.get('plateau_count', 0)}\n\n"
            "## Budget Pressure\n"
            f"- consecutive_same_title: {consecutive_same_title}\n"
            f"- consecutive_same_mode: {consecutive_same_mode}\n"
            f"- open_community_ideas: {len(community)}\n"
            "- This machine should prefer a strong new idea over repeated weak validation.\n\n"
            "## Recent Runs\n"
            f"{recent_block}\n\n"
            "## Best Runs\n"
            f"{self._format_best_runs(best_runs)}\n\n"
            f"{best_diff_section}"
            "## Community Queue\n"
            f"{self._format_community_queue(community)}\n\n"
            "## Research Notes\n"
            f"{self._format_research_notes(research_notes)}\n\n"
            f"{upstream_section}"
            "## Lessons\n"
            f"{lessons}\n"
        )

    def _rules_text(self) -> str:
        rules_path = self.store.paths.config_dir / "parameter_golf_rules.md"
        if rules_path.exists():
            return rules_path.read_text().strip()
        return ""

    def plan(self, research_notes: Sequence[dict], run_errors: Sequence[str] | None = None) -> Plan:
        codex_cfg = self.runtime.get("codex", {})
        if codex_cfg.get("enabled"):
            return self._codex_plan(research_notes, codex_cfg.get("model"), run_errors=run_errors)
        return self._heuristic_plan(research_notes)

    def _heuristic_plan(self, research_notes: Sequence[dict]) -> Plan:
        mode = self.choose_mode()
        idea = self._community_idea()
        learning = self.store.learning_state()
        logging_focus_map = {
            "explore": ["baseline score", "runtime", "artifact size"],
            "exploit": ["score delta", "runtime", "quantization effect"],
            "validate": ["repeatability", "score variance", "validation confidence"],
            "research": ["upstream tactic tested", "score delta", "what changed"],
            "community": ["community idea outcome", "score delta", "why accepted or rejected"],
        }

        title_map = {
            "explore": "Establish an upstream-local baseline on M4 under the 10-minute cap",
            "exploit": "Refine the current best direction",
            "validate": "Re-run the latest promising path to estimate variance",
            "research": "Test one upstream tactic adapted for Mac mini constraints",
            "community": f"{COMMUNITY_TITLE_PREFIX}{idea['title']}" if idea else "Process community suggestion queue",
        }
        rationale_map = {
            "explore": "No reliable best run exists yet, so the loop should establish a baseline.",
            "exploit": "A previous score exists, the loop is not yet plateaued.",
            "validate": "Recent results need confirmation before the public ledger treats them as solid.",
            "research": "The local loop has plateaued, so it should pivot to one specific upstream tactic.",
            "community": "Outside suggestions are public inputs. Test them only when they survive basic scrutiny.",
        }
        expected_map = {
            "explore": "Obtain a first comparable score and artifact package.",
            "exploit": "Either a small score lift or a cleaner signal.",
            "validate": "Lower uncertainty about whether the current result is real.",
            "research": "One hypothesis grounded in upstream records.",
            "community": "A public response tied to a concrete test or a documented rejection.",
        }

        # Use best modified script for exploit mode (compounding)
        modified_script = self.store.best_script() if mode == "exploit" else None

        return Plan(
            mode=mode,
            title=title_map[mode],
            rationale=rationale_map[mode],
            expected_signal=f"{expected_map[mode]} Plateau count: {learning.get('plateau_count', 0)}.",
            public_updates=["overview"],
            adapter="parameter_golf",
            logging_focus=logging_focus_map[mode],
            idea_source=idea.get("author") if idea else None,
            idea_id=idea.get("id") if idea else None,
            track=self.track,
            modified_script=modified_script,
        )

    def _training_script_content(self) -> str:
        workspace = self.runtime.get("parameter_golf", {}).get("workspace", "")
        script_path = Path(workspace) / "train_gpt_mlx.py"
        if script_path.exists():
            try:
                return script_path.read_text()
            except OSError:
                return "(script could not be read)"
        return "(script not available)"

    def _codex_plan(
        self, research_notes: Sequence[dict], model: Optional[str], run_errors: Sequence[str] | None = None,
    ) -> Plan:
        script_content = self._training_script_content()
        prompt = (
            "You are the autonomous planner for a public research lab on a Mac mini M4 (16GB).\n"
            "Return only JSON matching the provided schema.\n\n"
            "## Modes\n"
            "- explore: baselines (only when no data exists)\n"
            "- exploit: compound on current best\n"
            "- research: try something new\n"
            "- community: test an external suggestion\n"
            "- validate: confirm a suspicious win only when it is clearly worth burning another scarce run\n\n"
            "Prefer exploit/research. Avoid validate unless necessary. Avoid spending many runs on one weak idea.\n\n"
            "## Output\n"
            "Return `modified_script`: the COMPLETE modified `train_gpt_mlx.py`, or null.\n"
            "To compound: incorporate the best diff below and add your changes.\n"
            "Original is always restored after each run — be fearless.\n\n"
            f"{self._rules_text()}\n\n"
            f"{self._planner_context(research_notes)}\n\n"
            "## Original train_gpt_mlx.py\n\n"
            f"```python\n{script_content}\n```\n"
        )
        if run_errors:
            prompt += (
                "\n## Previous Run Errors\n\n"
                "Your previous attempts failed with the errors below.\n"
                "Fix the issue in your modified_script or try a different approach.\n\n"
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
            adapter=payload["adapter"],
            logging_focus=list(payload.get("logging_focus") or []),
            idea_source=payload.get("idea_source"),
            idea_id=payload.get("idea_id"),
            track=self.track,
            modified_script=payload.get("modified_script") or None,
        )
