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
from .services.codex_wrapper import CodexWrapper, CodexInvocationError
from .services.intake import IntakeService
from .state_store import StateStore


class Supervisor:
    def __init__(self, paths: Paths, config: Optional[LabConfig] = None) -> None:
        self.paths = paths
        self.config = config or LabConfig()
        self.store = StateStore(paths)
        self.planner = Planner(self.store)
        self.executor = Executor(self.store)
        self.publisher = Publisher(self.store)
        self.intake = IntakeService(paths)
        self.codex = CodexWrapper()

    def _emit(self, message: str) -> None:
        print(f"[lab] {message}", flush=True)

    def _lock_path(self) -> Path:
        return self.paths.state_dir / "run.lock"

    def _health_check(self) -> None:
        usage = shutil.disk_usage(self.paths.root)
        if usage.free < self.config.min_free_disk_bytes:
            raise RuntimeError("Refusing to proceed: low free disk space.")

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
        lock_path.write_text(json.dumps({"locked_at": datetime.now(timezone.utc).isoformat()}) + "\n")
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
                self._emit(f"starting {run_id}")
                self.store.write_checkpoint("starting", run_id)
                self.store.write_heartbeat({"run_id": run_id, "status": "starting", "timestamp": datetime.now(timezone.utc).isoformat()})

                community, research = self.intake.refresh()
                self._emit(f"intake: {len(community)} community, {len(research)} research")

                # Plan -> execute -> retry on failure
                run_errors: list[str] = []
                for attempt in range(3):
                    plan = self.planner.plan(research, community, run_errors=run_errors or None)
                    self.store.append_event("plan_created", {"run_id": run_id, "title": plan.title, "mode": plan.mode, "has_modified_script": bool(plan.modified_script)})
                    self.store.write_heartbeat({"run_id": run_id, "status": "planned", "mode": plan.mode, "timestamp": datetime.now(timezone.utc).isoformat()})
                    self._emit(f"plan {plan.mode}: {plan.title}")

                    try:
                        result = self.executor.execute(run_id, plan)
                        break
                    except Exception as exc:
                        run_errors.append(str(exc))
                        self._emit(f"run failed (attempt {attempt + 1}/3): {exc}")
                        self.store.append_event("run_attempt_failed", {"run_id": run_id, "attempt": attempt + 1, "error": str(exc)})
                        if attempt == 2:
                            raise RuntimeError("run failed after 3 attempts") from exc

                self._emit(f"result score={result.evaluation.score:.4f} passed={result.evaluation.passed}")
                self.store.update_after_run(result)
                self.publisher.publish(result)

                self.store.write_checkpoint("published", run_id, {"score": result.evaluation.score})
                self.store.write_heartbeat({"run_id": run_id, "status": "published", "timestamp": datetime.now(timezone.utc).isoformat()})
                self.store.append_event("run_published", {"run_id": run_id, "score": result.evaluation.score})
                self._emit(f"published {run_id}")
                return run_id
            except CodexInvocationError as exc:
                self._emit(f"waiting on codex: {exc}")
                self.store.write_checkpoint("waiting_on_codex", run_id, {"error": str(exc), "retryable": exc.retryable})
                self.store.append_event("codex_unavailable", {"run_id": run_id, "error": str(exc), "retryable": exc.retryable})
                self.store.write_heartbeat({"run_id": run_id, "status": "waiting_on_codex", "timestamp": datetime.now(timezone.utc).isoformat()})
                raise

    def daemon(self) -> None:
        failures = 0
        cycles = 0
        self._emit("daemon started")
        while self.config.max_cycles is None or cycles < self.config.max_cycles:
            try:
                self.run_once()
                failures = 0
                cycles += 1
                self._emit(f"cycle complete; sleeping {self.config.heartbeat_seconds}s")
                time.sleep(self.config.heartbeat_seconds)
            except KeyboardInterrupt:
                self.store.append_event("shutdown", {"reason": "keyboard_interrupt"})
                self._emit("shutdown requested")
                raise
            except CodexInvocationError as exc:
                failures += 1
                delay = min(self.config.base_backoff_seconds * (2 ** (failures - 1)), self.config.max_backoff_seconds)
                self._emit(f"codex unavailable; retrying in {delay}s")
                self.store.append_event("codex_unavailable", {"error": str(exc), "retry_in": delay, "retryable": exc.retryable})
                self.store.write_heartbeat({"status": "waiting_on_codex", "retry_in": delay, "timestamp": datetime.now(timezone.utc).isoformat()})
                if not exc.retryable:
                    raise
                time.sleep(delay)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                delay = min(self.config.base_backoff_seconds * (2 ** (failures - 1)), self.config.max_backoff_seconds)
                self._emit(f"run failed: {exc}; retrying in {delay}s")
                self.store.append_event("run_failed", {"error": str(exc), "failures": failures, "retry_in": delay})
                self.store.write_heartbeat({"status": "backoff", "error": str(exc), "retry_in": delay, "timestamp": datetime.now(timezone.utc).isoformat()})
                time.sleep(delay)
