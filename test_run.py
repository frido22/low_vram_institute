"""Tests for run.py and parameter_golf.py."""
import json
import tempfile
import unittest
from pathlib import Path

import run
import parameter_golf


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state = Path(self._tmp.name) / "state"
        self.state.mkdir()
        self._orig = run.STATE_DIR
        run.STATE_DIR = self.state

    def tearDown(self):
        run.STATE_DIR = self._orig

    def test_empty_ledger(self):
        self.assertEqual(run.ledger_rows(), [])
        self.assertIsNone(run.best_score())

    def test_append_and_read(self):
        run._append_ledger({"run_id": "r1", "score": 2.3})
        run._append_ledger({"run_id": "r2", "score": 2.1})
        self.assertEqual(len(run.ledger_rows()), 2)
        self.assertAlmostEqual(run.best_score(), 2.1)

    def test_save_and_read_best(self):
        run._save_best("r1", 2.0, "test", "print('hi')", "--- diff ---")
        self.assertEqual(run.best_script(), "print('hi')")
        self.assertIn("diff", run.best_diff())


class RenderContextTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state = Path(self._tmp.name) / "state"
        self.state.mkdir()
        self._orig = run.STATE_DIR
        run.STATE_DIR = self.state

    def tearDown(self):
        run.STATE_DIR = self._orig

    def test_no_runs(self):
        self.assertEqual(run.render_context(), "No runs yet.")

    def test_with_runs(self):
        run._append_ledger({"run_id": "r1", "score": 2.3, "improved_best": True, "title": "baseline", "mode": "explore"})
        run._append_ledger({"run_id": "r2", "score": 2.5, "improved_best": False, "has_modified_script": True, "title": "bad idea", "mode": "exploit", "rationale": "tried something wild"})
        ctx = run.render_context()
        self.assertIn("Best: 2.3000", ctx)
        self.assertIn("Failed ideas", ctx)
        self.assertIn("+0.2000", ctx)  # delta from best

    def test_near_misses(self):
        run._append_ledger({"run_id": "r1", "score": 2.30, "improved_best": True, "title": "baseline"})
        run._append_ledger({"run_id": "r2", "score": 2.31, "improved_best": False, "has_modified_script": True, "title": "close one", "rationale": "tweaked lr schedule"})
        run._append_ledger({"run_id": "r3", "score": 5.00, "improved_best": False, "has_modified_script": True, "title": "disaster"})
        ctx = run.render_context()
        self.assertIn("Near-misses", ctx)
        self.assertIn("close one", ctx)
        self.assertIn("tweaked lr schedule", ctx)
        # disaster should be in failures, not near-misses
        self.assertIn("disaster", ctx)

    def test_scales_to_many_runs(self):
        run._append_ledger({"run_id": "r1", "score": 2.3, "improved_best": True, "title": "baseline"})
        for i in range(100):
            run._append_ledger({"run_id": f"r{i+2}", "score": 2.3 + i * 0.01, "improved_best": False, "has_modified_script": True, "title": f"idea_{i}"})
        ctx = run.render_context()
        # Should still render without blowing up
        self.assertIn("Best: 2.3000", ctx)
        # Should cap failures at 20
        self.assertIn("and ", ctx)  # "... and N more"


class CurveTests(unittest.TestCase):
    def test_no_data(self):
        self.assertEqual(run._analyze_curve("")["shape"], "no_data")

    def test_improving(self):
        lines = "\n".join(json.dumps({"val_bpb": 3.0 - i * 0.1}) for i in range(10))
        result = run._analyze_curve(lines)
        self.assertEqual(result["shape"], "improving")
        self.assertAlmostEqual(result["first_val"], 3.0)
        self.assertAlmostEqual(result["last_val"], 2.1)
        self.assertAlmostEqual(result["drop"], 0.9)

    def test_flat(self):
        lines = "\n".join(json.dumps({"val_bpb": 2.3}) for _ in range(10))
        self.assertEqual(run._analyze_curve(lines)["shape"], "flat")


class MetricTests(unittest.TestCase):
    def test_parse_final(self):
        result = parameter_golf._parse_final_metrics("final_int8_zlib_roundtrip_exact val_loss:2.345 val_bpb:2.123")
        self.assertAlmostEqual(result["val_bpb"], 2.123)

    def test_parse_steps(self):
        rows = parameter_golf._parse_metrics_rows("step:1/10 val_loss:3.0 val_bpb:2.5\nstep:2/10 val_loss:2.8 val_bpb:2.3\n")
        self.assertEqual(len(rows), 2)

    def test_parse_diagnostics(self):
        d = parameter_golf._parse_diagnostics("throughput:avg_tok_s:1234.5 total_tokens:500000\nmemory:peak_mb:8192.0 active_mb:7000.0\n")
        self.assertAlmostEqual(d["avg_tok_s"], 1234.5)
        self.assertAlmostEqual(d["peak_mb"], 8192.0)


class ChartTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state = Path(self._tmp.name) / "state"
        self.state.mkdir()
        self._orig = run.STATE_DIR
        run.STATE_DIR = self.state

    def tearDown(self):
        run.STATE_DIR = self._orig

    def test_csv(self):
        run._append_ledger({"run_id": "r1", "score": 2.3, "mode": "explore", "has_modified_script": False, "title": "baseline"})
        self.assertIn("r1", run._render_csv())

    def test_svg_empty(self):
        self.assertIn("No history", run._render_svg())

    def test_svg_with_data(self):
        run._append_ledger({"run_id": "r1", "score": 2.3, "improved_best": True})
        self.assertIn("polyline", run._render_svg())


class PlanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state = Path(self._tmp.name) / "state"
        self.state.mkdir()
        self._orig_state = run.STATE_DIR
        self._orig_config = run.CONFIG_DIR
        run.STATE_DIR = self.state
        run.CONFIG_DIR = Path(self._tmp.name) / "config"
        run.CONFIG_DIR.mkdir()
        (run.CONFIG_DIR / "runtime.json").write_text(json.dumps({"codex": {"enabled": False}}))

    def tearDown(self):
        run.STATE_DIR = self._orig_state
        run.CONFIG_DIR = self._orig_config

    def test_heuristic_explore(self):
        self.assertEqual(run.plan()["mode"], "explore")

    def test_heuristic_exploit(self):
        run._append_ledger({"run_id": "r1", "score": 2.3})
        self.assertEqual(run.plan()["mode"], "exploit")


if __name__ == "__main__":
    unittest.main()
