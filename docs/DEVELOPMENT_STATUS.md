# Development Status

기준일: 2026-05-02

## Completed

| PR | 상태 | 구현 내용 | 검증 |
|---|---|---|---|
| PR-001 | 완료 | 저장소 골격, docs, sample test | `tests/test_skeleton.py` |
| PR-002 | 완료 | 공통 스키마, 해시 유틸, JSONL AuditChain | `tests/test_common.py` |
| PR-003 | 완료 | PC profile, mock LLM, mock embedding, RAG search, PII scan benchmark CLI | `tests/test_benchmark.py` |
| PR-004 | 완료 | FastAPI control-plane: node/task/audit/benchmark API | `tests/test_control_plane.py` |
| PR-005 | 완료 | node-agent CLI: register, heartbeat, run-worker, scan-folder, query, performance-doctor | `tests/test_node_agent.py` |
| PR-006 | 완료 | PII/internal/prompt-injection scanner, policy alert audit | `tests/test_policy.py` |
| PR-007 | 완료 | Korean chunker, mock embedding, in-memory vector store, LocalRAGService | `tests/test_rag_runtime.py` |
| PR-008 | 완료 | LLMProvider interface, MockLLMProvider, llama.cpp/Ollama placeholders, policy-gated generation | `tests/test_rag_runtime.py` |
| PR-009 | 완료 | Quarantine Gateway upload/scan/approve/reject/approved registry | `tests/test_quarantine_gateway.py` |
| PR-010 | 완료 | GovSkillRegistry draft/review/approve/reject/deploy and execute gate | `tests/test_control_plane.py` |
| PR-011 | 완료 | local-only e2e: scan, RAG, mock answer, audit verify, benchmark report | `tests/test_e2e.py` |
| PR-012 | 완료 | runbook/status docs and local verification commands | `docs/RUNBOOK.md` |

## Current Verification

```powershell
python -m pytest
```

현재 통과 기준: 59 tests.

## Remaining Development Process

이 저장소는 MVP 기능 골격과 검증 흐름을 갖춘 상태입니다. 제품화까지 남은 과정은 다음 순서가 적합합니다.

1. 운영 환경별 설정 프로필 분리
2. 실제 기관 테스트 corpus 수집 절차 수립
3. persistent vector store 성능 비교
4. 승인된 llama.cpp binary/model registry 설계
5. admin UI 정식 화면화
6. Windows service installer 제작
7. 기관 보안성 검토용 증적 패키지 작성

## Productization Work Added

- 운영 profile config: local/secure/test
- SQLite schema migration marker
- node/task filtering and pagination
- failed task retry state
- node-agent long-running worker loop
- policy evaluation corpus and precision/recall report
- corpus collection procedure/template
- vector store comparison benchmark
- persistent SQLite vector store adapter
- approved local model registry
- approved local llama.cpp execution gate
- quarantine binary base64 upload, MIME guessing, zip entry inspection
- admin status CLI and HTML dashboard
- Windows scheduled-task/service installer
- portable packaging script
- release gate and evidence package script

## Non-Goals Still Preserved

- 대형 모델 분산 샤딩은 MVP 범위가 아닙니다.
- 외부 LLM 호출은 기본 금지입니다.
- 실제 정부 데이터 또는 실제 개인정보는 사용하지 않습니다.
- 승인되지 않은 skill 실행은 금지입니다.
