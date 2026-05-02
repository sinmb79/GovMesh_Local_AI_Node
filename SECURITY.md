# Security Policy

GovMesh Local AI Node는 로컬 우선 보안 실험용 MVP입니다.

## 신고

보안 문제를 발견하면 GitHub issue에 공개 exploit detail을 올리지 말고, 재현 조건과 영향을 요약해 관리자에게 먼저 전달하세요.

## 기본 원칙

- 실제 개인정보를 저장소에 올리지 않습니다.
- 실제 정부 또는 기관 내부 문서를 저장소에 올리지 않습니다.
- token, key, certificate, cookie를 commit하지 않습니다.
- 외부 스캐너와 로컬 LLM 실행 파일은 SHA-256 pinning 후 사용합니다.

## 지원 범위

현재 공개 MVP는 로컬 실행과 검증 흐름을 대상으로 합니다. 실제 기관망 배포, SSO, WORM 저장소, AV/YARA/CDR 제품 연동은 기관 환경에 맞춘 별도 검토가 필요합니다.
