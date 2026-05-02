# Claude Code 토큰 절감 리서치

조사일: 2026-05-01

이 저장소는 Claude Code CLI의 토큰 사용량과 불필요한 context 사용을 줄이기 위한 리서치와 실험용 워크스페이스입니다.

## 산출물

- `research/claude-code-token-reduction.md` — 핵심 리서치 보고서와 우선순위별 실행안
- `research/benchmark-plan.md` — 절감 효과를 검증하기 위한 벤치마크 설계
- `claude-token-kit/` — statusline, 출력 축약/민감정보 제거, transcript 감사, 설정 스캔, 대용량 Read guard, 보조 AI 위임 도구
- `plugins/claude-token-optimizer/` — Claude Code 플러그인 배포본

## 5분 적용 가이드

1. Claude Code 안에서 `/usage`, `/context`, `/model`, `/effort`를 먼저 확인합니다.
2. 작업이 바뀔 때는 `/clear`를 사용하고, 긴 작업은 `/compact <보존할 내용>`으로 요약합니다.
3. 기본 모델은 `sonnet`을 쓰고, 설계·복잡한 추론에만 `opusplan`을 사용합니다. 단순 작업은 낮은 `/effort`로 충분합니다.
4. `CLAUDE.md`에는 핵심만 남기고, 긴 워크플로 지침은 skills/custom commands로 분리합니다.
5. MCP 서버를 최소화하고, `gh`, `rg`, `jq`, `aws`, `gcloud` 같은 CLI를 우선 사용합니다.
6. 테스트/빌드 로그는 hook이나 wrapper로 줄여 실패 구간만 Claude에 전달합니다.
7. subagent는 노이즈가 많은 리서치나 로그 분석을 분리할 때만 사용하고, agent team은 토큰 사용량이 배수로 늘 수 있으므로 작게 유지합니다.

## Claude Code 플러그인 배포

이 저장소에는 Claude Code plugin marketplace용 구조도 포함되어 있습니다.

- Marketplace 파일: `.claude-plugin/marketplace.json`
- 플러그인: `plugins/claude-token-optimizer/`
- 설치 후 사용할 수 있는 주요 skill:
  - `/claude-token-optimizer:setup`
  - `/claude-token-optimizer:optimize`
  - `/claude-token-optimizer:audit`
  - `/claude-token-optimizer:delegate`

로컬 테스트:

```bash
claude --plugin-dir ./plugins/claude-token-optimizer
```

이 저장소 루트에서 marketplace 설치 테스트:

```text
/plugin marketplace add ./
/plugin install claude-token-optimizer@claude-token-tools
```

GitHub에 배포한 뒤 사용자는 다음처럼 추가할 수 있습니다.

```text
/plugin marketplace add YOUR_GITHUB_USER/YOUR_REPO
/plugin install claude-token-optimizer@claude-token-tools
```

플러그인은 설치만으로 전역 hook을 자동으로 활성화하지 않습니다. 프로젝트 단위 opt-in 예시는 `plugins/claude-token-optimizer/examples/settings.example.json`을 참고하세요.

## 설치 후 설정 마법사

명령어를 외우기보다 Claude Code 안에서 setup skill을 실행하는 방식을 권장합니다.

```text
/claude-token-optimizer:setup
```

일반 shell에서는 플러그인 `bin/`이 `PATH`에 자동으로 추가되지 않을 수 있습니다. 이 저장소 루트에서 로컬 테스트할 때는 경로를 명시하세요.

```bash
./plugins/claude-token-optimizer/bin/claude-token-setup --plan
./plugins/claude-token-optimizer/bin/claude-token-setup --yes
```

개발 중 짧은 명령으로 실행하고 싶다면 현재 shell에만 `PATH`를 추가하세요.

```bash
export PATH="$PWD/plugins/claude-token-optimizer/bin:$PATH"
claude-token-setup --plan
```

