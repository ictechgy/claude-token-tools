# Claude Code CLI 토큰 사용량 절감 리서치

조사일: 2026-05-01  
범위: Claude Code CLI의 토큰/비용 절감, 컨텍스트 관리, 모델/effort 선택, 훅/스킬/MCP/subagent 운영, 측정 체계.

> 안전 경계: 여기서의 “수단과 방법”은 합법적이고 약관을 위반하지 않는 엔지니어링/운영 최적화로 제한한다. 계정 공유, 결제/한도 우회, 비인가 프록시, leaked source 악용, 취약점 이용은 제외한다.

## 결론 먼저

Claude Code 토큰 비용은 대부분 “매 요청마다 다시 읽히는 컨텍스트”와 “긴 tool output”에서 커진다. 따라서 최우선 절감 전략은 모델 자체보다 **컨텍스트 예산 관리**다.

우선순위:

1. **측정부터 고정**: `/usage`, `/context`, status line, OpenTelemetry/Console로 session/model/query_source/type별 토큰을 기록.
2. **세션 위생**: 작업 전환 시 `/clear`; 장기 작업은 `/compact`에 보존 지시를 붙이고, `/rename` + `/resume`으로 회수.
3. **모델/effort 라우팅**: 기본은 `sonnet`; 설계/아키텍처만 `opus` 또는 `opusplan`; 단순 작업은 `/effort low|medium`; `max`는 실험 통과 전 금지.
4. **컨텍스트 diet**: `CLAUDE.md`는 핵심만, 긴 절차는 skills/custom commands로; 큰 파일/빌드 산출물은 permissions deny; MCP는 필요한 것만.
5. **tool output 절단**: 테스트/빌드/로그는 실패 주변과 tail/head만 전달. 훅으로 Bash 명령을 wrapper에 태우면 반복 절감 효과가 크다.
6. **subagent는 격리용, team은 절제**: noisy 탐색/문서/로그 분석은 subagent에 보내 main context를 보호. 반대로 agent team은 각 인스턴스가 별도 context를 갖기 때문에 큰 폭으로 늘 수 있다.
7. **비대화형 batch는 budget guard**: `claude -p --max-turns --max-budget-usd --output-format json`으로 자동화하고, per-file fan-out은 작은 prompt와 제한된 tools로.

## 1. 비용 구조와 실제로 커지는 지점

공식 문서 기준으로 Claude Code의 context window에는 대화 기록, 파일 내용, 명령 출력, `CLAUDE.md`, auto memory, loaded skills, system instructions가 들어간다. 즉 “말을 한 번 더 거는 것”이 현재 context 전체를 다시 처리하는 비용이 될 수 있다.

토큰을 키우는 대표 원인:

- 긴 session을 `/clear` 없이 계속 이어감
- 광범위한 “이 코드베이스 개선해줘”류 prompt로 많은 파일 탐색 유도
- 테스트/빌드/로그 output 전체를 그대로 context에 투입
- `CLAUDE.md`/memory/skill 설명/MCP가 많아 startup context가 무거움
- Opus/high/max effort를 모든 작업에 사용
- subagent/team을 비용 격리 목적 없이 남발
- MCP 서버 다수 활성화 또는 verbose tool definitions/results
- 1M context를 “공짜 메모리”처럼 사용해 대형 session 유지

## 2. P0: 즉시 적용할 운영 규칙

### 2.1 매 session 첫 화면에 비용/컨텍스트를 띄운다

- Claude Code 안에서 `/usage`로 token/cost를 확인한다.
- `/context`로 어떤 범주가 context를 잡아먹는지 확인한다.
- status line을 구성해 model/context/cost를 항상 보이게 한다. status line script는 로컬에서 실행되어 API token을 쓰지 않는다.

이 repo에는 `claude-token-kit/statusline.sh` 예제가 있다.

### 2.2 작업 단위를 끊는다

- 관련 없는 작업으로 넘어가면 `/clear`.
- 같은 작업 안에서 context가 커졌다면 `/compact focus on <테스트 결과, 변경 파일, 남은 TODO>`처럼 보존 대상을 지정한다.
- session을 찾기 쉽게 `/rename <task-name>` 후 `/clear`, 필요 시 `/resume`.
- 두 번 이상 같은 방향으로 실패하면 failed attempts가 context pollution이 되므로 `/clear` 후 배운 내용을 짧게 새 prompt로 재작성한다.

