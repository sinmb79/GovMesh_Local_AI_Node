# 공개 배포 가이드

## 배포 목표

GovMesh는 누구나 내려받아 로컬에서 시험할 수 있어야 합니다. 배포 파일은 소스, 문서, 샘플, 설치 스크립트, 검증 스크립트를 포함합니다.

## 배포 파일 생성

```powershell
python scripts/build_release_bundle.py
```

생성물:

```text
dist/govmesh-local-ai-node-v0.3.1.zip
dist/SHA256SUMS.txt
dist/release_manifest.json
```

## 릴리즈 전 확인

```powershell
python -m pytest
python scripts/release_gate.py
python scripts/build_evidence_package.py
```

## GitHub Release 권장 첨부 파일

- `govmesh-local-ai-node-v0.3.1.zip`
- `SHA256SUMS.txt`
- `release_manifest.json`

## 사용자 안내 문구

```text
GovMesh Local AI Node는 보안 제약이 있는 조직 환경을 가정한 로컬 우선 AI 노드입니다.
처음 사용자는 docs/GETTING_STARTED_KO.md를 먼저 읽고, Windows 사용자는 docs/INSTALL_WINDOWS.md를 따라 실행하세요.
```

## 공개 배포 시 제외해야 할 것

- `.govmesh-local/`
- `.env`
- 실제 token, key, certificate
- 실제 개인정보
- 실제 정부 또는 기관 내부 문서
- `reports/`, `evidence/`, `dist/`의 임시 산출물
