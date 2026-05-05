#!/usr/bin/env bash
set -euo pipefail

if [[ -t 0 ]]; then
  echo "usage: pass Claude Code statusline JSON on stdin"
  exit 0
fi

input=$(cat)

if ! command -v jq >/dev/null 2>&1; then
  echo "[needs-jq] install jq for Claude token statusline"
  exit 0
fi

jq_get() {
  jq -r "$1 // empty" <<<"$input" 2>/dev/null || true
}

sanitize_status() {
  # Statusline values may come from untrusted workspace metadata; keep one-line printable text.
  LC_ALL=C tr -cd '[:print:]' <<<"$1" | cut -c 1-160
}

model=$(jq_get '.model.display_name')
model=${model:-$(jq_get '.model.id')}
model=${model:-unknown}
model=$(sanitize_status "$model")

context_pct=$(jq_get '.context_window.used_percentage')
if [[ -n "$context_pct" ]]; then
  context_pct=$(printf '%.0f' "$context_pct" 2>/dev/null || sanitize_status "$context_pct")
else
  context_pct="?"
fi

cost=$(jq_get '.cost.total_cost_usd')
if [[ -n "$cost" ]]; then
  cost=$(printf '$%.3f' "$cost" 2>/dev/null || sanitize_status "$cost")
else
  cost='n/a'
fi

cwd=$(jq_get '.workspace.current_dir')
dir=${cwd##*/}
dir=${dir:-.}
dir=$(sanitize_status "$dir")

branch=''
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  b=$(git branch --show-current 2>/dev/null || true)
  if [[ -n "$b" ]]; then
    b=$(sanitize_status "$b")
    branch=" | ${b}"
  fi
fi

# Cache hit rate from the transcript tail (best-effort, fast — reads only the last 256KB).
# Stays empty when transcript is unavailable or python3 fails so the status line never breaks.
cache_label=''
transcript_path=$(jq_get '.transcript_path')
if [[ -n "$transcript_path" && -r "$transcript_path" ]] && command -v python3 >/dev/null 2>&1; then
  rate=$(python3 - "$transcript_path" 2>/dev/null <<'PYEOF' || true
import json
import os
import sys

path = sys.argv[1] if len(sys.argv) > 1 else ""
if not path or not os.path.isfile(path):
    sys.exit(0)

input_tokens = cache_read = cache_creation = 0
TAIL_BYTES = 256 * 1024
MAX_RECORDS = 300
WALK_BUDGET = 5000

try:
    size = os.path.getsize(path)
    read_size = min(size, TAIL_BYTES)
    with open(path, "rb") as fh:
        if size > read_size:
            fh.seek(size - read_size)
        chunk = fh.read(read_size)
    lines = chunk.splitlines()
    if size > read_size and lines:
        # First line in the tail window is likely partial; drop it.
        lines = lines[1:]
    for raw in lines[-MAX_RECORDS:]:
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        stack = [obj]
        steps = 0
        while stack and steps < WALK_BUDGET:
            steps += 1
            cur = stack.pop()
            if isinstance(cur, dict):
                v = cur.get("input_tokens")
                if isinstance(v, int) and not isinstance(v, bool):
                    input_tokens += v
                for k in ("cache_read_input_tokens", "cacheRead"):
                    v = cur.get(k)
                    if isinstance(v, int) and not isinstance(v, bool):
                        cache_read += v
                        break
                for k in ("cache_creation_input_tokens", "cacheCreation"):
                    v = cur.get(k)
                    if isinstance(v, int) and not isinstance(v, bool):
                        cache_creation += v
                        break
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    denom = input_tokens + cache_read + cache_creation
    if denom <= 0:
        sys.exit(0)
    print(f"{cache_read / denom * 100:.0f}")
except Exception:
    sys.exit(0)
PYEOF
  )
  if [[ -n "$rate" ]]; then
    rate=$(sanitize_status "$rate")
    cache_label=" | cache ${rate}%"
  fi
fi

# Keep it one line and cheap: this script runs locally and should not do expensive git status.
echo "[$model] ${dir}${branch} | ctx ${context_pct}% | cost ${cost}${cache_label}"