### 2.3 prompt를 좁힌다

나쁜 prompt:

```text
이 코드베이스 개선해줘.
```

좋은 prompt:

```text
src/auth/session.ts의 refresh token 만료 처리만 조사해줘.
먼저 관련 파일 3개 이하를 읽고, 수정 전 계획을 10줄 이하로 써줘.
검증은 npm test -- auth/session 으로 해줘.
```

핵심은 “범위, 읽을 후보, 산출물, 검증 명령, 금지사항”을 같이 주는 것이다.

### 2.4 model/effort 기본값을 낮춘다

권장 routing:

- 일상 coding/debugging: `sonnet`
- 아키텍처/어려운 추론: `opus` 또는 `opusplan`
- 단순 검색/요약/subagent: `haiku` 또는 낮은 effort
- 비용 민감 작업: `/effort medium`부터 시작
- 반복/스크립트 automation: `--max-turns`, `--max-budget-usd`를 둔다
- `max` effort: 벤치마크로 품질 이득이 확인된 task class에만 임시 사용

`opusplan`은 plan mode에서는 Opus, 실행에서는 Sonnet을 쓰는 hybrid이므로 “설계는 비싸게, 구현은 싸게”라는 기본 전략과 잘 맞는다.

### 2.5 1M context는 절감 장치가 아니다

1M context는 긴 작업을 가능하게 하지만, 큰 context를 계속 유지하면 매 요청 처리량이 커진다. plan/계정에 따라 extra usage가 붙을 수도 있다. 대형 context가 습관적으로 켜져 있다면 다음을 실험한다.

```bash
export CLAUDE_CODE_DISABLE_1M_CONTEXT=1
```

단, 1M이 꼭 필요한 대형 repo migration은 별도 benchmark 후 허용한다.

### 2.6 prompt caching은 끄지 않는다

Claude Code는 prompt caching을 자동 사용한다. 디버깅 목적이 아니면 `DISABLE_PROMPT_CACHING*` 환경변수를 설정하지 않는다.

## 3. P1: 컨텍스트 diet 설계

### 3.1 `CLAUDE.md`를 “항상 필요한 200줄 이하”로 유지

공식 비용 문서는 `CLAUDE.md`가 session 시작 때 context에 들어가므로, workflow-specific 장문 지침은 skills로 옮기라고 권한다. 운영 규칙:

- 항상 필요한 repo 규칙만 `CLAUDE.md`에 둔다.
- PR review, migration, release, DB 작업 같은 긴 절차는 `.claude/skills/*/SKILL.md` 또는 custom command로 분리한다.
- 자동 로딩이 필요 없는 skill은 `disable-model-invocation: true`로 설명조차 startup context에서 뺀다.
- skill 내용은 invocation 후 conversation에 남고 compaction 후 일부 재주입되므로, skill 자체도 짧게 만든다.

### 3.2 큰 디렉터리/파일은 읽지 못하게 한다

`.claude/settings.json`의 `permissions.deny`로 build artifacts, dependency directories, generated files, huge logs를 차단한다.

예시:

```json
{
  "permissions": {
    "deny": [
      "Read(./node_modules/**)",
      "Read(./dist/**)",
      "Read(./build/**)",
      "Read(./coverage/**)",
      "Read(./tmp/**)",
      "Read(./logs/**)",
      "Read(./.env)",
      "Read(./.env.*)"
    ]
  }
}
```

민감 파일 차단은 보안과 토큰 절감이 동시에 된다.

### 3.3 MCP를 “기본 off, 필요할 때 on”으로

공식 문서상 MCP tool definitions는 deferred이지만, 그래도 tool name과 사용 후 결과는 context/비용에 영향을 준다.

규칙:

- `gh`, `aws`, `gcloud`, `sentry-cli`, `rg`, `jq` 같은 CLI가 있으면 MCP보다 먼저 쓴다.
- `/mcp`로 활성 서버를 점검하고 현재 작업과 무관한 서버는 끈다.
- automation에서는 `--strict-mcp-config --mcp-config ./minimal-mcp.json`로 최소 MCP만 로드한다.

