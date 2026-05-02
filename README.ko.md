# claude-token-tools

Claude Code 세션에서 토큰 사용량을 줄이고, context를 작게 유지하며, 크거나 민감한 output이 Claude에 그대로 들어가는 일을 줄이기 위한 Claude Code 플러그인과 helper 도구 모음입니다.

English documentation is available in [`README.md`](README.md).

## 제공 기능

- **Claude Code 플러그인**: 설정, 최적화, 사용량 감사, 선택적 보조 AI 위임을 위한 installable skill을 제공합니다.
- **Project-local 설정 마법사**: global Claude 설정은 건드리지 않고, 추천 `.claude/settings.json` 옵션을 프로젝트에 병합합니다.
- **Context hygiene 스캐너**: 누락된 guardrail, noisy hook, 비싼 기본값, broad read, 많은 MCP server, 크거나 secret-like인 context 파일을 점검합니다.
- **대용량 Read guard와 symbol reader**: 큰 파일 전체 Read 대신 `rg`와 symbol/line-range 읽기를 사용하도록 안내합니다.
- **Output trim/sanitize**: 테스트·빌드·검색·diff output을 줄이고, Claude에 보이기 전에 secret-like 값을 redact합니다.
- **Statusline과 transcript audit helper**: token/cost/model 상태와 사용량 hotspot을 확인합니다.
- **Opt-in 보조 AI delegation**: Gemini CLI나 Codex CLI가 안전한 read-only context를 요약하게 하고, Claude에는 제한된 preview만 전달합니다.

## Claude Code에서 설치

Marketplace를 추가하고 플러그인을 설치합니다.

```text
/plugin marketplace add ictechgy/claude-token-tools
/plugin install claude-token-optimizer@claude-token-tools
```

설치 후 Claude Code 안에서 설정 마법사를 실행하세요.

```text
/claude-token-optimizer:setup
```

사용할 수 있는 plugin skill:

```text
/claude-token-optimizer:setup
/claude-token-optimizer:optimize
/claude-token-optimizer:audit
/claude-token-optimizer:delegate
```

플러그인은 설치만으로 전역 hook을 자동으로 활성화하지 않습니다. 설정은 project-local이며 opt-in 방식입니다. 예시는 `plugins/claude-token-optimizer/examples/settings.example.json`을 참고하세요.

## 이 저장소에서 로컬 테스트

Plugin directory로 Claude Code를 실행합니다.

```bash
claude --plugin-dir ./plugins/claude-token-optimizer
```

저장소 루트에서 marketplace 설치를 테스트합니다.

```text
/plugin marketplace add ./
/plugin install claude-token-optimizer@claude-token-tools
```

Plugin helper binary가 일반 shell의 `PATH`에 자동으로 추가된다고 보장할 수 없습니다. 로컬 테스트에서는 경로를 직접 명시하세요.

```bash
./plugins/claude-token-optimizer/bin/claude-token-setup --plan
./plugins/claude-token-optimizer/bin/claude-token-setup --yes
```

개발 중 짧은 명령으로 실행하고 싶다면 현재 shell에만 plugin bin 경로를 추가하세요.

```bash
export PATH="$PWD/plugins/claude-token-optimizer/bin:$PATH"
claude-token-setup --plan
```

## 자주 쓰는 helper workflow

프로젝트 context hygiene 스캔:

```bash
./plugins/claude-token-optimizer/bin/claude-token-diet scan .
```

대용량 파일 전체 대신 symbol 단위로 읽기:

```bash
./plugins/claude-token-optimizer/bin/claude-read-symbol path/to/file.py TargetSymbol
```

긴 테스트/빌드 로그를 줄이고 감싼 명령의 exit code 보존:

```bash
./plugins/claude-token-optimizer/bin/claude-trim-output --max-lines 120 -- npm test
```

Claude에 전달하기 전에 검색·diff output 정제:

```bash
./plugins/claude-token-optimizer/bin/claude-sanitize-output -- rg -n "TOKEN|SECRET" .
./plugins/claude-token-optimizer/bin/claude-sanitize-output -- git diff
```

로컬 Claude transcript 사용량 감사:

```bash
./plugins/claude-token-optimizer/bin/claude-token-audit ~/.claude/projects --top 20 --recommend
```

## 선택 기능: 보조 AI delegation

Gemini CLI나 Codex CLI를 사용할 수 있다면, 넓은 파일 triage, 긴 로그 요약, 원인 가설 생성, second-opinion planning 같은 read-only 작업을 다른 로컬 AI CLI에 맡길 수 있습니다.

```text
/claude-token-optimizer:delegate enable --provider gemini
/claude-token-optimizer:delegate auto-enable
/claude-token-optimizer:delegate ask --provider gemini --prompt "Summarize this failing test log" --context ./log.txt
/claude-token-optimizer:delegate disable
```

수동 delegation은 기본 OFF이며, project-local 상태를 `.claude-token-optimizer/` 아래에 저장합니다. 자동 delegation은 provider별로 별도 opt-in이 필요합니다. 외부 provider와 공유해도 되는 context만 위임하세요. secrets, 고객 데이터, 정책상 금지된 내용은 위임하지 말고, 보조 AI 출력은 검증 전까지 untrusted로 취급하세요.

## 저장소 구조

- `.claude-plugin/marketplace.json` — Claude Code marketplace manifest
- `plugins/claude-token-optimizer/` — installable Claude Code plugin package
- `claude-token-kit/` — 기반 Python/Bash helper 도구
- `tests/` — helper 동작을 검증하는 targeted regression tests

## 라이선스

Copyright 2026 jinhongan. Apache License 2.0으로 배포됩니다. 자세한 내용은 [LICENSE](LICENSE)와 [NOTICE](NOTICE)를 참고하세요.
