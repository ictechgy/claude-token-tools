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
import shutil
import sys

# Reject shell control syntax before wrapping. The wrapper is intended only for a
# single safe argv-style test/build/lint command, not arbitrary shell programs.
SHELL_META_RE = re.compile(r"[;&|<>`$()\n]")
WRAPPER_MARKERS = ("trim_command_output.py", "claude-trim-output")


def find_wrapper() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "claude-trim-output"),
        os.path.join(script_dir, "trim_command_output.py"),
        "claude-token-kit/trim_command_output.py",
        ".claude/hooks/trim_command_output.py",
        "claude-trim-output",
    ]
    for path in candidates:
        if os.path.sep in path or (os.path.altsep and os.path.altsep in path):
            if os.path.exists(path):
                return path
        elif shutil.which(path):
            return path
    return candidates[1]


def split_single_safe_command(command: str) -> list[str] | None:
    if not command.strip() or SHELL_META_RE.search(command):
        return None
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    return argv or None


def is_noisy_command(argv: list[str]) -> bool:
    if not argv:
        return False
    first = argv[0]
    second = argv[1] if len(argv) > 1 else ""
    third = argv[2] if len(argv) > 2 else ""

    if first in {"npm", "pnpm", "yarn", "bun"}:
        return second == "test" or (second == "run" and third in {"test", "build", "lint"})
    if first == "pytest":
        return True
    if first == "python" and len(argv) > 2 and argv[1:3] == ["-m", "pytest"]:
        return True
    if first == "go" and second == "test":
        return True
    if first == "cargo" and second == "test":
        return True
    if first == "mvn" and second == "test":
        return True
    if first in {"gradle", "./gradlew"} and second == "test":
        return True
    if first == "make" and second in {"test", "build", "lint"}:
        return True
    return False


def build_wrapped_command(wrapper: str, argv: list[str]) -> str:
    if wrapper.endswith(".py"):
        prefix = ["python3", wrapper]
    else:
        prefix = [wrapper]
    wrapped_argv = prefix + ["--max-lines", "220", "--"] + argv
    return shlex.join(wrapped_argv)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("{}")
        return 0

    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    command = tool_input.get("command") or ""

    if not command or any(marker in command for marker in WRAPPER_MARKERS):
        print("{}")
        return 0

    argv = split_single_safe_command(command)
    if not argv or not is_noisy_command(argv):
        print("{}")
        return 0

    wrapper = find_wrapper()
    wrapped = build_wrapped_command(wrapper, argv)

    response = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {"command": wrapped},
        }
    }
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