### 3.4 code intelligence를 이용해 “파일 통째 읽기”를 줄인다

LSP/code intelligence가 가능하면 정의/참조/타입 에러를 tool로 좁혀서 찾게 하라. 큰 파일 여러 개를 읽는 것보다 symbol 기반 이동이 싸다.

## 4. P1: tool output 절단

테스트/빌드 output은 수천~수만 줄이 되기 쉽다. Claude에게 필요한 것은 보통 다음뿐이다.

- 실패한 테스트명
- assertion/error stack 주변
- exit code
- 마지막 100~200줄
- 재현 명령

이 repo의 예제:

- `claude-token-kit/trim_command_output.py`: 명령 실행 후 head/tail/error 주변만 출력하고 원래 exit code 보존
- `claude-token-kit/rewrite_bash_for_token_budget.py`: Claude Code `PreToolUse` hook에서 test/build/lint 명령을 wrapper로 감쌈
- `claude-token-kit/settings.example.json`: project settings 예시

설치 실험:

```bash
mkdir -p .claude/hooks
cp claude-token-kit/trim_command_output.py .claude/hooks/
cp claude-token-kit/rewrite_bash_for_token_budget.py .claude/hooks/
cp claude-token-kit/settings.example.json .claude/settings.json
```

주의: wrapper가 shell quoting을 바꾸므로 먼저 작은 repo에서 test command 3~5개로 검증한다.

## 5. P2: subagent와 team 비용 정책

subagent는 별도 context window를 가져 main conversation을 보호한다. noisy 작업에는 좋다.

좋은 사용:

- “이 5천 줄 로그에서 실패 root cause만 요약”
- “외부 문서 3개를 읽고 핵심 API contract만 반환”
- “repo 탐색 결과 파일 후보 5개만 반환”

나쁜 사용:

- 작은 질문마다 subagent spawn
- main prompt에 긴 spawn 지시를 붙임
- 여러 agent가 같은 파일/로그를 중복 탐색
- agent team을 기본값처럼 켬

공식 비용 문서는 agent team plan mode가 표준 session 대비 약 7배 token을 쓸 수 있다고 설명한다. 따라서 team은 병렬 가치가 token 배수를 넘을 때만 사용한다.

## 6. P2: 자동화/비대화형 비용 가드

반복 batch 작업은 interactive session보다 `claude -p`로 고립시키는 편이 context 누수를 막기 쉽다.

예시:

```bash
claude -p \
  --model sonnet \
  --effort medium \
  --max-turns 3 \
  --max-budget-usd 1.00 \
  --output-format json \
  "Review src/foo.ts only. Return JSON with findings[]."
```

파일 단위 migration은 다음 식으로 fan-out한다.

```bash
while read -r file; do
  claude -p --model sonnet --effort medium --max-turns 2 \
    --allowedTools "Read,Edit,Bash(npm test*)" \
    "Migrate only @$file. Do not inspect unrelated files. Return OK or FAIL."
done < files.txt
```

단, prompt cache warm-up, 병렬 요청 한도, 실패 재시도 비용까지 포함해 측정해야 한다.

## 7. P2: 측정/감사 체계

### 7.1 OpenTelemetry/Console

Claude Code는 `claude_code.token.usage`, `claude_code.cost.usage` 같은 metric을 내보낼 수 있고, token type은 `input`, `output`, `cacheRead`, `cacheCreation`으로 쪼갤 수 있다. model, query_source(main/subagent/auxiliary), effort로 segment하면 어떤 레버가 효과적인지 보인다.

### 7.2 Transcript 감사

Claude Code session은 로컬 JSONL transcript로 저장된다. 구조는 버전별로 달라질 수 있으니, 이 repo의 `claude-token-kit/claude_transcript_cost_audit.py`는 알려진 usage/cost field를 재귀적으로 찾아 합산한다.

```bash
python3 claude-token-kit/claude_transcript_cost_audit.py ~/.claude/projects --top 20
```

목표:

- token이 큰 session top N 찾기
- output token vs input token vs cache creation/read 비율 확인
- model/effort/subagent 사용 패턴 확인
- tool output이 많은 session 후보 찾기

