# Hardening Notes

이 문서는 GovMesh Local AI Node MVP에 반영한 보안 보완 사항과 아직 남은 개발 과정을 정리합니다.

## 반영한 보완 사항

### 1. API 인증과 역할 분리

- Control Plane과 Quarantine Gateway에 `Authorization: Bearer <token>` 기반 인증 정책을 추가했습니다.
- 운영 서버 진입점(`python -m apps.control_plane`, `python -m apps.quarantine_gateway`)은 환경 변수 토큰이 없으면 시작하지 않습니다.
- 역할은 `agent`, `operator`, `auditor`, `importer`, `approver`로 분리했습니다.
- CLI는 `--api-token` 또는 `GOVMESH_*_TOKEN` 환경 변수를 통해 인증 헤더를 붙입니다.
- mTLS는 앱이 직접 종단하지 않고, 내부 프록시가 전달하는 `X-Client-Cert-SHA256` 지문을 allowlist로 검증할 수 있게 했습니다.

### 2. 감사 로그 봉인

- 기존 해시 체인에 선택형 HMAC 서명을 추가했습니다.
- `GOVMESH_AUDIT_SIGNING_KEY`가 설정된 환경에서는 이벤트별 `signature`를 검증합니다.
- `/audit/events`로 외부 감사 이벤트를 받을 때 기존 `event_hash`, `previous_hash`, `signature` 값은 신뢰하지 않고 서버가 다시 계산합니다.
- 현재 audit head를 외부 보관용 checkpoint JSON으로 export하고, 이후 현재 head와 일치하는지 검증할 수 있습니다.

### 3. 격리 게이트웨이 방어 강화

- 업로드 크기 제한을 추가했습니다.
- Base64 입력 검증을 엄격하게 바꿨습니다.
- ZIP 내부 경로 탈출(`../`), 위험 확장자, 중첩 압축 파일, 과도한 압축률, 과도한 압축 해제 크기를 탐지합니다.
- 스캔 로그에는 원문 대신 finding 종류와 해시 중심의 정보만 남기도록 유지했습니다.
- `packages/govmesh_quarantine` 검사 엔진을 분리해 확장 가능한 scanner/report 구조를 만들었습니다.
- Office macro 흔적, PDF JavaScript/OpenAction, PowerShell encoded command 같은 signature rule을 기본 검사에 추가했습니다.

### 4. RAG 검색 정책

- 민감 chunk는 기본 검색 결과에서 제외합니다.
- 운영자가 명시적으로 `include_sensitive=True`를 요청한 경우에만 마스킹된 민감 chunk를 조회할 수 있습니다.
- 이 흐름은 "민감정보를 마스킹했더라도 기본 답변 근거로 쓰지 않는다"는 정책을 코드 기본값으로 둔 것입니다.

### 5. 로컬 런타임 무결성

- `LocalLlamaCppProvider`는 승인 여부만으로 실행되지 않도록 강화했습니다.
- 실행 파일과 모델 파일의 SHA-256 pinning을 요구합니다.
- `pre_args`는 기본 차단하고, 테스트나 명시 승인된 wrapper 실행에서만 `allow_pre_args=True`로 허용합니다.

### 6. 정책 스캐너 결과 구조

- finding에 `confidence`와 `match_hash`를 추가했습니다.
- 정책 결과에서 원문 매칭 값을 노출하지 않고, 후속 감사와 디버깅은 해시 기반으로 추적할 수 있게 했습니다.
- 주민등록번호와 사업자등록번호는 checksum 메타데이터를 기록합니다.
- 여권번호 후보와 사업자등록번호 후보 recognizer를 추가했습니다.

### 7. Grounding 검증

- LLM 응답이 검색 context ID를 실제로 근거로 달았는지 확인하는 `verify_grounding`을 추가했습니다.
- `generate_with_policy`는 grounding 결과와 `needs_review` 플래그를 함께 반환합니다.

### 8. 운영자 진단

- `scripts/govmesh_doctor.py`를 추가해 필수 환경 변수와 로컬 포트 사용 가능 여부를 점검합니다.
- `scripts/generate_local_tokens.py`로 로컬 토큰과 감사 서명키, SSO 프록시 secret을 생성할 수 있습니다.

### 9. 외부 보안 엔진 연동

- `ExternalScannerConfig`와 `run_external_scanner`를 추가했습니다.
- 외부 AV/YARA/CDR 도구는 실행 파일 SHA-256과 보조 스크립트/룰 파일 SHA-256이 맞을 때만 실행됩니다.
- 외부 도구는 JSON findings를 반환하는 계약으로 통일했습니다.

### 10. CDR 무해화 산출물

- 텍스트 계열 파일은 제어문자 제거와 정책 스캐너 마스킹을 거친 sanitized 파일로 재구성할 수 있습니다.
- 지원하지 않는 파일 형식은 자동 승인하지 않고 `manual_review_required`로 남깁니다.

### 11. SSO 프록시 서명

- 기관 SSO는 프록시에서 종단하고, 앱은 `X-GovMesh-*` 헤더의 HMAC 서명을 검증하는 구조를 추가했습니다.
- unsigned identity header는 신뢰하지 않습니다.

## 남은 개발 과정

1. 정식 사용자/기관 계정 체계
   - 현재는 로컬 API 토큰, mTLS 프록시 지문 allowlist, 서명된 SSO 프록시 헤더 기반입니다.
   - 다음 단계는 실제 기관 IdP와 단말 인증서 생명주기 관리입니다.

2. 전문 파일 검사
   - 현재 Quarantine Gateway는 경량 정적 검사, signature rule 엔진, pinned external scanner 계약을 포함합니다.
   - 실제 제출급 환경에서는 기관이 쓰는 AV/YARA/CDR 제품의 실제 실행파일과 룰셋을 등록해야 합니다.

3. Presidio 수준 PII 인식기
   - 현재는 정규식 기반 스캐너에 confidence/hash/checksum/context metadata를 보강한 상태입니다.
   - 다음 단계는 실제 행정 corpus 기반 오탐 리뷰와 기관별 custom recognizer 관리입니다.

4. 근거성 평가와 환각 방지
   - RAG context ID 기반 grounding report는 들어갔습니다.
   - 다음 단계는 문장별 citation 검증, 근거 없는 문장 차단, human review 큐입니다.

5. 감사 로그 운영 보관
   - HMAC 서명과 checkpoint export는 들어갔습니다.
   - 운영 단계에서는 WORM 저장소, 키 관리 절차, 외부 감사 보관소가 필요합니다.

6. Windows 설치 UX
   - 현재는 CLI, 서비스 스크립트, 운영자 doctor, 토큰 생성 스크립트 중심입니다.
   - 비개발자 운영자를 위해 설치 마법사 UI와 장애 진단 화면을 추가해야 합니다.
