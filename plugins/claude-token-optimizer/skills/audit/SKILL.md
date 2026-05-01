---
description: Audit local Claude Code transcript usage and summarize likely token hotspots. Use when the user asks where Claude Code tokens are going or wants evidence before optimizing.
argument-hint: [optional transcript path]
disable-model-invocation: true
---

# Claude Token Audit

Run a best-effort transcript audit, then interpret the result conservatively.

Default command:

```bash
claude-token-audit ~/.claude/projects --top 20
```

If the user supplies a path, audit that path instead:

```bash
claude-token-audit "$ARGUMENTS" --top 20
```

Report:

- observed token buckets: input, output, cache_read, cache_creation;
- model distribution;
- query_source distribution: main, subagent, auxiliary;
- top likely causes and one safe next experiment.

Caveat: Claude Code transcript schemas can change. Treat this as an operational signal, not billing authority. For billing authority, use Claude Console, cloud-provider billing, or configured OpenTelemetry metrics.
