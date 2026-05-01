#!/usr/bin/env python3
"""Opt-in auxiliary AI delegation for Claude Code token reduction.

This helper lets a Claude Code session offload read-only research, log analysis,
or broad planning to another locally authenticated AI CLI (for example Gemini or
Codex). It is intentionally disabled by default and prints only a bounded
preview so the answer does not bloat Claude's context.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

CONFIG_ENV = "CLAUDE_TOKEN_OPTIMIZER_CONFIG"
ENABLED_ENV = "CLAUDE_TOKEN_OPTIMIZER_AUX_AI"
DEFAULT_CONFIG_PATH = Path(".claude-token-optimizer/config.json")
DEFAULT_DELEGATION_DIR = Path(".claude-token-optimizer/delegations")

DEFAULT_CONFIG: dict[str, Any] = {
    "aux_ai_enabled": False,
    "default_provider": "gemini",
    "max_output_chars": 4000,
    "context_max_chars": 60000,
    "delegation_dir": str(DEFAULT_DELEGATION_DIR),
    "providers": {
        "gemini": {
            "enabled": True,
            "description": "Google Gemini CLI in non-interactive plan/read-only mode",
            "command": [
                "gemini",
                "--approval-mode",
                "plan",
                "--output-format",
                "text",
                "-p",
                "Read the full delegated task from stdin. Answer concisely.",
            ],
            "stdin": True,
        },
        "codex": {
            "enabled": True,
            "description": "OpenAI Codex CLI in non-interactive read-only sandbox mode",
            "command": ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-"],
            "stdin": True,
        },
    },
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(base))
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def config_path() -> Path:
    raw = os.environ.get(CONFIG_ENV)
    return Path(raw).expanduser() if raw else DEFAULT_CONFIG_PATH


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        with path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Failed to read config {path}: {exc}")
    if not isinstance(loaded, dict):
        raise SystemExit(f"Config {path} must be a JSON object")
    return deep_merge(DEFAULT_CONFIG, loaded)


def save_config(config: dict[str, Any]) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
        f.write("\n")
    return path


def env_enabled_override() -> bool | None:
    raw = os.environ.get(ENABLED_ENV)
    if raw is None:
        return None
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "off", "disabled"}:
        return False
    return None


def is_enabled(config: dict[str, Any]) -> bool:
    override = env_enabled_override()
    if override is not None:
        return override
    return bool(config.get("aux_ai_enabled", False))


def provider_config(config: dict[str, Any], provider: str | None) -> tuple[str, dict[str, Any]]:
    name = provider or str(config.get("default_provider") or "gemini")
    providers = config.get("providers") or {}
    item = providers.get(name)
    if not isinstance(item, dict):
        raise SystemExit(f"Unknown provider '{name}'. Known providers: {', '.join(sorted(providers))}")
    if not item.get("enabled", True):
        raise SystemExit(f"Provider '{name}' is disabled in {config_path()}")
    return name, item


def executable_available(command: list[str]) -> bool:
    return bool(command and shutil.which(command[0]))


def render_command(command: list[str], prompt: str) -> list[str]:
    return [part.replace("{prompt}", prompt) for part in command]


def build_aux_prompt(task: str, contexts: list[tuple[str, str]], max_output_chars: int) -> str:
    parts = [
        "You are an auxiliary AI helping a Claude Code session reduce Claude token usage.",
        "Operate as a read-only research/planning assistant. Do not modify files, run destructive actions, or ask for credentials.",
        f"Return a concise answer under {max_output_chars} characters.",
        "Prioritize: relevant files/symbols, root-cause hypotheses, commands to run, risks, and exact next steps for Claude.",
        "If context is insufficient, say the smallest additional file/symbol/log snippet needed.",
        "",
        "TASK:",
        task.strip(),
    ]
    if contexts:
        parts.extend(["", "CONTEXT FILES:"])
        for path, content in contexts:
            parts.extend([f"--- {path} ---", content.rstrip(), f"--- end {path} ---"])
    return "\n".join(parts).strip() + "\n"


def read_contexts(paths: list[str], context_max_chars: int) -> tuple[list[tuple[str, str]], list[str]]:
    contexts: list[tuple[str, str]] = []
    warnings: list[str] = []
    remaining = max(0, context_max_chars)
    for raw in paths:
        path = Path(raw).expanduser()
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            warnings.append(f"could not read context {raw}: {exc}")
            continue
        if len(content) > remaining:
            if remaining <= 0:
                warnings.append(f"skipped {raw}: context budget exhausted")
                continue
            warnings.append(f"truncated {raw}: {len(content)} -> {remaining} chars")
            content = content[:remaining] + "\n[truncated by claude-token-delegate]\n"
        contexts.append((str(path), content))
        remaining -= len(content)
    return contexts, warnings


def trim_for_stdout(text: str, limit: int) -> tuple[str, bool]:
    if limit <= 0:
        return "", bool(text)
    if len(text) <= limit:
        return text, False
    marker = f"\n\n[trimmed: {len(text)} chars]\n"
    keep = max(0, limit - len(marker))
    return text[:keep].rstrip() + marker, True


def save_response(config: dict[str, Any], provider: str, response: str, task: str, rc: int) -> Path:
    out_dir = Path(str(config.get("delegation_dir") or DEFAULT_DELEGATION_DIR)).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"{stamp}-{provider}.md"
    content = [
        "# Auxiliary AI delegation response",
        "",
        f"- provider: `{provider}`",
        f"- exit_code: `{rc}`",
        f"- created_at: `{_dt.datetime.now().isoformat(timespec='seconds')}`",
        f"- task_chars: `{len(task)}`",
        "",
        "## Response",
        "",
        response.rstrip(),
        "",
    ]
    path.write_text("\n".join(content), encoding="utf-8")
    return path


def cmd_status(_: argparse.Namespace) -> int:
    config = load_config()
    override = env_enabled_override()
    effective = is_enabled(config)
    print(f"config_path={config_path()}")
    print(f"aux_ai_enabled={str(effective).lower()}")
    if override is not None:
        print(f"enabled_source=env:{ENABLED_ENV}")
    else:
        print("enabled_source=config")
    print(f"default_provider={config.get('default_provider')}")
    print(f"max_output_chars={config.get('max_output_chars')}")
    print("providers:")
    for name, item in sorted((config.get("providers") or {}).items()):
        command = item.get("command") or []
        available = executable_available(command) if isinstance(command, list) else False
        enabled = item.get("enabled", True)
        exe = command[0] if command else ""
        print(f"  - {name}: enabled={str(bool(enabled)).lower()} available={str(available).lower()} executable={exe}")
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    config = load_config()
    config["aux_ai_enabled"] = True
    if args.provider:
        provider_config(config, args.provider)
        config["default_provider"] = args.provider
    if args.max_output_chars:
        config["max_output_chars"] = args.max_output_chars
    path = save_config(config)
    print(f"enabled auxiliary AI delegation in {path}")
    print(f"default_provider={config.get('default_provider')}")
    print("privacy_note=Only delegate context you are allowed to share with the selected external AI provider.")
    return 0


def cmd_disable(_: argparse.Namespace) -> int:
    config = load_config()
    config["aux_ai_enabled"] = False
    path = save_config(config)
    print(f"disabled auxiliary AI delegation in {path}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    config = load_config()
    if args.provider:
        provider_config(config, args.provider)
        config["default_provider"] = args.provider
    path = save_config(config)
    print(f"wrote config template to {path}")
    print("aux_ai_enabled=false")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    config = load_config()
    if not args.force and not is_enabled(config):
        print(
            "auxiliary AI delegation is disabled. Run `claude-token-delegate enable --provider gemini|codex` "
            "or set CLAUDE_TOKEN_OPTIMIZER_AUX_AI=1 to opt in.",
            file=sys.stderr,
        )
        return 3

    provider, item = provider_config(config, args.provider)
    command_template = item.get("command")
    if not isinstance(command_template, list) or not all(isinstance(x, str) for x in command_template):
        print(f"provider '{provider}' has invalid command template", file=sys.stderr)
        return 2
    if not executable_available(command_template):
        print(f"provider '{provider}' executable not found: {command_template[0]}", file=sys.stderr)
        return 127

    task = args.prompt or ""
    if args.prompt_file:
        try:
            task = Path(args.prompt_file).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"failed to read prompt file: {exc}", file=sys.stderr)
            return 2
    if not task and not sys.stdin.isatty():
        task = sys.stdin.read()
    if not task.strip():
        print("missing prompt; use --prompt, --prompt-file, or stdin", file=sys.stderr)
        return 2

    max_output_chars = args.max_output_chars or int(config.get("max_output_chars") or 4000)
    context_max_chars = args.context_max_chars or int(config.get("context_max_chars") or 60000)
    contexts, warnings = read_contexts(args.context or [], context_max_chars)
    prompt = build_aux_prompt(task, contexts, max_output_chars)
    command = render_command(command_template, prompt)

    if args.dry_run:
        print(f"provider={provider}")
        print("command=" + json.dumps(command, ensure_ascii=False))
        print(f"stdin={str(bool(item.get('stdin', False))).lower()}")
        print(f"prompt_chars={len(prompt)}")
        for warning in warnings:
            print(f"warning={warning}")
        return 0

    proc = subprocess.run(
        command,
        input=prompt if item.get("stdin", False) else None,
        text=True,
        capture_output=True,
        cwd=os.getcwd(),
    )
    combined = proc.stdout
    if proc.stderr.strip():
        combined = combined.rstrip() + "\n\n[stderr]\n" + proc.stderr.strip() + "\n"

    saved = save_response(config, provider, combined, task, proc.returncode)
    preview, trimmed = trim_for_stdout(combined, max_output_chars)

    print(f"provider={provider}")
    print(f"exit_code={proc.returncode}")
    print(f"response_saved={saved}")
    print(f"trimmed={str(trimmed).lower()}")
    for warning in warnings:
        print(f"warning={warning}")
    print("--- auxiliary response preview ---")
    print(preview.rstrip())
    print("--- end auxiliary response preview ---")
    return proc.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Opt-in Gemini/Codex delegation helper for Claude Code token reduction."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="Show enabled state and provider availability")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("init", help="Write a disabled config template")
    p.add_argument("--provider", choices=["gemini", "codex"], help="Default provider to record")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("enable", help="Enable auxiliary AI delegation in project-local config")
    p.add_argument("--provider", choices=["gemini", "codex"], help="Default provider")
    p.add_argument("--max-output-chars", type=int, help="Preview char budget printed back to Claude")
    p.set_defaults(func=cmd_enable)

    p = sub.add_parser("disable", help="Disable auxiliary AI delegation")
    p.set_defaults(func=cmd_disable)

    p = sub.add_parser("ask", help="Ask the enabled auxiliary AI and print a bounded preview")
    p.add_argument("--provider", choices=["gemini", "codex"], help="Provider to use")
    p.add_argument("--prompt", help="Prompt text")
    p.add_argument("--prompt-file", help="Read prompt text from file")
    p.add_argument("--context", action="append", default=[], help="Context file to send to auxiliary AI, not Claude")
    p.add_argument("--max-output-chars", type=int, help="Preview char budget printed back to Claude")
    p.add_argument("--context-max-chars", type=int, help="Total context chars sent to auxiliary AI")
    p.add_argument("--dry-run", action="store_true", help="Print rendered command metadata without executing")
    p.add_argument("--force", action="store_true", help="Run even when config is disabled")
    p.set_defaults(func=cmd_ask)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
