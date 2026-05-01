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

model=$(jq_get '.model.display_name')
model=${model:-$(jq_get '.model.id')}
model=${model:-unknown}

context_pct=$(jq_get '.context_window.used_percentage')
if [[ -n "$context_pct" ]]; then
  context_pct=$(printf '%.0f' "$context_pct" 2>/dev/null || echo "$context_pct")
else
  context_pct="?"
fi

cost=$(jq_get '.cost.total_cost_usd')
if [[ -n "$cost" ]]; then
  cost=$(printf '$%.3f' "$cost" 2>/dev/null || echo "$cost")
else
  cost='n/a'
fi

cwd=$(jq_get '.workspace.current_dir')
dir=${cwd##*/}
dir=${dir:-.}

branch=''
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  b=$(git branch --show-current 2>/dev/null || true)
  if [[ -n "$b" ]]; then
    branch=" | ${b}"
  fi
fi

# Keep it one line and cheap: this script runs locally and should not do expensive git status.
echo "[$model] ${dir}${branch} | ctx ${context_pct}% | cost ${cost}"
