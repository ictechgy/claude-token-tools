#!/usr/bin/env python3
"""Claude Code PreToolUse hook: wrap noisy Bash test/build/lint commands.

Reads hook JSON from stdin and prints a JSON response understood by Claude Code.
Install via `.claude/settings.json` hooks. Keep this script project-local during
experiments so it can be versioned and reviewed.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys

NOISY_COMMAND_RE = re.compile(
    r"^\s*("
    r"npm\s+(test|run\s+(test|build|lint))\b|"
    r"pnpm\s+(test|run\s+(test|build|lint))\b|"
    r"yarn\s+(test|run\s+(test|build|lint))\b|"
    r"bun\s+(test|run\s+(test|build|lint))\b|"
    r"pytest\b|python\s+-m\s+pytest\b|"
    r"go\s+test\b|cargo\s+test\b|"
    r"mvn\s+test\b|gradle\s+test\b|./gradlew\s+test\b|"
    r"make\s+(test|build|lint)\b"
    r")",
    re.IGNORECASE,
)


def find_wrapper() -> str:
    candidates = [
        "claude-token-kit/trim_command_output.py",
        ".claude/hooks/trim_command_output.py",
        os.path.join(os.path.dirname(__file__), "trim_command_output.py"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("{}")
        return 0

    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    command = tool_input.get("command") or ""

    if not command or "trim_command_output.py" in command or not NOISY_COMMAND_RE.search(command):
        print("{}")
        return 0

    wrapper = find_wrapper()
    wrapped = (
        f"python3 {shlex.quote(wrapper)} --max-lines 220 -- "
        f"bash -lc {shlex.quote(command)}"
    )

    response = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {"command": wrapped},
        }
    }
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
