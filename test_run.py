from pathlib import Path
import json
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run


class CodexErrorTests(unittest.TestCase):
    @patch("run.shutil.which", return_value="/usr/bin/codex")
    @patch("run.subprocess.run")
    def test_transport_failures_are_retryable(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(
            returncode=1,
            stdout="",
            stderr=(
                "failed to refresh available models: "
                "stream disconnected before completion: "
                "error sending request for url "
                "(https://chatgpt.com/backend-api/codex)"
            ),
        )

        with self.assertRaises(run.CodexError) as ctx:
            run._call_codex("prompt")

        self.assertTrue(ctx.exception.retryable)

    def test_invalid_model_errors_are_not_retryable(self):
        self.assertFalse(run._is_retryable_codex_failure("invalid model: gpt-unknown"))

    @patch("run.shutil.which", return_value=None)
    def test_missing_codex_binary_is_not_retryable(self, _mock_which):
        with self.assertRaises(run.CodexError) as ctx:
            run._call_codex("prompt")

        self.assertFalse(ctx.exception.retryable)

    @patch("run.shutil.which", return_value="/usr/bin/codex")
    @patch("run.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="", stderr=""))
    def test_missing_output_file_is_not_retryable(self, _mock_run, _mock_which):
        with self.assertRaises(run.CodexError) as ctx:
            run._call_codex("prompt")

        self.assertFalse(ctx.exception.retryable)

    @patch("run.shutil.which", return_value="/usr/bin/codex")
    @patch("run.subprocess.run")
    def test_invalid_json_output_is_not_retryable(self, mock_run, _mock_which):
        def fake_run(cmd, **_kwargs):
            output_path = Path(cmd[cmd.index("--output-last-message") + 1])
            output_path.write_text("{not json")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        mock_run.side_effect = fake_run

        with self.assertRaises(run.CodexError) as ctx:
            run._call_codex("prompt")

        self.assertFalse(ctx.exception.retryable)


class BestStateTests(unittest.TestCase):
    def test_render_context_uses_best_valid_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            rows = [
                {
                    "run_id": "valid",
                    "score": 1.6,
                    "title": "Valid winner",
                    "under_16mb": True,
                    "has_modified_script": True,
                    "improved_best": True,
                },
                {
                    "run_id": "oversize",
                    "score": 1.5,
                    "title": "Oversize raw winner",
                    "under_16mb": False,
                    "has_modified_script": True,
                    "improved_best": True,
                },
            ]
            (state_dir / "ledger.jsonl").write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
            )

            with patch.object(run, "STATE_DIR", state_dir):
                context = run.render_context()

            self.assertIn("Best valid: 1.6000 (valid)", context)
            self.assertIn("oversize", context)

    def test_oversize_run_does_not_replace_best_script(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            state_dir.mkdir(exist_ok=True)
            existing = {
                "run_id": "valid",
                "score": 1.6,
                "title": "Valid winner",
                "under_16mb": True,
                "has_modified_script": True,
                "improved_best": True,
            }
            (state_dir / "ledger.jsonl").write_text(json.dumps(existing, sort_keys=True) + "\n")

            with patch.object(run, "STATE_DIR", state_dir):
                run._save_best("valid", 1.6, "Valid winner", "valid script", "valid patch")
                run._update_after_run(
                    "oversize",
                    {
                        "title": "Oversize raw winner",
                        "rationale": "better score but too large",
                        "modified_script": "oversize script",
                    },
                    {
                        "score": 1.5,
                        "runtime_seconds": 1.0,
                        "passed": True,
                        "patch": "oversize patch",
                        "metrics_jsonl": "",
                        "diagnostics": {
                            "under_16mb": False,
                            "artifact_bytes": 18_000_110,
                            "quantized_bytes": 17_931_574,
                            "code_bytes": 72_536,
                        },
                    },
                )
                saved = json.loads((state_dir / "best_script.json").read_text())

            self.assertEqual(saved["run_id"], "valid")
            self.assertEqual(saved["modified_script"], "valid script")


if __name__ == "__main__":
    unittest.main()
