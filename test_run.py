"""Tests for run.py and parameter_golf.py — no training required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run
import parameter_golf


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state = Path(self._tmp.name) / "state"
        self.state.mkdir()
        self._orig_state = run.STATE_DIR
        run.STATE_DIR = self.state

    def tearDown(self):
        run.STATE_DIR = self._orig_state

    def test_empty_ledger(self):
        self.assertEqual(run.ledger_rows(), [])
        self.assertIsNone(run.best_score())

    def test_append_and_read(self):
        run._append_ledger({"run_id": "r1", "score": 2.3})
        run._append_ledger({"run_id": "r2", "score": 2.1})
        rows = run.ledger_rows()
        self.assertEqual(len(rows), 2)
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
        self._orig_state = run.STATE_DIR
        run.STATE_DIR = self.state

    def tearDown(self):
        run.STATE_DIR = self._orig_state

    def test_no_runs(self):
        self.assertEqual(run.render_context(), "No runs yet.")

    def test_with_runs(self):
        run._append_ledger({"run_id": "r1", "score": 2.3, "improved_best": True, "title": "baseline", "mode": "explore"})
        run._append_ledger({"run_id": "r2", "score": 2.5, "improved_best": False, "has_modified_script": True, "title": "bad idea", "mode": "exploit"})
        ctx = run.render_context()
        self.assertIn("Best: 2.3000", ctx)
        self.assertIn("bad idea", ctx)
        self.assertIn("Failed modifications", ctx)


class CurveAnalysisTests(unittest.TestCase):
    def test_no_data(self):
        self.assertEqual(run._analyze_curve(""), "no_data")

    def test_improving(self):
        lines = "\n".join(json.dumps({"val_bpb": 3.0 - i * 0.1}) for i in range(10))
        self.assertEqual(run._analyze_curve(lines), "improving")

    def test_flat(self):
        lines = "\n".join(json.dumps({"val_bpb": 2.3}) for _ in range(10))
        self.assertEqual(run._analyze_curve(lines), "flat")


class MetricParsingTests(unittest.TestCase):
    def test_parse_final(self):
        log = "final_int8_zlib_roundtrip_exact val_loss:2.345 val_bpb:2.123"
        result = parameter_golf._parse_final_metrics(log)
        self.assertAlmostEqual(result["val_bpb"], 2.123)

    def test_parse_steps(self):
        log = "step:1/10 val_loss:3.0 val_bpb:2.5\nstep:2/10 val_loss:2.8 val_bpb:2.3\n"
        rows = parameter_golf._parse_metrics_rows(log)
        self.assertEqual(len(rows), 2)

    def test_parse_diagnostics(self):
        log = "throughput:avg_tok_s:1234.5 total_tokens:500000\nmemory:peak_mb:8192.0 active_mb:7000.0\n"
        d = parameter_golf._parse_diagnostics(log)
        self.assertAlmostEqual(d["avg_tok_s"], 1234.5)
        self.assertAlmostEqual(d["peak_mb"], 8192.0)


class HistoryRenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state = Path(self._tmp.name) / "state"
        self.state.mkdir()
        self._orig_state = run.STATE_DIR
        run.STATE_DIR = self.state

    def tearDown(self):
        run.STATE_DIR = self._orig_state

    def test_csv(self):
        run._append_ledger({"run_id": "r1", "score": 2.3, "mode": "explore", "has_modified_script": False, "title": "baseline"})
        csv = run._render_history_csv()
        self.assertIn("r1", csv)
        self.assertIn("2.3", csv)

    def test_svg_empty(self):
        svg = run._render_history_svg()
        self.assertIn("No history", svg)

    def test_svg_with_data(self):
        run._append_ledger({"run_id": "r1", "score": 2.3, "improved_best": True})
        svg = run._render_history_svg()
        self.assertIn("polyline", svg)


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
        p = run.plan([], [])
        self.assertEqual(p["mode"], "explore")

    def test_heuristic_exploit(self):
        run._append_ledger({"run_id": "r1", "score": 2.3})
        p = run.plan([], [])
        self.assertEqual(p["mode"], "exploit")


if __name__ == "__main__":
    unittest.main()
