# Windows 설치 가이드

## 자동 설치

```powershell
.\scripts\install.ps1
```

설치 스크립트는 다음 작업을 수행합니다.

- `.venv` 생성
- 패키지 설치
- `.govmesh-local/env.ps1` 생성
- 운영 준비 상태 점검

설치 후 환경 변수를 불러옵니다.

```powershell
. .\.govmesh-local\env.ps1
```

## 로컬 스택 시작

```powershell
.\scripts\start_local_stack.ps1
```

기본 포트:

- Control Plane: `127.0.0.1:8787`
- Quarantine Gateway: `127.0.0.1:8790`
- Admin UI: `127.0.0.1:8795`

## 로컬 스택 종료

```powershell
.\scripts\stop_local_stack.ps1
```

## 수동 설치

```powershell
python -m pip install -e .[dev]
python scripts/setup_local_env.py
. .\.govmesh-local\env.ps1
python scripts/govmesh_doctor.py
```

## 문제 해결

- Python을 찾지 못하면 Python 3.11 이상을 설치하고 PowerShell을 다시 여세요.
- 포트가 사용 중이면 `scripts/govmesh_doctor.py`가 알려주는 포트를 확인하세요.
- 실행 정책 문제는 현재 PowerShell에서만 다음 명령으로 완화할 수 있습니다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
