---
description: Interactive or guided project setup for Claude Code token optimizer settings. Use when the user asks to install, configure, setup, enable hooks, or choose token-saving options interactively.
argument-hint: [plan|apply|options]
allowed-tools: Bash(claude-token-setup *), Bash(claude-token-diet scan *)
---

# Claude Token Optimizer Setup

Goal: help the user configure this plugin without memorizing helper commands.

Default flow:

1. Run a read-only plan first:

```bash
claude-token-setup --plan
```

2. Explain the options briefly:
   - deny bulky/sensitive reads,
   - token/cost statusline,
   - Bash trim + grep/diff sanitizer hook,
   - large Read guard,
   - missing model/effort defaults,
   - optional Gemini/Codex auxiliary AI delegation.
3. If the user wants the recommended project-local setup, run:

```bash
claude-token-setup --yes
```

4. If they want auxiliary AI too, only enable it after explicit confirmation because selected context may be sent to another provider:

```bash
claude-token-setup --yes --aux-provider gemini
# or
claude-token-setup --yes --aux-provider codex
```

Safety:

- Do not modify global `~/.claude/settings.json`.
- Prefer project-local `.claude/settings.json`.
- Never enable auxiliary AI implicitly.
- After applying, run `claude-token-diet scan .` to show remaining gaps.
