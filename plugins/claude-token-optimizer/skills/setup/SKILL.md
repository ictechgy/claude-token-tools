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
   - optional Gemini/Codex manual auxiliary AI delegation,
   - separate optional automatic delegation for safe, non-sensitive, project-local read-only triage or long-log analysis, bound to the selected provider.
3. If the user wants the recommended project-local setup, run:

```bash
claude-token-setup --yes
```

4. If they want manual auxiliary AI too, only enable it after explicit confirmation because selected context may be sent to another provider:

```bash
claude-token-setup --yes --aux-provider gemini
# or
claude-token-setup --yes --aux-provider codex
```

5. If they also want plugin skills to auto-delegate safe read-only context, require an additional explicit opt-in:

```bash
claude-token-setup --yes --aux-provider gemini --auto-delegate
# or
claude-token-setup --yes --aux-provider codex --auto-delegate
```

Safety:

- Do not modify global `~/.claude/settings.json`.
- Prefer project-local `.claude/settings.json`.
- Never enable manual auxiliary AI implicitly.
- Never enable automatic delegation implicitly. Manual delegation enablement is not automatic-delegation consent, and rerunning setup without `--auto-delegate` clears automatic-delegation consent.
- Automatic delegation still must not send blocked paths, secrets, credentials, customer/private data, or policy-prohibited proprietary data.
- After applying, run `claude-token-diet scan .` to show remaining gaps.
