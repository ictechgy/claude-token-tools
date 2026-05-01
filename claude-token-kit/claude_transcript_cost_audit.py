#!/usr/bin/env python3
"""Best-effort Claude Code transcript usage auditor.

Claude Code transcript schemas may change. This script recursively scans JSONL
objects for common token/cost fields rather than relying on one exact schema.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

TOKEN_KEYS = {
    "input_tokens": "input",
    "output_tokens": "output",
    "cache_creation_input_tokens": "cache_creation",
    "cache_read_input_tokens": "cache_read",
    "cacheCreation": "cache_creation",
    "cacheRead": "cache_read",
}
COST_KEYS = {"cost_usd", "total_cost_usd", "costUSD"}
MODEL_KEYS = {"model", "model_id", "modelId"}
QUERY_SOURCE_KEYS = {"query_source", "querySource"}


@dataclass
class UsageSummary:
    files: int = 0
    records: int = 0
    tokens: Counter[str] = field(default_factory=Counter)
    cost_usd: float = 0.0
    by_model: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    by_query_source: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))

    @property
    def total_tokens(self) -> int:
        return sum(self.tokens.values())


def iter_jsonl_files(paths: Iterable[str]) -> Iterable[Path]:
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_file() and path.suffix in {".jsonl", ".json"}:
            yield path
        elif path.is_dir():
            yield from path.rglob("*.jsonl")


def walk(obj: Any) -> Iterable[dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


def first_string(obj: dict[str, Any], keys: set[str]) -> str | None:
    for key in keys:
        val = obj.get(key)
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            nested = val.get("id") or val.get("name")
            if isinstance(nested, str):
                return nested
    return None


def add_usage(summary: UsageSummary, root: Any) -> None:
    root_model = None
    root_query_source = None
    if isinstance(root, dict):
        root_model = first_string(root, MODEL_KEYS)
        root_query_source = first_string(root, QUERY_SOURCE_KEYS)

    for d in walk(root):
        local_tokens: Counter[str] = Counter()
        for raw_key, bucket in TOKEN_KEYS.items():
            val = d.get(raw_key)
            if isinstance(val, bool):
                continue
            if isinstance(val, (int, float)):
                local_tokens[bucket] += int(val)

        # OpenTelemetry-style records sometimes use {name, value, attributes.type}.
        name = d.get("name") or d.get("metric")
        if name == "claude_code.token.usage":
            value = d.get("value") or d.get("sum") or d.get("count")
            attrs = d.get("attributes") or {}
            token_type = attrs.get("type", "unknown") if isinstance(attrs, dict) else "unknown"
            if isinstance(value, (int, float)):
                local_tokens[str(token_type)] += int(value)

        if local_tokens:
            summary.tokens.update(local_tokens)
            model = first_string(d, MODEL_KEYS) or root_model or "unknown"
            query_source = first_string(d, QUERY_SOURCE_KEYS) or root_query_source or "unknown"
            summary.by_model[model].update(local_tokens)
            summary.by_query_source[query_source].update(local_tokens)

        for key in COST_KEYS:
            val = d.get(key)
            if isinstance(val, bool):
                continue
            if isinstance(val, (int, float)):
                summary.cost_usd += float(val)


def scan(paths: list[str]) -> UsageSummary:
    summary = UsageSummary()
    for file in iter_jsonl_files(paths):
        summary.files += 1
        try:
            with file.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    summary.records += 1
                    add_usage(summary, obj)
        except OSError:
            continue
    return summary


def print_counter(title: str, counter: Counter[str], top: int) -> None:
    print(f"\n{title}")
    for key, val in counter.most_common(top):
        print(f"  {key:24s} {val:12d}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", default=[os.path.expanduser("~/.claude/projects")])
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = scan(args.paths)

    if args.json:
        print(json.dumps({
            "files": summary.files,
            "records": summary.records,
            "total_tokens": summary.total_tokens,
            "tokens": dict(summary.tokens),
            "cost_usd_observed": summary.cost_usd,
            "by_model": {k: dict(v) for k, v in summary.by_model.items()},
            "by_query_source": {k: dict(v) for k, v in summary.by_query_source.items()},
        }, indent=2, sort_keys=True))
        return 0

    print("Claude Code transcript usage audit")
    print(f"files_scanned={summary.files} records={summary.records}")
    print(f"observed_total_tokens={summary.total_tokens}")
    if summary.cost_usd:
        print(f"observed_cost_usd={summary.cost_usd:.4f}")
    print_counter("Token buckets", summary.tokens, args.top)

    model_totals = Counter({model: sum(tokens.values()) for model, tokens in summary.by_model.items()})
    print_counter("By model", model_totals, args.top)

    source_totals = Counter({src: sum(tokens.values()) for src, tokens in summary.by_query_source.items()})
    print_counter("By query_source", source_totals, args.top)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
