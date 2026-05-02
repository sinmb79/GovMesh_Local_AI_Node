# GovMesh Local AI Node

정부·공공기관 환경을 가정한 **로컬 우선 AI 노드 MVP**입니다. 낮은 성능의 Windows 중심 업무 PC를 안전한 내부 AI 노드로 전환해, 문서 색인, 한국어 RAG, 개인정보 탐지, 감사로그, 벤치마크, 검역형 반입, 승인형 로컬 모델 실행을 하나의 운영 흐름으로 묶습니다.

> 정부 AI의 첫 제품은 단순 챗봇이 아니라, 닫힌 망과 낮은 사양 PC에서도 신뢰할 수 있는 “일하는 방식”이어야 합니다.

## 왜 필요한가

공공기관 AI 도입의 병목은 대형 모델 하나가 없어서만은 아닙니다.

- 정부망은 외부 연결이 제한됩니다.
- 업무 PC 사양은 제각각이고 낮은 경우가 많습니다.
- 행정 지식은 문서, 사람, 시스템, 관행 속에 흩어져 있습니다.
- 외부 LLM 호출은 보안, 비용, 감사, 책임 문제가 큽니다.
- AI 답변은 근거와 정책 차단 이유를 설명할 수 있어야 합니다.

GovMesh는 이 문제를 “PC 여러 대를 거대한 모델로 묶자”가 아니라, **각 PC가 안전하게 문서를 색인하고, 민감정보를 걸러내고, 근거 기반 답변을 만들며, 모든 과정을 감사 가능하게 남기는 로컬 AI 운영체계**로 풀어냅니다.

## 핵심 기능

- **Control Plane**: 노드 등록, heartbeat, 작업 큐, 감사 이벤트, 벤치마크 기록
- **Node Agent CLI**: 성능 진단, 폴더 스캔, RAG 질의, worker loop
- **Policy Scanner**: 주민등록번호, 전화번호, 이메일, 계좌 후보, 내부문서 표기, 프롬프트 인젝션 후보 탐지
- **Local RAG**: 한국어 chunking, mock embedding, in-memory/SQLite vector store
- **Runtime Adapter**: mock LLM, 승인형 llama.cpp provider gate, Ollama placeholder
- **Quarantine Gateway**: 외부 파일 upload → scan → approve/reject → approved registry
- **Skill Registry**: draft → review → approve → deploy, 미승인 skill 실행 차단
- **Admin Dashboard**: 운영 상태 JSON/HTML 확인
- **Benchmark Harness**: PC profile, mock LLM, RAG, PII scan, vector store 비교
- **Release Gate**: fake PII 범위, localhost 기본값, 필수 파일, 테스트 검증

## 보안 원칙

- 실제 정부 데이터 사용 금지
- 실제 개인정보 사용 금지
- 외부 네트워크 호출 기본 금지
- 로컬 API 기본 bind는 `127.0.0.1`
- 정책 검사 전 LLM/provider 호출 금지
- 감사로그에 raw PII 저장 금지
- 승인되지 않은 model/skill 실행 금지
- 외부 반입물은 Quarantine Gateway를 거쳐야 함

## 빠른 실행

```powershell
python -m pytest
python -m packages.govmesh_benchmark run --sample samples/documents --out reports/benchmarks
python -m apps.node_agent performance-doctor
python -m apps.node_agent scan-folder --path samples/documents
python -m apps.node_agent query --sample samples/documents --question "근거 문서 기준으로 요약해줘"
```

## 서버 실행

서버를 직접 실행할 때는 로컬 토큰을 먼저 지정합니다.

```powershell
$env:GOVMESH_API_TOKEN="replace-with-local-dev-token"
$env:GOVMESH_AUDIT_SIGNING_KEY="replace-with-local-audit-key"
```

Control Plane:

```powershell
python -m apps.control_plane
```

Quarantine Gateway:

```powershell
python -m apps.quarantine_gateway
```

Admin UI:

```powershell
python -m apps.admin_ui --control-plane http://127.0.0.1:8787 --serve
```

## 검증

현재 로컬 검증 기준:

```powershell
python -m pytest
python scripts/release_gate.py
.\scripts\smoke_test.ps1
```

작성 시점 기준 테스트는 `59 passed`입니다.

## 저장소 구조

```text
apps/
  control_plane/          FastAPI control-plane
  node_agent/             local node CLI and worker
  quarantine_gateway/     import quarantine workflow
  admin_ui/               operator dashboard
packages/
  govmesh_common/         schemas, config, audit chain, skill registry
  govmesh_policy/         PII/internal/prompt-injection scanner
  govmesh_rag/            chunker, embeddings, vector stores, RAG service
  govmesh_runtime/        provider interface and model registry
  govmesh_benchmark/      benchmark runner and reports
docs/
  RUNBOOK.md              실행 가이드
  DEVELOPMENT_STATUS.md   개발 상태
  SECURITY_MODEL.md       보안 모델
  HARDENING_NOTES.md      보안 보완 사항과 남은 개발 과정
  RELEASE_CHECKLIST.md    릴리즈 검증
```

## 프로젝트 특징

- 폐쇄망·저사양 PC라는 공공기관 현실을 기본 제약으로 둔 설계
- 대형 모델 분산 추론보다 문서 색인, 보안 필터, RAG, 감사로그를 먼저 제품화
- 외부 반입·모델 실행·skill 실행을 승인 흐름으로 통제
- 테스트와 release gate로 “안전하게 작동한다”는 증거를 남김
- 실제 데이터 없이도 로컬에서 바로 실행할 수 있는 sample 기반 MVP

## 한계와 다음 단계

- 실제 기관 corpus와 보안성 검토는 별도 절차가 필요합니다.
- llama.cpp 연동은 승인된 local executable/model registry를 전제로 합니다.
- Admin UI는 MVP dashboard이며, 정식 운영 화면은 추가 개발 대상입니다.
- Windows service 설치 스크립트는 실제 `node_id` 등록 후 사용합니다.

## 문서

- [실행 가이드](docs/RUNBOOK.md)
- [보안 모델](docs/SECURITY_MODEL.md)
- [보안 보완 노트](docs/HARDENING_NOTES.md)
- [기관 corpus 절차](docs/CORPUS_COLLECTION.md)
- [릴리즈 체크리스트](docs/RELEASE_CHECKLIST.md)

## 라이선스

MIT License
