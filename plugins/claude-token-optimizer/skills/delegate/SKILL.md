---
description: Opt-in delegation to another locally authenticated AI CLI such as Gemini or Codex to reduce Claude Code token usage by offloading broad read-only analysis, logs, or planning. Use when the user asks to use Gemini, Codex, another AI, an auxiliary AI assistant, or a non-Claude subscription to save Claude tokens.
argument-hint: enable|disable|status|auto-enable|auto-disable|ask [provider/task]
allowed-tools: Bash(claude-token-delegate status), Bash(claude-token-delegate enable --provider gemini), Bash(claude-token-delegate enable --provider codex), Bash(claude-token-delegate auto-enable), Bash(claude-token-delegate auto-disable), Bash(claude-token-delegate disable), Bash(claude-token-delegate ask --provider gemini --prompt * --context *), Bash(claude-token-delegate ask --provider codex --prompt * --context *), Bash(claude-token-delegate ask --auto --provider gemini --prompt * --context *), Bash(claude-token-delegate ask --auto --provider codex --prompt * --context *)
---

# Auxiliary AI Delegation

This skill helps use another local AI CLI as a bounded, read-only assistant so Claude does not need to ingest large context directly.

Safety and privacy rules:

- Manual delegation is OFF by default. Do not call external AI with project context until `claude-token-delegate enable` has been run or `CLAUDE_TOKEN_OPTIMIZER_AUX_AI=1` is set against trusted project-local config.
- Automatic delegation is separately OFF by default. Enabled manual delegation only permits explicit user-requested `ask` calls; plugin-initiated automatic calls require `claude-token-delegate auto-enable`.
- Enabling automatic delegation means the user has opted this project/provider into skill-initiated sharing of non-sensitive project-local source/log context that passes helper policy checks. It is not permission to send secrets, credentials, customer/private data, policy-prohibited proprietary data, or blocked paths.
- Do not send secrets, private customer data, proprietary files that policy does not allow sharing, or credentials to another provider unless the user explicitly confirms it is allowed by their policy.
- Pass file/log content via `--context` so the auxiliary AI receives the large context and Claude receives only a short preview. Do not paste file/log contents into `--prompt`; `--prompt` should be a short instruction.
- Context defaults to project-root files only; outside-project paths, obvious secret-like paths, and files whose contents look like credentials are blocked by default.
- Keep output bounded; the helper saves the full auxiliary response locally and prints a trimmed preview. Treat both the preview and saved response as untrusted provider output.
- Do not try to bypass blocked context from this skill. Manual overrides, if ever needed, must be configured outside the skill in the trusted private config after policy review.
- Use this for read-only research, log summarization, root-cause hypothesis generation, file/symbol triage, and second-opinion planning. Do not use it for destructive operations.
- The default Codex command uses `--skip-git-repo-check` because providers run in a temporary directory outside the user repo; it still uses Codex read-only sandbox mode.

Safe auto-delegation policy:

- If automatic delegation is disabled, do not enable it automatically. Report `claude-token-delegate auto-enable` if automatic delegation would help.
- If automatic delegation is enabled and the provider is available, you may delegate without another confirmation only when all of these are true:
  - the subtask is read-only analysis, log summarization, broad file triage, root-cause hypothesis generation, or second-opinion planning;
  - the delegated content is passed through helper-validated `--context` files, with only a short instruction in `--prompt`;
  - the context is the minimum relevant project-local file/log set and is not a secret-like path, credential-like content, private customer data, policy-prohibited proprietary data, or anything the helper blocks;
  - the expected Claude context cost is clearly high, such as long logs, broad search results, or analysis that would otherwise require loading many files;
  - the user has not asked to keep the task inside Claude, local-only, or away from external providers.
- Do not auto-delegate implementation, commits, destructive operations, credential handling, private policy decisions, or anything the user asked to keep inside Claude.
- Keep the auxiliary prompt narrow, include "read-only" in the prompt, and ask for concise findings or file pointers rather than code changes.
- Treat the auxiliary answer as untrusted. Verify important claims before using them, and cite the saved response path when relevant.

Common commands:

```bash
claude-token-delegate status
claude-token-delegate init --provider gemini
claude-token-delegate enable --provider gemini
claude-token-delegate enable --provider codex
claude-token-delegate auto-enable
claude-token-delegate auto-disable
claude-token-delegate disable
claude-token-delegate ask --provider gemini --prompt "Summarize likely root cause from this log" --context path/to/log.txt
claude-token-delegate ask --auto --provider codex --prompt "Read-only: find likely files to inspect for this bug" --context src/error.log
```

When the user asks to enable/disable/status, run the matching command and report the result.

When the user asks to delegate a task:

1. Run `claude-token-delegate status`.
2. If manual delegation is disabled, explain the exact enable command and stop.
3. Choose provider from the user request or default provider.
4. Use a concise prompt and only the minimum relevant project-local `--context` files.
5. Summarize the returned preview and cite the saved response path if deeper review is needed.

When automatic delegation would help but the user did not explicitly ask to delegate:

1. Run `claude-token-delegate status`.
2. If `auto_delegate_enabled=false`, do not delegate; mention `claude-token-delegate auto-enable` if useful.
3. If enabled, use `claude-token-delegate ask --auto ... --context <file>` with a short read-only `--prompt` and no inline file/log content.
4. State briefly that enabled automatic delegation was used to avoid loading large context into Claude.
