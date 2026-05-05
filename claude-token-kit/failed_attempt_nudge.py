#!/usr/bin/env python3
"""Claude Code PostToolUse hook: 동일 Bash 명령이 연속 실패하면 /clear 권유.

같은 명령으로 두 번 연속 실패하면 그 흐름은 컨텍스트 오염을 일으키고 캐시 무효화를
누적시킨다. 이 hook 은 그 패턴을 감지해 다음 turn 의 추가 컨텍스트로 짧은 권유 문구를
주입한다 (블록하지 않음).

상태 저장 위치: 프로젝트 로컬 `.claude-token-optimizer/failures-<session>.json`.
session_id 가 없는 경우 단일 파일에 기록한다. 트래킹 깊이는 5 회로 제한해 디스크
사용을 무시할 수 있게 한다.

Install via `.claude/settings.json` PostToolUse hook with matcher "Bash".
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path

STATE_DIR = Path(".claude-token-optimizer")
STATE_FILE_TEMPLATE = "failures-{session}.json"
MAX_TRACKED = 5
MIN_CONSECUTIVE = 2

NUDGE_TEXT = (
    "동일 Bash 명령이 이 세션에서 연속 두 번 실패했습니다. "
    "실패 시도가 누적되면 컨텍스트가 오염되고 prompt cache 도 매번 무효화됩니다. "
    "방향을 바꾸기 전에 `/clear` 또는 `/compact focus on …` 으로 세션을 정리하고, "
    "재현 명령·기대 결과·금지 사항을 한 번 더 prompt 에 명시한 뒤 다시 시도하세요."
)

def normalize_command(command: str) -> str:
    """명령을 stable fingerprint 텍스트로 축약한다.

    "방향" 만 보존하기 위해 모든 `-`/`--` 옵션을 제거하고 positional 토큰 중 처음
    2 개(보통 `command primary_target`)만 남긴다. 예:
    - `pytest tests/auth.py`, `pytest tests/auth.py -v`,
      `pytest tests/auth.py -k login` 모두 같은 fingerprint = "pytest tests/auth.py".
    - `pytest tests/billing.py` 는 다른 fingerprint.

    한계:
    - flag value 가 positional 으로 잘못 잡혀도 첫 2 개만 보므로 영향이 거의 없다.
    - 같은 작업을 여러 대상에 나눠 실행하면 (`pytest A` 후 `pytest B`) 다른 fp 로 본다.
    이 단순화는 도구별 옵션 목록 유지비용 없이 운영 의도("같은 방향으로 두 번 실패하면
    권유") 와 가장 잘 맞도록 의도적으로 거칠게 잡았다.
    """
    try:
        argv = shlex.split(command)
    except ValueError:
        argv = command.split()
    positional = [tok for tok in argv if not tok.startswith("-")]
    return " ".join(positional[:2])


def fingerprint(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:16]


def load_entries(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def save_entries(path: Path, entries: list[dict]) -> None:
    # setup_wizard 가 .claude-token-optimizer/ 를 0o700 으로 생성하므로 본 hook 은
    # 디렉터리 모드를 다시 만지지 않고 파일 모드만 0o600 으로 잠근다.
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(entries, ensure_ascii=False)
    path.write_text(payload, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def safe_session_label(session_id: str | None) -> str:
    if not session_id:
        return "unknown"
    return re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)[:64] or "unknown"


def extract_exit_code(tool_response: dict) -> int | None:
    for key in ("exitCode", "exit_code", "returncode"):
        value = tool_response.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("{}")
        return 0
    if not isinstance(payload, dict):
        print("{}")
        return 0

    tool_name = payload.get("tool_name") or payload.get("toolName")
    if tool_name != "Bash":
        print("{}")
        return 0

    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    tool_response = payload.get("tool_response") or payload.get("toolResponse") or {}
    if not isinstance(tool_input, dict) or not isinstance(tool_response, dict):
        print("{}")
        return 0

    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        print("{}")
        return 0

    exit_code = extract_exit_code(tool_response)
    if exit_code is None or exit_code == 0:
        print("{}")
        return 0

    session = safe_session_label(payload.get("session_id") or payload.get("sessionId"))
    state_path = STATE_DIR / STATE_FILE_TEMPLATE.format(session=session)
    fp = fingerprint(normalize_command(command))

    entries = load_entries(state_path)
    entries.append({"fp": fp})
    if len(entries) > MAX_TRACKED:
        entries = entries[-MAX_TRACKED:]
    try:
        save_entries(state_path, entries)
    except OSError:
        # 상태 저장 실패해도 실행은 막지 않는다 (best-effort nudge).
        pass

    consecutive = 0
    for entry in reversed(entries):
        if entry.get("fp") == fp:
            consecutive += 1
        else:
            break
    if consecutive < MIN_CONSECUTIVE:
        print("{}")
        return 0

    response = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": NUDGE_TEXT,
        }
    }
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
