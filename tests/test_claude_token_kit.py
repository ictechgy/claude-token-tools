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


if __name__ == "__main__":
    unittest.main()
