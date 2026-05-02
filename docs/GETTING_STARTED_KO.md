# GovMesh 처음 시작하기

이 문서는 개발자가 아니어도 로컬에서 GovMesh를 실행해 볼 수 있도록 만든 빠른 시작 안내입니다.

## 준비물

- Windows 10/11
- Python 3.11 이상
- Git
- PowerShell

## 1. 내려받기

```powershell
git clone https://github.com/sinmb79/GovMesh_Local_AI_Node.git
cd GovMesh_Local_AI_Node
```

## 2. 설치

```powershell
python -m pip install -e .[dev]
python scripts/setup_local_env.py
. .\.govmesh-local\env.ps1
```

## 3. 상태 점검

```powershell
python scripts/govmesh_doctor.py
```

`ok: true`가 나오면 로컬 실행 준비가 된 것입니다.

## 4. 샘플 실행

```powershell
python -m apps.node_agent performance-doctor
python -m apps.node_agent scan-folder --path samples/documents
python -m apps.node_agent query --sample samples/documents --question "근거 문서를 바탕으로 요약해줘"
```

## 5. 서버 실행

PowerShell 창 1:

```powershell
. .\.govmesh-local\env.ps1
python -m apps.control_plane
```

PowerShell 창 2:

```powershell
. .\.govmesh-local\env.ps1
python -m apps.quarantine_gateway
```

PowerShell 창 3:

```powershell
. .\.govmesh-local\env.ps1
python -m apps.admin_ui --control-plane http://127.0.0.1:8787 --serve
```

브라우저에서 `http://127.0.0.1:8795`를 엽니다.

## 6. 배포 zip 만들기

```powershell
python scripts/build_release_bundle.py
```

`dist/` 폴더에 zip 파일과 checksum 파일이 생성됩니다.

## 주의

- 실제 개인정보나 실제 정부 문서를 넣지 마세요.
- 외부 공개 서버에 그대로 올리는 프로젝트가 아닙니다.
- 기본 실행은 로컬 PC `127.0.0.1`을 기준으로 합니다.
