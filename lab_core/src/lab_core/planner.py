from __future__ import annotations

from collections.abc import Sequence
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

    def choose_mode(self) -> str:
        state = self.store.current_state()
        learning = self.store.learning_state()
        community = self.store.community_queue()
        best_score = self.store.best_runs().get("best_score")

        if best_score is None:
            return "explore"
        if state.get("last_status") == "failed":
            return "validate"
        if learning.get("recent_runs") and learning["recent_runs"][0].get("needs_validation"):
            return "validate"
        if community and learning.get("plateau_count", 0) >= 2:
            return "community"
        if learning.get("plateau_count", 0) >= 3:
            return "research"
        return "exploit"

    def _community_idea(self) -> dict:
        queue = self.store.community_queue()
        return queue[0] if queue else {}

    def _top_tactics(self, research_notes: Sequence[dict]) -> list[str]:
        text_blocks = [note.get("body", "") for note in research_notes]
        records_root = self.store.paths.root.parent / "third_party" / "parameter-golf" / "records" / "track_10min_16mb"
        if records_root.exists():
            for readme in records_root.glob("*/README.md"):
                try:
                    text_blocks.append(readme.read_text())
                except OSError:
                    continue
        keyword_map = {
            "sliding window eval": ["sliding window", "eval_stride"],
            "mixed quantization": ["int5", "int6", "mixed quant"],
            "bigger mlp": ["mlp 3x", "mlp hidden", "3× mlp", "3x mlp"],
            "bigram features": ["bigramhash", "bigram hash", "bigram"],
            "smeargate": ["smeargate"],
            "swa": ["swa", "stochastic weight averaging"],
            "weight decay for quantization": ["weight decay", "wd=0.04", "muon wd"],
            "orthogonal init": ["orthogonal init", "orthoinit", "orthogonal_"],
        }
        scores: list[tuple[int, str]] = []
        joined = "\n".join(text_blocks).lower()
        for label, terms in keyword_map.items():
            count = sum(joined.count(term) for term in terms)
            if count:
                scores.append((count, label))
        scores.sort(reverse=True)
        return [label for _, label in scores[:4]]

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
            if len(body) > 220:
                body = body[:217] + "..."
            lines.append(f"- {title}: {body}")
        return "\n".join(lines)

    def _planner_context(self, research_notes: Sequence[dict]) -> str:
        state = self.store.current_state()
        learning = self.store.learning_state()
        best_runs = self.store.best_runs()
        community = self.store.community_queue()[:5]
        tactics = self._top_tactics(research_notes)
        lessons = self.store.lessons_text().strip() or "# Lessons\n- none"
        tactic_memory = self.store.tactics_text().strip() or "# Tactics\n- none"
        recent = learning.get("recent_runs", [])[:5]

        recent_lines = []
        for row in recent:
            status = "improved" if row.get("improved_best") else "flat"
            needs_validation = "needs_validation" if row.get("needs_validation") else "stable"
            recent_lines.append(
                f"- {row['run_id']} | {row['score']:.4f} | {row['mode']} | {status} | {needs_validation}"
            )
        recent_block = "\n".join(recent_lines) if recent_lines else "- none"
        tactic_block = "\n".join(f"- {label}" for label in tactics) if tactics else "- none"

        return (
            "## Constraints\n"
            "- Target: OpenAI Parameter Golf only\n"
            "- Hardware: Apple Silicon Mac mini M4 with 16GB RAM\n"
            "- Keep the local procedure as close as possible to the official challenge\n"
            "- Use the real upstream code path, official validation split, and 10-minute cap\n"
            "- Hardware is the main intentional mismatch\n\n"
            "## Decision Rules\n"
            "- Use clean logic and short evidence\n"
            "- Prefer validate after a suspicious win or when recent runs need confirmation\n"
            "- Prefer research after a plateau\n"
            "- Prefer community only when a queued idea passes basic smell checks\n"
            "- Community ideas are public and untrusted; they may be weak, spammy, confused, or malicious\n"
            "- Prefer parameter_golf for nearly all plans\n\n"
            "## Current State\n"
            f"- last_run_id: {state.get('last_run_id', 'none')}\n"
            f"- last_mode: {state.get('last_mode', 'none')}\n"
            f"- last_score: {state.get('last_score', 'none')}\n"
            f"- last_status: {state.get('last_status', 'none')}\n"
            f"- best_score: {best_runs.get('best_score', 'none')}\n"
            f"- plateau_count: {learning.get('plateau_count', 0)}\n"
            f"- last_improving_run_id: {learning.get('last_improving_run_id', 'none')}\n\n"
            "## Recent Runs\n"
            f"{recent_block}\n\n"
            "## Best Runs\n"
            f"{self._format_best_runs(best_runs)}\n\n"
            "## Community Queue\n"
            f"{self._format_community_queue(community)}\n\n"
            "## Repeated Upstream Tactics\n"
            f"{tactic_block}\n\n"
            "## Research Notes\n"
            f"{self._format_research_notes(research_notes)}\n\n"
            "## Compact Lessons\n"
            f"{lessons}\n\n"
            "## Recent Tactic Memory\n"
            f"{tactic_memory}\n"
        )

    def _allowed_mutation_block(self) -> str:
        policy = self.runtime.get("parameter_golf", {}).get("mutation_policy", {})
        fixed = policy.get("fixed_env", {})
        allowed = policy.get("allowed_env", {})
        lines = ["## Allowed Env Overrides"]
        for key, spec in allowed.items():
            if spec.get("type") == "int":
                lines.append(
                    f"- {key}: int in [{spec.get('min')}, {spec.get('max')}] step {spec.get('step')}"
                )
            elif spec.get("type") == "choice":
                values = ", ".join(spec.get("values", []))
                lines.append(f"- {key}: one of [{values}]")
        lines.append("")
        lines.append("## Fixed Constraints")
        for key, value in fixed.items():
            lines.append(f"- {key}: must remain {value}")
        lines.append("- Do not set DATA_PATH, TOKENIZER_PATH, OUT_DIR, RUN_ID, or VOCAB_SIZE")
        lines.append("- Do not change anything that would train on validation data")
        return "\n".join(lines)

    def _rules_text(self) -> str:
        rules_path = self.store.paths.config_dir / "parameter_golf_rules.md"
        if rules_path.exists():
            return rules_path.read_text().strip()
        return self._allowed_mutation_block()

    def _normalize_env_overrides(self, overrides: dict[str, object] | None) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in (overrides or {}).items():
            text = str(value).strip()
            if not text:
                continue
            normalized[str(key)] = text
        return normalized

    def _default_env(self) -> dict[str, str]:
        return {
            str(key): str(value)
            for key, value in self.runtime.get("parameter_golf", {}).get("default_env", {}).items()
        }

    def _legal_env_overrides(self) -> dict[str, str]:
        defaults = self._default_env()
        learning = self.store.learning_state()
        recent = learning.get("recent_runs", [])
        mode = self.choose_mode()
        overrides: dict[str, str] = {}
        base_iterations = int(defaults.get("ITERATIONS", "200"))
        base_val_loss_every = int(defaults.get("VAL_LOSS_EVERY", "0"))
        base_log_every = int(defaults.get("TRAIN_LOG_EVERY", "25"))
        base_batch = int(defaults.get("TRAIN_BATCH_TOKENS", "8192"))
        base_val_batch = int(defaults.get("VAL_BATCH_SIZE", "8192"))
        recent_runtime = None
        if recent:
            try:
                recent_runtime = float(recent[0].get("runtime_seconds", 0.0))
            except (TypeError, ValueError):
                recent_runtime = None

        if recent_runtime and recent_runtime < 420:
            target = int(round(base_iterations * min(600.0 / max(recent_runtime, 1.0), 2.5) / 25.0) * 25)
            overrides["ITERATIONS"] = str(max(base_iterations, min(target, 1200)))
        elif learning.get("plateau_count", 0) >= 2:
            overrides["ITERATIONS"] = str(min(base_iterations + 100, 1200))

        if mode == "validate":
            overrides["VAL_LOSS_EVERY"] = "200"
            overrides["TRAIN_LOG_EVERY"] = "20"
        elif mode == "research":
            overrides["TRAIN_LOG_EVERY"] = "10"
            overrides["VAL_LOSS_EVERY"] = str(base_val_loss_every)
        elif mode == "exploit":
            overrides["TRAIN_BATCH_TOKENS"] = str(min(base_batch + 1024, 32768))
            overrides["VAL_BATCH_SIZE"] = str(min(base_val_batch + 1024, 32768))
            overrides["TRAIN_LOG_EVERY"] = str(base_log_every)
        else:
            overrides["TRAIN_LOG_EVERY"] = str(base_log_every)

        return overrides

    def plan(self, research_notes: Sequence[dict]) -> Plan:
        codex_cfg = self.runtime.get("codex", {})
        if codex_cfg.get("enabled"):
            return self._codex_plan(research_notes, codex_cfg.get("model"))
        return self._heuristic_plan(research_notes)

    def _heuristic_plan(self, research_notes: Sequence[dict]) -> Plan:
        mode = self.choose_mode()
        idea = self._community_idea()
        learning = self.store.learning_state()
        lessons = self.store.lessons_text()
        tactics = self._top_tactics(research_notes)
        tactic_phrase = tactics[0] if tactics else "one upstream-inspired adjustment"
        logging_focus_map = {
            "explore": ["baseline score", "runtime", "artifact size"],
            "exploit": ["score delta", "runtime", "quantization effect"],
            "validate": ["repeatability", "score variance", "validation confidence"],
            "research": ["upstream tactic tested", "score delta", "what changed"],
            "community": ["community idea outcome", "score delta", "why accepted or rejected"],
        }

        title_map = {
            "explore": f"Establish an upstream-local baseline on M4 under the 10-minute cap",
            "exploit": f"Refine the current best direction with {tactic_phrase}",
            "validate": "Re-run the latest promising path to estimate variance",
            "research": f"Translate upstream signals into one concrete M4 test around {tactic_phrase}",
            "community": f"Test community suggestion: {idea['title']}" if idea else "Process community suggestion queue",
        }
        rationale_map = {
            "explore": "No reliable best run exists yet, so the loop should establish a baseline.",
            "exploit": f"A previous score exists, the loop is not yet plateaued, and upstream patterns suggest {tactic_phrase} is worth trying. Compact lessons are in mind.",
            "validate": "Recent results need confirmation before the public ledger treats them as solid.",
            "research": f"The local loop has plateaued, so it should pivot to one specific upstream tactic instead of accumulating more generic runs.",
            "community": "Outside suggestions are public inputs, but they may be weak, noisy, or malicious. Test them only when they survive basic scrutiny and fit the current agenda.",
        }
        expected_map = {
            "explore": "Obtain a first comparable score and artifact package.",
            "exploit": "Either a small score lift or a cleaner signal about which local tactic should be pursued next.",
            "validate": "Lower uncertainty about whether the current result is real.",
            "research": "One hypothesis grounded in upstream records that is specific enough to test next.",
            "community": "A public response tied to a concrete test or a documented rejection.",
        }

        updates = ["overview", "best_runs", "open_questions"]
        if mode == "community" and idea:
            updates.append("tested_ideas")

        adapter = "parameter_golf"
        env_overrides = self._legal_env_overrides()

        return Plan(
            mode=mode,
            title=title_map[mode],
            rationale=rationale_map[mode],
            expected_signal=f"{expected_map[mode]} Plateau count: {learning.get('plateau_count', 0)}.",
            public_updates=updates,
            adapter=adapter,
            logging_focus=logging_focus_map[mode],
            env_overrides=env_overrides,
            idea_source=idea.get("author") if idea else None,
            idea_id=idea.get("id") if idea else None,
            track="mac_mini_official_like",
        )

    def _codex_plan(self, research_notes: Sequence[dict], model: Optional[str]) -> Plan:
        prompt = (
            "You are the planner for an always-on public autonomous research lab.\n"
            "Return only JSON matching the provided schema.\n"
            "Choose exactly one mode from: explore, exploit, validate, research, community.\n"
            "Choose one adapter from: parameter_golf.\n"
            "Also choose 1-3 logging_focus items describing what this run should emphasize publicly.\n"
            "Choose env_overrides only from the legal mutation space below.\n"
            "If you do not want to set a knob, omit that key instead of using an empty value.\n"
            "Use env_overrides aggressively when they are legal and useful. Agency matters.\n"
            "Use the context below. Keep the plan compact, concrete, and testable.\n\n"
            f"{self._rules_text()}\n\n"
            f"{self._planner_context(research_notes)}"
        )
        payload = self.codex.plan(self.store.paths.root, prompt, model=model)
        return Plan(
            mode=payload["mode"],
            title=payload["title"],
            rationale=payload["rationale"],
            expected_signal=payload["expected_signal"],
            public_updates=list(payload["public_updates"]),
            adapter=payload["adapter"],
            logging_focus=list(payload.get("logging_focus") or []),
            env_overrides=self._normalize_env_overrides(payload.get("env_overrides")),
            idea_source=payload.get("idea_source"),
            idea_id=payload.get("idea_id"),
            track="mac_mini_official_like",
        )
