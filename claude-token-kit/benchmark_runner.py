#!/usr/bin/env python3
"""Claude Code 토큰 절감 벤치마크 자동 실행 runner.

`research/benchmark-plan.md` 의 task set × variant 조합을 비대화형 `claude -p`
호출로 실행하고, `tokens_per_successful_task` 측정에 필요한 컬럼을 CSV 에 적재한다.

사용 예:

```bash
claude-token-kit/benchmark_runner.py \
    --tasks bench/tasks.json --variants bench/variants.json \
    --csv bench/results.csv

claude-token-kit/benchmark_runner.py --tasks bench/tasks.json \
    --variants bench/variants.json --task-id t01 --variant baseline --dry-run
```

Task fixture (`tasks.json`): 각 task 는 다음 필드를 가진다.

```json
[
  {
    "id": "t01",
    "prompt": "Add validation to src/auth/session.ts ...",
    "model": "sonnet",
    "effort": "medium",
    "max_turns": 3,
    "max_budget_usd": 1.0,
    "allowed_tools": ["Read", "Edit", "Bash(npm test*)"],
    "success_command": "npm test -- auth/session",
    "success_cwd": "."
  }
]
```

Variant fixture (`variants.json`): 각 variant 는 `claude -p` 에 추가할 옵션 묶음을 정의한다.

```json
[
  {"name": "baseline", "extra_args": []},
  {"name": "context_hygiene", "extra_args": ["--strict-mcp-config", "--mcp-config", "bench/minimal-mcp.json"]}
]
```

dry-run 모드는 실제 호출은 하지 않고 어떤 명령이 실행될지만 출력한다.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CSV_COLUMNS = [
    "date",
    "claude_version",
    "task_id",
    "variant",
    "model",
    "effort",
    "total_tokens",
    "input_tokens",
    "output_tokens",
    "cache_read",
    "cache_creation",
    "cost_usd",
    "success",
    "corrections",
    "notes",
]

# claude -p --output-format json 의 usage 키 후보. Anthropic SDK 와 Claude Code 의 출력
# 형식이 시간이 지나며 바뀔 수 있어 다중 후보로 best-effort 매칭한다.
USAGE_KEY_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("input_tokens", ("input_tokens",)),
    ("output_tokens", ("output_tokens",)),
    ("cache_read", ("cache_read_input_tokens", "cacheRead")),
    ("cache_creation", ("cache_creation_input_tokens", "cacheCreation")),
)
COST_KEYS = ("total_cost_usd", "cost_usd", "costUSD")


@dataclass
class TaskFixture:
    id: str
    prompt: str
    model: str = "sonnet"
    effort: str = "medium"
    max_turns: int = 3
    max_budget_usd: float | None = 1.0
    allowed_tools: list[str] = field(default_factory=list)
    success_command: str | None = None
    success_cwd: str = "."


@dataclass
class Variant:
    name: str
    extra_args: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    task_id: str
    variant: str
    model: str
    effort: str
    tokens: dict[str, int]
    cost_usd: float
    success: bool
    notes: str
    corrections: int = 0


def parse_tasks(path: Path) -> list[TaskFixture]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit(f"tasks file must be a JSON list: {path}")
    fixtures: list[TaskFixture] = []
    for item in raw:
        if not isinstance(item, dict):
            raise SystemExit(f"task entry must be a JSON object: {item}")
        fixtures.append(TaskFixture(
            id=str(item["id"]),
            prompt=str(item["prompt"]),
            model=str(item.get("model", "sonnet")),
            effort=str(item.get("effort", "medium")),
            max_turns=int(item.get("max_turns", 3)),
            max_budget_usd=item.get("max_budget_usd"),
            allowed_tools=list(item.get("allowed_tools", [])),
            success_command=item.get("success_command"),
            success_cwd=str(item.get("success_cwd", ".")),
        ))
    return fixtures


def parse_variants(path: Path) -> list[Variant]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit(f"variants file must be a JSON list: {path}")
    variants: list[Variant] = []
    for item in raw:
        if not isinstance(item, dict):
            raise SystemExit(f"variant entry must be a JSON object: {item}")
        variants.append(Variant(
            name=str(item["name"]),
            extra_args=[str(a) for a in item.get("extra_args", [])],
        ))
    return variants


def collect_usage(payload: Any) -> tuple[dict[str, int], float]:
    """`claude -p --output-format json` 응답에서 token / cost 합산.

    JSON 구조는 버전별로 다를 수 있어 dict/list 를 재귀적으로 walk 하며
    알려진 키만 합산한다.
    """
    tokens: dict[str, int] = {key: 0 for key, _ in USAGE_KEY_GROUPS}
    cost = 0.0
    stack: list[Any] = [payload]
    seen_cost = False
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for bucket, keys in USAGE_KEY_GROUPS:
                for key in keys:
                    val = cur.get(key)
                    if isinstance(val, bool):
                        continue
                    if isinstance(val, (int, float)):
                        tokens[bucket] += int(val)
                        break
            for key in COST_KEYS:
                val = cur.get(key)
                if isinstance(val, bool):
                    continue
                if isinstance(val, (int, float)) and not seen_cost:
                    cost = float(val)
                    seen_cost = True
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return tokens, cost


def claude_version(claude_bin: str) -> str:
    try:
        proc = subprocess.run([claude_bin, "--version"], text=True, capture_output=True, timeout=5)
        return proc.stdout.strip().splitlines()[0] if proc.stdout else "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def build_claude_argv(claude_bin: str, task: TaskFixture, variant: Variant) -> list[str]:
    argv = [claude_bin, "-p", "--model", task.model, "--effort", task.effort,
            "--max-turns", str(task.max_turns), "--output-format", "json"]
    if task.max_budget_usd is not None:
        argv.extend(["--max-budget-usd", str(task.max_budget_usd)])
    if task.allowed_tools:
        argv.extend(["--allowedTools", ",".join(task.allowed_tools)])
    argv.extend(variant.extra_args)
    argv.append(task.prompt)
    return argv


def run_success_command(task: TaskFixture, project_root: Path) -> tuple[bool, str]:
    """fixture 의 success_command 를 실행한다.

    shell 메타문자 없이 단일 argv 형태만 받아 `shell=False` 로 실행한다. 파이프·리디렉션
    같은 shell 합성이 필요하면 헬퍼 스크립트를 만들어 그 경로를 success_command 로 둔다.
    이렇게 하면 fixture JSON 자체가 shell injection surface 가 되지 않는다.
    """
    if not task.success_command:
        return True, "no success_command configured"
    try:
        argv = shlex.split(task.success_command)
    except ValueError as exc:
        return False, f"success_command parse error: {exc}"
    if not argv:
        return False, "success_command parsed to empty argv"
    cwd = (project_root / task.success_cwd).resolve()
    try:
        proc = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"success_command failed to launch: {exc}"
    return proc.returncode == 0, f"exit={proc.returncode}"


def run_fixture(task: TaskFixture, variant: Variant, claude_bin: str,
                project_root: Path, dry_run: bool) -> RunResult:
    argv = build_claude_argv(claude_bin, task, variant)
    if dry_run:
        return RunResult(
            task_id=task.id, variant=variant.name, model=task.model, effort=task.effort,
            tokens={k: 0 for k, _ in USAGE_KEY_GROUPS}, cost_usd=0.0,
            success=True, notes=f"dry-run: {shlex.join(argv)}",
        )
    try:
        proc = subprocess.run(argv, text=True, capture_output=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return RunResult(
            task_id=task.id, variant=variant.name, model=task.model, effort=task.effort,
            tokens={k: 0 for k, _ in USAGE_KEY_GROUPS}, cost_usd=0.0,
            success=False, notes=f"claude launch failed: {exc}",
        )
    if proc.returncode != 0:
        return RunResult(
            task_id=task.id, variant=variant.name, model=task.model, effort=task.effort,
            tokens={k: 0 for k, _ in USAGE_KEY_GROUPS}, cost_usd=0.0,
            success=False, notes=f"claude exit={proc.returncode}: {proc.stderr[-200:].strip()}",
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return RunResult(
            task_id=task.id, variant=variant.name, model=task.model, effort=task.effort,
            tokens={k: 0 for k, _ in USAGE_KEY_GROUPS}, cost_usd=0.0,
            success=False, notes=f"claude returned non-JSON: {exc.msg}",
        )
    tokens, cost = collect_usage(payload)
    success, success_note = run_success_command(task, project_root)
    return RunResult(
        task_id=task.id, variant=variant.name, model=task.model, effort=task.effort,
        tokens=tokens, cost_usd=cost, success=success, notes=success_note,
    )


def append_csv(csv_path: Path, claude_ver: str, result: RunResult) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if new_file:
            writer.writeheader()
        tokens = result.tokens
        total = sum(tokens.values())
        writer.writerow({
            "date": _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "claude_version": claude_ver,
            "task_id": result.task_id,
            "variant": result.variant,
            "model": result.model,
            "effort": result.effort,
            "total_tokens": total,
            "input_tokens": tokens.get("input_tokens", 0),
            "output_tokens": tokens.get("output_tokens", 0),
            "cache_read": tokens.get("cache_read", 0),
            "cache_creation": tokens.get("cache_creation", 0),
            "cost_usd": f"{result.cost_usd:.6f}",
            "success": "true" if result.success else "false",
            "corrections": result.corrections,
            "notes": result.notes,
        })


def existing_keys(csv_path: Path) -> set[tuple[str, str]]:
    """이미 적재된 (task_id, variant) 조합. resume 시 skip 판정에 사용."""
    if not csv_path.exists():
        return set()
    keys: set[tuple[str, str]] = set()
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tid = row.get("task_id") or ""
            var = row.get("variant") or ""
            if tid and var:
                keys.add((tid, var))
    return keys


def filter_targets(tasks: list[TaskFixture], variants: list[Variant],
                   only_task: str | None, only_variant: str | None) -> list[tuple[TaskFixture, Variant]]:
    targets: list[tuple[TaskFixture, Variant]] = []
    for task in tasks:
        if only_task and task.id != only_task:
            continue
        for variant in variants:
            if only_variant and variant.name != only_variant:
                continue
            targets.append((task, variant))
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tasks", required=True, type=Path, help="task fixture JSON")
    parser.add_argument("--variants", required=True, type=Path, help="variant fixture JSON")
    parser.add_argument("--csv", default=Path("bench/results.csv"), type=Path,
                        help="results CSV path (header is added on first write)")
    parser.add_argument("--task-id", default=None, help="run only the named task id")
    parser.add_argument("--variant", default=None, help="run only the named variant")
    parser.add_argument("--claude-bin", default=os.environ.get("CLAUDE_BIN", "claude"),
                        help="claude CLI executable (default: $CLAUDE_BIN or 'claude')")
    parser.add_argument("--project-root", default=Path("."), type=Path,
                        help="working directory used for success_command (default: cwd)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the claude command without invoking it")
    parser.add_argument("--resume", action="store_true",
                        help="skip (task_id, variant) rows already present in --csv")
    args = parser.parse_args()

    if not args.dry_run and shutil.which(args.claude_bin) is None:
        # claude_bin 이 절대경로면 shutil.which 가 None 일 수 있으므로 추가 검사.
        if not Path(args.claude_bin).exists():
            print(f"claude binary not found: {args.claude_bin}", file=sys.stderr)
            return 2

    tasks = parse_tasks(args.tasks)
    variants = parse_variants(args.variants)
    targets = filter_targets(tasks, variants, args.task_id, args.variant)
    if not targets:
        print("no (task, variant) targets matched the filters", file=sys.stderr)
        return 1

    skip_keys = existing_keys(args.csv) if args.resume else set()
    project_root = args.project_root.resolve()
    claude_ver = "dry-run" if args.dry_run else claude_version(args.claude_bin)

    completed = 0
    for task, variant in targets:
        if (task.id, variant.name) in skip_keys:
            print(f"skip {task.id}/{variant.name} (already in {args.csv})")
            continue
        print(f"run {task.id}/{variant.name} ...", flush=True)
        result = run_fixture(task, variant, args.claude_bin, project_root, args.dry_run)
        append_csv(args.csv, claude_ver, result)
        completed += 1
        status = "ok" if result.success else "FAIL"
        print(f"  {status} tokens={sum(result.tokens.values())} cost=${result.cost_usd:.4f} {result.notes}")
    print(f"completed {completed} run(s); results in {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