## 8. 비추천/위험한 방법

| 방법 | 판정 | 이유 |
|---|---:|---|
| prompt caching 비활성화 | 대부분 금지 | 비용/성능 최적화 장치를 끄는 것 |
| 구버전 Claude Code 고정 | 신중 | 보안/호환성/과금 보고 버그 위험. regression 재현용으로만 |
| auto-compact 무조건 끄기 | 신중 | 일부 workflow에서 품질이 좋아질 수 있으나 context 폭증 위험. benchmark 필요 |
| leaked source 기반 패치/우회 | 금지 | 법적/보안/공급망 리스크 |
| 계정/결제/한도 우회 | 금지 | 약관/법적 리스크 |
| 무차별 agent team | 금지에 가까움 | 각 agent가 별도 context와 token을 씀 |
| 거대 `CLAUDE.md`/skill 모음 | 금지에 가까움 | startup/reinjection context bloat |

## 9. 실험 가설과 목표 절감률

공식 문서는 정량 절감률을 보장하지 않는다. 다만 비용 원인상 다음 가설을 세울 수 있다.

- 세션 전환 `/clear` + prompt scoping: 긴 작업 혼합 session에서 20~50% 입력 token 절감 가능
- test/build output wrapper: 실패 로그가 긴 repo에서 tool-result context 50~90% 절감 가능
- `CLAUDE.md`/skill diet: startup context가 큰 사용자에게 session당 고정 입력 token 절감
- Sonnet/effort medium 기본화: output/thinking token 절감, 품질 영향은 task class별 측정 필요
- subagent 격리: main context 증가 억제. 총 token은 늘 수도 있으므로 “main session 품질/반복 감소”까지 같이 측정

절감률은 반드시 `research/benchmark-plan.md` 방식으로 “성공한 task당 token” 기준으로 검증한다.

## 10. 권장 baseline config

프로젝트별 `.claude/settings.json` 예시:

```json
{
  "model": "sonnet",
  "effortLevel": "medium",
  "statusLine": {
    "type": "command",
    "command": "bash claude-token-kit/statusline.sh"
  },
  "permissions": {
    "deny": [
      "Read(./node_modules/**)",
      "Read(./dist/**)",
      "Read(./build/**)",
      "Read(./coverage/**)",
      "Read(./logs/**)",
      "Read(./tmp/**)",
      "Read(./.env)",
      "Read(./.env.*)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 claude-token-kit/rewrite_bash_for_token_budget.py"
          }
        ]
      }
    ]
  }
}
```

환경변수 예시:

```bash
# 기본 모델 alias를 명시적으로 싸게 둔다.
export ANTHROPIC_MODEL=sonnet
export CLAUDE_CODE_EFFORT_LEVEL=medium

# 1M context가 습관적 context bloat를 유발하면 실험적으로 비활성화.
# export CLAUDE_CODE_DISABLE_1M_CONTEXT=1

# prompt caching은 끄지 않는다.
unset DISABLE_PROMPT_CACHING DISABLE_PROMPT_CACHING_HAIKU DISABLE_PROMPT_CACHING_SONNET DISABLE_PROMPT_CACHING_OPUS
```

## 11. 근거 자료

공식 자료를 1차 근거로 사용했다.

- Claude Code 비용 관리: https://code.claude.com/docs/en/costs
- Claude Code 작동 방식/context window: https://code.claude.com/docs/en/how-claude-code-works
- Context window walkthrough: https://code.claude.com/docs/en/context-window
- Best practices: https://code.claude.com/docs/en/best-practices
- Model configuration/effort/1M/prompt caching: https://code.claude.com/docs/en/model-config
- Commands reference: https://code.claude.com/docs/en/commands
- Status line: https://code.claude.com/docs/en/statusline
- Subagents: https://code.claude.com/docs/en/sub-agents
- Hooks reference: https://code.claude.com/docs/en/hooks
- Monitoring usage: https://code.claude.com/docs/en/monitoring-usage
- CLI reference: https://code.claude.com/docs/en/cli-reference
- Tools reference/LSP/Monitor: https://code.claude.com/docs/en/tools-reference
- Claude Help Center usage/limits: https://support.claude.com/en/articles/14552983-models-usage-and-limits-in-claude-code
