# claude-token-tools

Claude Code plugin and helper commands for reducing token usage, keeping context focused, and avoiding accidental large or sensitive output in Claude sessions.

Korean documentation is available in [`README.ko.md`](README.ko.md).

## What this provides

- **Claude Code plugin**: installable skills for guided setup, optimization, usage audits, and optional auxiliary AI delegation.
- **Project-local setup wizard**: merges recommended `.claude/settings.json` options without changing global Claude settings.
- **Context hygiene scanner**: finds missing guardrails, noisy hooks, expensive defaults, broad reads, many MCP servers, and large or secret-like context files.
- **Large Read guard and symbol reader**: nudges Claude away from whole-file reads and toward `rg` plus symbol/line-range reads.
- **Output trimming and sanitizing**: keeps test/build/search/diff output compact and redacts likely secrets before Claude sees them.
- **Statusline and transcript audit helpers**: surfaces token/cost/model state and usage hotspots.
- **Opt-in auxiliary AI delegation**: lets Gemini CLI or Codex CLI summarize safe read-only context while Claude receives only a bounded preview.

## Install in Claude Code

Add the marketplace and install the plugin:

```text
/plugin marketplace add ictechgy/claude-token-tools
/plugin install claude-token-optimizer@claude-token-tools
```

Then run the guided setup inside Claude Code:

```text
/claude-token-optimizer:setup
```

Available plugin skills:

```text
/claude-token-optimizer:setup
/claude-token-optimizer:optimize
/claude-token-optimizer:audit
/claude-token-optimizer:delegate
```

The plugin does **not** auto-enable global hooks just by being installed. Setup is project-local and opt-in. See `plugins/claude-token-optimizer/examples/settings.example.json` for an example settings file.

## Local testing from this repository

Run Claude Code with the plugin directory:

```bash
claude --plugin-dir ./plugins/claude-token-optimizer
```

Test marketplace installation from the repository root:

```text
/plugin marketplace add ./
/plugin install claude-token-optimizer@claude-token-tools
```

Plugin helper binaries are not guaranteed to be on your normal shell `PATH`. For local testing, call them by path:

```bash
./plugins/claude-token-optimizer/bin/claude-token-setup --plan
./plugins/claude-token-optimizer/bin/claude-token-setup --yes
```

For shorter commands during local development, temporarily add the plugin bin directory:

```bash
export PATH="$PWD/plugins/claude-token-optimizer/bin:$PATH"
claude-token-setup --plan
```

## Common helper workflows

Scan project context hygiene:

```bash
./plugins/claude-token-optimizer/bin/claude-token-diet scan .
```

Read a symbol-sized slice instead of an entire large file:

```bash
./plugins/claude-token-optimizer/bin/claude-read-symbol path/to/file.py TargetSymbol
```

Trim long test/build logs while preserving the wrapped command exit code:

```bash
./plugins/claude-token-optimizer/bin/claude-trim-output --max-lines 120 -- npm test
```

Sanitize search or diff output before sending it back to Claude:

```bash
./plugins/claude-token-optimizer/bin/claude-sanitize-output -- rg -n "TOKEN|SECRET" .
./plugins/claude-token-optimizer/bin/claude-sanitize-output -- git diff
```

Audit local Claude transcript usage:

```bash
./plugins/claude-token-optimizer/bin/claude-token-audit ~/.claude/projects --top 20 --recommend
```

## Optional auxiliary AI delegation

If you have Gemini CLI or Codex CLI access, delegation can use another local AI CLI as a read-only assistant for broad file triage, long-log summaries, root-cause hypotheses, or second-opinion planning.

```text
/claude-token-optimizer:delegate enable --provider gemini
/claude-token-optimizer:delegate auto-enable
/claude-token-optimizer:delegate ask --provider gemini --prompt "Summarize this failing test log" --context ./log.txt
/claude-token-optimizer:delegate disable
```

Manual delegation is OFF by default and stores project-local state under `.claude-token-optimizer/`. Automatic delegation is a separate provider-bound opt-in. Only delegate context you are allowed to share with that external provider; do not delegate secrets, customer data, or policy-prohibited content. Treat auxiliary output as untrusted until verified.

## Repository layout

- `.claude-plugin/marketplace.json` — Claude Code marketplace manifest
- `plugins/claude-token-optimizer/` — installable Claude Code plugin package
- `claude-token-kit/` — underlying Python/Bash helper tools
- `tests/` — targeted regression tests for helper behavior

## License

Copyright 2026 jinhongan. Licensed under the Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