설정 마법사는 deny rules, statusline, Bash trim/sanitize hook, large Read guard, model/effort defaults, 선택적 Gemini/Codex delegation을 대화형으로 선택하게 합니다. 설정은 project-local `.claude/settings.json`에 병합되며, global Claude 설정은 수정하지 않습니다.

참고: 이 플러그인 소스 저장소는 테스트 중 생기는 `.claude/` 등 로컬 Claude runtime state를 `.gitignore`로 제외합니다. 실제 사용자 프로젝트에서는 팀 공용 `.claude/settings.json`을 커밋할지, 로컬 전용으로 둘지 정책에 맞게 결정하세요.

## 주요 helper 사용 예시

프로젝트 위생 스캔:

```bash
./plugins/claude-token-optimizer/bin/claude-token-diet scan .
```

대용량 파일은 전체 Read 대신 symbol 단위로 읽기:

```bash
./plugins/claude-token-optimizer/bin/claude-read-symbol path/to/file.py TargetSymbol
```

secret이 포함될 수 있는 검색·diff output 정제:

```bash
./plugins/claude-token-optimizer/bin/claude-sanitize-output -- rg -n "TOKEN|SECRET" .
./plugins/claude-token-optimizer/bin/claude-sanitize-output -- git diff
```

`claude-sanitize-output -- <command>` 형태의 wrapper mode는 감싼 명령의 exit code를 그대로 보존합니다. `git diff | claude-sanitize-output` 같은 pipe mode도 임시 정리에 쓸 수 있지만, shell `pipefail` 없이는 producer의 exit code를 알 수 없습니다.

긴 테스트/빌드 로그 축약:

```bash
./plugins/claude-token-optimizer/bin/claude-trim-output --max-lines 120 -- npm test
```

## 선택 기능: 보조 AI delegation

Gemini CLI나 Codex CLI를 사용할 수 있다면, 광범위한 탐색이나 긴 로그 분석을 보조 AI에 위임해 Claude 토큰 소비를 줄일 수 있습니다. 이 기능의 기본값은 OFF입니다.

Claude Code 안에서:

```text
/claude-token-optimizer:delegate enable --provider gemini
/claude-token-optimizer:delegate auto-enable
/claude-token-optimizer:delegate ask --provider gemini --prompt "Summarize this failing test log" --context ./log.txt
/claude-token-optimizer:delegate disable
```

shell에서 직접 테스트하려면 플러그인 bin 경로를 명시하거나 `PATH`를 추가한 뒤 실행하세요.

```bash
./plugins/claude-token-optimizer/bin/claude-token-delegate status
./plugins/claude-token-optimizer/bin/claude-token-delegate enable --provider codex
./plugins/claude-token-optimizer/bin/claude-token-delegate auto-enable
```

보조 AI를 사용하면 선택한 context가 외부 provider로 전송될 수 있습니다. secrets, 고객 데이터, 사내 비공개 자료는 정책상 허용되는 경우에만 위임하세요. 보조 AI의 전체 응답은 `.claude-token-optimizer/` 아래에 저장되며, Claude에는 짧은 preview만 출력됩니다.

자동 위임은 provider별로 별도 동의가 필요한 opt-in 기능입니다. 수동 delegation을 켠 뒤 `claude-token-delegate auto-enable`을 실행한 경우에만 plugin skill이 긴 로그 요약, 넓은 파일 triage, 원인 가설 생성, second-opinion planning처럼 Claude context를 크게 쓰는 안전한 read-only 작업을 현재/default provider에 자동 위임할 수 있습니다. 자동 호출은 `--provider`를 생략해 helper가 승인된 provider만 사용하게 하고, helper가 검증한 `--context` 파일만 전달합니다. `--prompt`에는 짧은 지시만 넣고, blocked/sensitive/customer/policy-prohibited data를 피하며, 보조 AI 출력은 검증 전까지 untrusted로 취급하세요.

## 라이선스

Copyright 2026 jinhongan. Apache License 2.0으로 배포됩니다. 자세한 내용은 [LICENSE](LICENSE)와 [NOTICE](NOTICE)를 참고하세요.
