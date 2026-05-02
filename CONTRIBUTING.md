# Contributing

GovMesh는 한국어 우선 문서와 로컬 실행 가능성을 중요하게 봅니다.

## 개발 흐름

```powershell
python -m pip install -e .[dev]
python -m pytest
python scripts/release_gate.py
```

## PR 기준

- 실제 개인정보나 실제 내부 문서를 추가하지 않습니다.
- 새 기능은 최소 테스트를 포함합니다.
- 보안 관련 변경은 `docs/RISK_REGISTER.md` 또는 `docs/SECURITY_MODEL.md` 갱신을 함께 고려합니다.
- Windows PowerShell에서 실행 가능한 명령을 우선합니다.

## 문서 스타일

- 한국어를 기본으로 합니다.
- 과장된 홍보 문구보다 기능, 제약, 검증 방법을 명확히 적습니다.
