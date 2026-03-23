from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
