# claude-token-kit

Claude Code CLI token 절감을 위한 실험용 도구 모음입니다. 전부 Python/Bash 표준 기능만 사용합니다.

## 구성

- `statusline.sh` — context/cost/model을 status line에 표시
- `trim_command_output.py` — 긴 명령 output을 head/tail/error 중심으로 축약하고 원래 exit code 보존
- `rewrite_bash_for_token_budget.py` — Claude Code `PreToolUse` hook에서 test/build/lint 명령을 wrapper로 감쌈
- `claude_transcript_cost_audit.py` — `~/.claude/projects` JSONL transcript에서 usage/cost field를 찾아 합산
- `settings.example.json` — project `.claude/settings.json` 예시

## 빠른 실험

```bash
python3 claude-token-kit/trim_command_output.py --max-lines 80 -- bash -lc 'seq 1 1000; echo FAIL test_x >&2; exit 1'
python3 claude-token-kit/claude_transcript_cost_audit.py ~/.claude/projects --top 10
```

Claude Code에 적용하려면 `settings.example.json`을 `.claude/settings.json`으로 복사하되, 먼저 작은 repo에서 quoting/exit code를 확인하세요.
