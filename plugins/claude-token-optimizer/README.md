# claude-token-optimizer

A Claude Code plugin with skills and helper commands for reducing token usage.

## Skills

After installation, use:

```text
/claude-token-optimizer:optimize
/claude-token-optimizer:audit
```

## Helper commands

The plugin exposes executables in `bin/` while enabled:

```bash
claude-token-audit ~/.claude/projects --top 20
claude-trim-output --max-lines 120 -- npm test
claude-token-statusline
claude-token-rewrite-bash
```

## Local test before publishing

From the marketplace repository root:

```bash
claude --plugin-dir ./plugins/claude-token-optimizer
```

Then run:

```text
/claude-token-optimizer:optimize
```

For marketplace testing:

```text
/plugin marketplace add ./
/plugin install claude-token-optimizer@claude-token-tools
```
