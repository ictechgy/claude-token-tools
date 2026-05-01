# Claude Code 토큰 절감 벤치마크 계획

목표: 절감 기법을 “느낌”이 아니라 **성공한 작업당 token/cost**로 평가한다.

## 1. 측정 지표

필수:

- total tokens
- input tokens
- output/thinking tokens
- cache read tokens
- cache creation tokens
- cost USD 또는 subscription usage delta
- model, effort, query_source(main/subagent/auxiliary)
- 작업 성공 여부: tests pass, build pass, reviewer accepted, human accepted 등

보조:

- tool call 수
- 읽은 파일 수
- Bash output line 수
- `/context` 상위 카테고리
- human correction 횟수
- wall time

## 2. Task set

최소 12개 작업을 고정한다.

| 카테고리 | 예시 | 성공 기준 |
|---|---|---|
| 작은 수정 | 단일 파일 validation 추가 | targeted test pass |
| 중간 bugfix | 실패 test root cause 수정 | failing test -> pass |
| 탐색 | auth flow 요약 | reviewer factual check |
| code review | PR diff 리뷰 | seeded issue recall |
| 로그 분석 | 긴 CI log root cause | 정확한 failing command/file |
| migration | 파일 5개 API 변경 | build/typecheck pass |
| 문서 작업 | README 갱신 | spec coverage |
| UI/visual | screenshot 기준 수정 | visual diff/수동 승인 |

## 3. 실험군

A. Baseline

- 현재 사용자 기본 Claude Code 설정 그대로
- interactive long session 허용

B. Context hygiene

- 작업별 `/clear`
- prompt에 scope/검증 명시
- `/compact` focus 지시 사용

C. Model/effort routing

- `sonnet + effort medium`
- 어려운 planning만 `opusplan`

D. Output-budget hooks

- test/build/log 명령을 `trim_command_output.py`로 감싸기

E. Context diet

- `CLAUDE.md` 200줄 이하
- 긴 workflow는 skill로 이동
- unused MCP off
- deny generated/large dirs

F. Subagent isolation

- noisy 탐색/로그 분석만 subagent로 격리
- agent team 미사용

## 4. 실행 프로토콜

1. Claude Code 버전 기록: `claude --version`
2. 각 task 전 `/clear` 여부를 실험군에 맞춰 고정
3. prompt text를 파일로 저장해 반복 사용
4. 각 run 후 `/usage` 결과 또는 telemetry를 저장
5. 실패한 run은 실패로 기록하고, 재시도 token까지 포함한 “성공까지 총 비용”도 별도 계산
6. prompt cache 영향을 분리하려면 warm run/cold run을 나눠 2회씩 실행

## 5. 판정 기준

- 품질이 baseline과 같거나 더 좋은 경우만 절감으로 인정
- primary metric: `tokens_per_successful_task`
- secondary metric: `human_corrections_per_task`
- guardrail: 실패율이 10%p 이상 상승하면 해당 절감 기법은 task class별 opt-in으로 격하

## 6. 기대 결과 템플릿

```csv
date,claude_version,task_id,variant,model,effort,total_tokens,input_tokens,output_tokens,cache_read,cache_creation,cost_usd,success,corrections,notes
2026-05-01,2.x,t01,baseline,opus,xhigh,0,0,0,0,0,0,true,0,
```
