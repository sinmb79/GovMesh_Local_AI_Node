# Security Model

## Default Posture

GovMesh는 폐쇄망과 로컬 우선 환경을 기본값으로 둡니다. 내부망 PC도 자동으로 신뢰하지 않고, 노드 등록과 정책 승인을 거친 작업만 실행합니다.

## Network Rules

- 기본 bind host는 `127.0.0.1`입니다.
- `0.0.0.0` 또는 public interface bind는 기본 거부합니다.
- 운영 서버 진입점은 `Authorization: Bearer <token>` 기반 API 토큰이 없으면 시작하지 않습니다.
- 토큰 역할은 `agent`, `operator`, `auditor`, `importer`, `approver`로 나누며, 상태 변경 API는 역할 검사를 통과해야 합니다.
- mTLS는 내부 reverse proxy 또는 gateway에서 종단하고, 앱은 `X-Client-Cert-SHA256` 지문 allowlist를 검증하는 방식으로 연동할 수 있습니다.
- 기관 SSO도 프록시에서 종단하고, 앱은 HMAC 서명된 `X-GovMesh-*` identity header만 신뢰합니다.
- 외부 LLM 호출은 MVP에서 금지합니다.
- 외부 모델, 문서, 패치는 Quarantine Gateway를 통과해야 합니다.
- 테스트는 외부 네트워크 없이 통과해야 합니다.

## Data Rules

- 실제 정부 데이터와 실제 개인정보는 저장소에 넣지 않습니다.
- 감사로그에는 raw prompt 또는 raw PII를 저장하지 않습니다.
- 민감 content는 mask 또는 hash 처리합니다.
- 감사로그는 해시 체인과 선택형 HMAC 서명으로 위변조를 탐지합니다.
- 감사로그 head checkpoint는 외부 보관소나 WORM 저장소로 내보내 사후 조작 여부를 비교할 수 있습니다.
- 샘플 데이터는 가짜 데이터임을 명시합니다.

## Quarantine Flow

```text
External Fetch Zone
  -> AI Quarantine Gateway
  -> static/signature/external scanner
  -> optional CDR sanitize
  -> Approval Console
  -> Internal Registry
  -> GovMesh Distribution
```

## Zero Trust Mapping

- 내부 위치만으로 신뢰하지 않습니다.
- 사용자, 기기, 작업 권한을 각각 확인합니다.
- 노드 상태와 정책 상태를 작업마다 확인합니다.
- 모든 중요 상태 변경은 감사 이벤트를 남깁니다.

## Data Diode Guidance

단방향 반입은 hard-to-inspect 데이터를 격리망으로 들여오는 보조 통제로 볼 수 있습니다. 그러나 양방향 API 흐름을 만들기 위해 양방향 diode를 붙이는 설계는 피합니다.

## References

- NIST SP 800-207 Zero Trust Architecture: https://csrc.nist.gov/pubs/sp/800/207/final
- NCSC OT boundary guidance: https://www.ncsc.gov.uk/collection/operational-technology/secure-connectivity/principle-5
- KISA N2SF support notice: https://www.kisa.or.kr/401/form?lang_type=KO&postSeq=3626
