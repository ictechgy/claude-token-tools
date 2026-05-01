import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClaudeTokenKitTests(unittest.TestCase):
    def test_trim_preserves_exit_code_and_trims(self):
        cmd = [
            sys.executable,
            str(ROOT / "claude-token-kit" / "trim_command_output.py"),
            "--max-lines",
            "20",
            "--",
            sys.executable,
            "-c",
            "import sys; [print(i) for i in range(80)]; print('FAILED sample', file=sys.stderr); sys.exit(7)",
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 7)
        self.assertIn("output trimmed", proc.stdout)
        self.assertIn("FAILED sample", proc.stdout)
        self.assertLess(len(proc.stdout.splitlines()), 40)

    def test_rewrite_hook_wraps_pytest_command(self):
        payload = {"tool_input": {"command": "pytest tests -q"}}
        proc = subprocess.run(
            [sys.executable, str(ROOT / "claude-token-kit" / "rewrite_bash_for_token_budget.py")],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=ROOT,
            check=True,
        )
        out = json.loads(proc.stdout)
        command = out["hookSpecificOutput"]["updatedInput"]["command"]
        self.assertIn("trim_command_output.py", command)
        self.assertIn("pytest tests -q", command)

    def test_transcript_audit_reads_usage(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "session.jsonl"
            sample.write_text(
                json.dumps({
                    "message": {
                        "model": "claude-sonnet-test",
                        "usage": {
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "cache_read_input_tokens": 3,
                        },
                    }
                }) + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(ROOT / "claude-token-kit" / "claude_transcript_cost_audit.py"), str(sample), "--json"],
                text=True,
                capture_output=True,
                check=True,
            )
        data = json.loads(proc.stdout)
        self.assertEqual(data["total_tokens"], 18)
        self.assertEqual(data["tokens"]["input"], 10)
        self.assertEqual(data["tokens"]["output"], 5)
        self.assertEqual(data["tokens"]["cache_read"], 3)

    def test_aux_delegate_enable_disable_and_disabled_ask(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["CLAUDE_TOKEN_OPTIMIZER_CONFIG"] = str(Path(tmp) / "config.json")
            enable = subprocess.run(
                [sys.executable, str(ROOT / "claude-token-kit" / "aux_ai_delegate.py"), "enable", "--provider", "gemini"],
                text=True,
                capture_output=True,
                env=env,
                check=True,
            )
            self.assertIn("enabled auxiliary AI delegation", enable.stdout)

            disable = subprocess.run(
                [sys.executable, str(ROOT / "claude-token-kit" / "aux_ai_delegate.py"), "disable"],
                text=True,
                capture_output=True,
                env=env,
                check=True,
            )
            self.assertIn("disabled auxiliary AI delegation", disable.stdout)

            ask = subprocess.run(
                [sys.executable, str(ROOT / "claude-token-kit" / "aux_ai_delegate.py"), "ask", "--provider", "gemini", "--prompt", "hello"],
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(ask.returncode, 3)
            self.assertIn("delegation is disabled", ask.stderr)

    def test_aux_delegate_runs_mock_provider_and_trims_preview(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(json.dumps({
                "aux_ai_enabled": True,
                "default_provider": "gemini",
                "max_output_chars": 40,
                "delegation_dir": str(Path(tmp) / "delegations"),
                "providers": {
                    "gemini": {
                        "enabled": True,
                        "command": [
                            sys.executable,
                            "-c",
                            "import sys; data=sys.stdin.read(); print('MOCK:' + data[:120])",
                        ],
                        "stdin": True,
                    }
                },
            }), encoding="utf-8")
            env = os.environ.copy()
            env["CLAUDE_TOKEN_OPTIMIZER_CONFIG"] = str(config_path)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "claude-token-kit" / "aux_ai_delegate.py"),
                    "ask",
                    "--provider",
                    "gemini",
                    "--prompt",
                    "analyze this",
                ],
                text=True,
                capture_output=True,
                env=env,
                check=True,
            )
            self.assertIn("provider=gemini", proc.stdout)
            self.assertIn("response_saved=", proc.stdout)
            self.assertIn("MOCK:", proc.stdout)
            self.assertIn("trimmed=true", proc.stdout)
            saved_line = next(line for line in proc.stdout.splitlines() if line.startswith("response_saved="))
            saved_path = Path(saved_line.split("=", 1)[1])
            self.assertTrue(saved_path.exists())



if __name__ == "__main__":
    unittest.main()
