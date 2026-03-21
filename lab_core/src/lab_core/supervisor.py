from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import shutil
import time
from pathlib import Path
from typing import Optional

from .config import LabConfig, Paths
from .executor import Executor
from .planner import Planner
from .publisher import Publisher
from .services.codex_wrapper import CodexWrapper
from .services.codex_wrapper import CodexInvocationError
from .services.github_intake import GitHubIntake
from .services.research import ResearchSnapshotService
from .state_store import StateStore


class Supervisor:
    def __init__(self, paths: Paths, config: Optional[LabConfig] = None) -> None:
        self.paths = paths
        self.config = config or LabConfig()
        self.store = StateStore(paths)
        self.planner = Planner(self.store)
        self.executor = Executor(self.store)
        self.publisher = Publisher(self.store)
        self.github_intake = GitHubIntake(paths, self.store)
        self.research = ResearchSnapshotService(paths)
        self.codex = CodexWrapper()

    def _lock_path(self) -> Path:
        return self.paths.state_dir / "run.lock"

    def _health_check(self) -> None:
        usage = shutil.disk_usage(self.paths.root)
        if usage.free < self.config.min_free_disk_bytes:
            raise RuntimeError("Refusing to proceed: low free disk space.")
        for path in [self.paths.state_dir, self.paths.logs_dir, self.paths.public_root]:
            path.mkdir(parents=True, exist_ok=True)

    def _run_id(self) -> str:
        existing = [
            path.name
            for path in self.paths.public_runs_dir.iterdir()
            if path.is_dir() and path.name.startswith(datetime.now(timezone.utc).strftime("%Y_%m_%d_run_"))
        ]
        index = len(existing) + 1
        return datetime.now(timezone.utc).strftime("%Y_%m_%d_run_") + f"{index:04d}"

    @contextmanager
    def run_lock(self):
        lock_path = self._lock_path()
        if lock_path.exists():
            payload = json.loads(lock_path.read_text())
            locked_at = datetime.fromisoformat(payload["locked_at"])
            age = (datetime.now(timezone.utc) - locked_at).total_seconds()
            if age > self.config.stale_lock_seconds:
                lock_path.unlink()
            else:
                raise RuntimeError("Another run appears active.")
        lock_path.write_text(json.dumps({"locked_at": datetime.now(timezone.utc).isoformat()}, indent=2) + "\n")
        try:
            yield
        finally:
            if lock_path.exists():
                lock_path.unlink()

    def run_once(self) -> str:
        self._health_check()
        with self.run_lock():
            run_id = self._run_id()
            try:
                self.store.write_checkpoint("starting", run_id)
                self.store.write_heartbeat({"run_id": run_id, "status": "starting", "timestamp": datetime.now(timezone.utc).isoformat()})
                codex_status = self.codex.detect()
                self.store.append_event("codex_status", codex_status.__dict__)

                research_notes = self.research.refresh()
                self.store.write_checkpoint("research_refreshed", run_id, {"count": len(research_notes)})
                community = self.github_intake.refresh()
                self.store.write_checkpoint("community_refreshed", run_id, {"count": len(community)})

                plan = self.planner.plan(research_notes)
                self.store.append_event("plan_created", {"run_id": run_id, "plan": plan.__dict__})
                self.store.write_heartbeat({"run_id": run_id, "status": "planned", "mode": plan.mode, "timestamp": datetime.now(timezone.utc).isoformat()})

                result = self.executor.execute(run_id, plan)
                self.store.update_after_run(result)
                self.publisher.publish(result)

                self.store.write_checkpoint("published", run_id, {"score": result.evaluation.score})
                self.store.write_heartbeat({"run_id": run_id, "status": "published", "timestamp": datetime.now(timezone.utc).isoformat()})
                self.store.append_event("run_published", {"run_id": run_id, "score": result.evaluation.score})
                return run_id
            except CodexInvocationError as exc:
                self.store.write_checkpoint(
                    "waiting_on_codex",
                    run_id,
                    {"error": str(exc), "detail": exc.detail, "retryable": exc.retryable},
                )
                self.store.append_event(
                    "codex_unavailable",
                    {"run_id": run_id, "error": str(exc), "detail": exc.detail, "retryable": exc.retryable},
                )
                self.store.write_heartbeat(
                    {
                        "run_id": run_id,
                        "status": "waiting_on_codex",
                        "error": str(exc),
                        "retryable": exc.retryable,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                raise

    def daemon(self) -> None:
        failures = 0
        cycles = 0
        while self.config.max_cycles is None or cycles < self.config.max_cycles:
            try:
                self.run_once()
                failures = 0
                cycles += 1
                time.sleep(self.config.heartbeat_seconds)
            except KeyboardInterrupt:
                self.store.append_event("shutdown", {"reason": "keyboard_interrupt"})
                raise
            except CodexInvocationError as exc:
                failures += 1
                delay = min(self.config.base_backoff_seconds * (2 ** (failures - 1)), self.config.max_backoff_seconds)
                self.store.write_checkpoint(
                    "waiting_on_codex",
                    None,
                    {"error": str(exc), "detail": exc.detail, "retry_in": delay, "retryable": exc.retryable},
                )
                self.store.append_event(
                    "codex_unavailable",
                    {"error": str(exc), "detail": exc.detail, "retry_in": delay, "retryable": exc.retryable},
                )
                self.store.write_heartbeat(
                    {
                        "status": "waiting_on_codex",
                        "error": str(exc),
                        "retry_in": delay,
                        "retryable": exc.retryable,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                if not exc.retryable:
                    raise
                time.sleep(delay)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                delay = min(self.config.base_backoff_seconds * (2 ** (failures - 1)), self.config.max_backoff_seconds)
                self.store.append_event("run_failed", {"error": str(exc), "failures": failures, "retry_in": delay})
                self.store.write_heartbeat(
                    {
                        "status": "backoff",
                        "error": str(exc),
                        "retry_in": delay,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                time.sleep(delay)
