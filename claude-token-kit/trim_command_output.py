#!/usr/bin/env python3
"""Run a command, preserve exit code, and print a token-budgeted output summary.

Designed for Claude Code Bash tool output. It avoids dumping thousands of log
lines into the conversation while preserving the lines most likely to be useful.
"""
from __future__ import annotations

import argparse
import collections
import re
import subprocess
import sys
from typing import Iterable

ERROR_RE = re.compile(
    r"(FAIL|FAILED|ERROR|Error:|Exception|Traceback|AssertionError|panic:|fatal:|"
    r"segmentation fault|not ok|\bE\s+assert|\[ERROR\]|✗|✖)",
    re.IGNORECASE,
)


def unique_keep_order(lines: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        key = line.rstrip("\n")
        if key not in seen:
            out.append(line)
            seen.add(key)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-lines", type=int, default=220)
    parser.add_argument("--head-lines", type=int, default=40)
    parser.add_argument("--tail-lines", type=int, default=80)
    parser.add_argument("--error-lines", type=int, default=120)
    parser.add_argument("--", dest="dashdash", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("trim_command_output.py: missing command", file=sys.stderr)
        return 2

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        errors="replace",
    )

    all_lines: list[str] = []
    head: list[str] = []
    tail: collections.deque[str] = collections.deque(maxlen=args.tail_lines)
    error_lines: list[str] = []
    total = 0

    assert proc.stdout is not None
    for line in proc.stdout:
        total += 1
        if total <= args.head_lines:
            head.append(line)
        tail.append(line)
        if ERROR_RE.search(line) and len(error_lines) < args.error_lines:
            error_lines.append(line)
        if total <= args.max_lines:
            all_lines.append(line)

    rc = proc.wait()

    if total <= args.max_lines:
        sys.stdout.writelines(all_lines)
    else:
        head_budget = min(args.head_lines, max(1, args.max_lines // 4))
        tail_budget = min(args.tail_lines, max(1, args.max_lines // 3))
        head_out = head[:head_budget]
        tail_out = list(tail)[-tail_budget:]
        remaining = max(0, args.max_lines - len(head_out) - len(tail_out))
        error_out = unique_keep_order(error_lines)[:remaining]

        print(f"[claude-token-kit] output trimmed: {total} lines -> budget about {args.max_lines} log lines")
        print(f"[claude-token-kit] command exit_code={rc}")
        print("\n--- head ---")
        sys.stdout.writelines(head_out)
        if error_out:
            print("\n--- matched error/failure lines ---")
            sys.stdout.writelines(error_out)
        print("\n--- tail ---")
        sys.stdout.writelines(tail_out)
        print("\n[claude-token-kit] rerun the command without trim only if more context is essential.")

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
