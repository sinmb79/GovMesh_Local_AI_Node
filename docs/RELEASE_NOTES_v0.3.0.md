# GovMesh Local AI Node v0.3.0

## 핵심 변경

- 로컬 설치와 실행을 위한 Windows 보조 스크립트 추가
- 배포 zip, SHA256SUMS, release manifest 생성 스크립트 추가
- 사람 검토 큐와 governance evidence workflow 추가
- SSO proxy signature, external scanner adapter, CDR sanitize 기반 추가
- 감사 checkpoint store와 grounding 검증 강화
- 한국어 시작 문서와 배포 문서 정리

## 검증

- `python -m pytest`
- `python scripts/release_gate.py`
- GitHub Actions CI

## 주의

실제 개인정보, 실제 정부 문서, 기관 내부 자료를 샘플이나 테스트에 넣지 마세요.
